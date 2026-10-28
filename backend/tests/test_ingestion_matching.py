import asyncio
from datetime import datetime, timedelta, timezone
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
import httpx

from app.services import job_fetcher as jf, job_sources as src, ingestion, embeddings
from app.services.job_policy import searchable, location_eligible
from app.routers import jobs
from tests.support import MemoryDB
from tests.test_reliability import job


class IngestionMatchingTests(IsolatedAsyncioTestCase):
    def setUp(self):
        jf._job_store = {}
        jf._cache_loaded = False
        jf._refresh_finished = False

    def test_read_time_expiry_and_publication_age_and_unknown_status(self):
        now = datetime.now(timezone.utc)
        self.assertTrue(searchable(job()))
        self.assertFalse(searchable(job(expires_at=(now - timedelta(seconds=1)).isoformat())))
        self.assertFalse(searchable(job(posted_date=(now - timedelta(days=31)).isoformat(), fetched_at=now.isoformat())))
        self.assertFalse(searchable(job(fetched_at=(now - timedelta(days=15)).isoformat())))
        self.assertFalse(searchable(job(availability="closed")))
        self.assertFalse(searchable(job(availability="unknown")))
        self.assertFalse(searchable(job(posted_date=None)))

    def test_search_words_and_phrases_alias_dates_and_stable_pagination(self):
        records = [job("a", description="Python SQL services"), job("b", title="Python API Engineer", description="Python API services"),
                   job("c", title="Machine Learning Engineer", description="ML Python and SQL"),
                   job("old", title="Legacy Python Engineer", posted_date=(datetime.now(timezone.utc)-timedelta(days=10)).isoformat())]
        jf.publish_snapshot(records)
        self.assertEqual({j.id for j in jf.search_jobs(q="Python SQL")[0]}, {"a", "c"})
        self.assertEqual([j.id for j in jf.search_jobs(q='"machine learning"')[0]], ["c"])
        self.assertEqual([j.id for j in jf.search_jobs(q="ML")[0]], ["c"])
        self.assertEqual(jf.search_jobs(q="mail")[1], 0)
        self.assertEqual(jf.search_jobs(posted_within_days=7)[1], 3)
        all_ids = [j.id for j in jf.search_jobs()[0]]
        self.assertEqual(all_ids, [j.id for page in (1,2) for j in jf.search_jobs(page=page,per_page=2)[0]])

    def test_distinct_locations_are_not_deduplicated(self):
        jf.publish_snapshot([job("a",location="Karachi"),job("b",location="Lahore")])
        self.assertEqual(len(jf._job_store),2)

    def test_source_country_and_fractional_timezone_eligibility(self):
        self.assertFalse(location_eligible(job(location_restrictions=["United States"]), "Karachi, Pakistan"))
        self.assertFalse(location_eligible(job(timezone_restrictions=[330]), "Karachi"))
        self.assertTrue(location_eligible(job(timezone_restrictions=[300]), "Karachi"))
        self.assertFalse(location_eligible(job(location="USA",job_type="remote"), "Pakistan"))
        self.assertTrue(location_eligible(job(location="Worldwide",job_type="remote"), "Pakistan"))

    def test_city_only_and_unresolved_locations_are_not_assumed_worldwide(self):
        for location in ("Vancouver", "North Cambridge, Middlesex County", "Unresolved Specific City", "Remote-US", "U.S."):
            self.assertFalse(location_eligible(job(location=location,job_type="remote"),"Karachi"),location)

    def test_senior_titles_do_not_bypass_experience_on_short_descriptions(self):
        for title in ("Principal Data Scientist", "Staff ML Engineer", "Senior Python Engineer", "Lead MLOps Engineer"):
            self.assertIsNone(embeddings._profile_match({"skills":["Python"],"experience_years":0},None,job(title=title)))
        self.assertIsNotNone(embeddings._profile_match({"skills":["Python"],"experience_years":8},None,job(title="Principal Data Scientist")))

    def test_talent_pools_are_not_presented_as_vacancies(self):
        self.assertFalse(jf._is_relevant_job(job(title="Backend Developer - Talent Pool")))

    async def test_match_profile_updates_reorder_experience_and_exclude_foreign_jobs(self):
        roles=[job("junior",title="Junior Python Engineer",description="Python. 1 year of experience"),
               job("senior",title="Senior Python Engineer",description="Python. 8 years of experience"),
               job("foreign",location_restrictions=["USA"]),
               job("wrong",title="Java Engineer",description="Java services")]
        base={"skills":["Python"],"target_roles":["Python Engineer"],"location":"Karachi","experience_years":1}
        with patch.object(embeddings.settings,"GEMINI_API_KEY",None):
            first=await embeddings.rank_jobs_for_user("test",base,None,roles,100)
            self.assertEqual(first[0]["job"].id,"junior")
            self.assertNotIn("foreign",[r["job"].id for r in first])
            self.assertNotIn("wrong",[r["job"].id for r in first])
            self.assertTrue(any("Experience" in reason for reason in first[0]["match_reasons"]))
            changed=await embeddings.rank_jobs_for_user("test",{**base,"experience_years":8,"target_roles":["Senior Python Engineer"]},None,roles,100)
            self.assertEqual(changed[0]["job"].id,"senior")

    async def test_resume_skills_work_without_profile_and_names_do_not_match(self):
        with patch.object(embeddings.settings,"GEMINI_API_KEY",None):
            result=await embeddings.rank_jobs_for_user("x",{"name":"Python","skills":[]},None,[job()])
            self.assertEqual(result,[])
            result=await embeddings.rank_jobs_for_user("x",{}, {"skills":["Python"],"experience":[{"company":"irrelevant"}]},[job()])
            self.assertEqual(len(result),1)
            self.assertEqual(result[0]["matching_skills"],["python"])

    async def test_pagination_retains_first_page_on_later_failure(self):
        client=AsyncMock(); client.__aenter__.return_value=client
        payload={"id":1,"jobTitle":"Python Engineer","companyName":"Local","pubDate":datetime.now(timezone.utc).isoformat()}
        with patch.object(src.httpx,"AsyncClient",return_value=client), \
             patch.object(src,"request_json",AsyncMock(side_effect=[{"jobs":[payload],"nextCursor":"cursor-a"},httpx.ReadTimeout("synthetic")])), \
             patch.object(src.asyncio,"sleep",AsyncMock()):
            result=await src.fetch_jobicy_jobs()
        self.assertEqual(len(result),1)
        self.assertEqual(result.error,"ReadTimeout")

    async def test_429_stops_without_burst_retries(self):
        response=httpx.Response(429,request=httpx.Request("GET","https://example.invalid"),headers={"Retry-After":"3600"})
        client=AsyncMock(); client.get.return_value=response
        with self.assertRaises(httpx.HTTPStatusError):
            await src.request_json(client,"https://example.invalid")
        self.assertEqual(client.get.await_count,1)

    async def test_durable_budgets_survive_second_coordinator_run(self):
        now=datetime.now(timezone.utc).isoformat()
        db=MemoryDB({"jobs":[{**job().model_dump(),"fetched_at":now}]})
        remote=AsyncMock(return_value=src.Feed([job(title="Updated Python Engineer")]))
        with patch.object(jf,"_get_supabase_client",return_value=db), \
             patch.object(jf,"fetch_remoteok_jobs",remote), \
             patch.object(jf,"fetch_remotive_jobs",AsyncMock(return_value=src.Feed())), \
             patch.object(jf,"fetch_himalayas_jobs",AsyncMock(return_value=src.Feed())), \
             patch.object(jf,"fetch_jobicy_jobs",AsyncMock(return_value=src.Feed())), \
             patch.object(jf.settings,"ADZUNA_APP_ID",None):
            await ingestion.refresh_jobs()
            jf._job_store={}
            await ingestion.refresh_jobs()
        self.assertEqual(remote.await_count,1)
        self.assertEqual(len(db.rows["job_fetch_runs"]),1)
        self.assertEqual(db.rows["jobs"][0]["title"],"Updated Python Engineer")
        self.assertEqual(db.deletes,[])

    async def test_database_failure_retains_last_good_snapshot(self):
        jf.publish_snapshot([job()])
        with patch.object(jf,"fetch_jobs_from_supabase",AsyncMock(side_effect=RuntimeError("synthetic"))):
            result=await ingestion.refresh_jobs()
        self.assertEqual(len(result),1)

    async def test_extra_unrelated_profile_skills_do_not_lower_fit(self):
        with patch.object(embeddings.settings,"GEMINI_API_KEY",None):
            first=await embeddings.rank_jobs_for_user("x",{"skills":["Python"]},None,[job()])
            second=await embeddings.rank_jobs_for_user("x",{"skills":["Python","Rust","Java"]},None,[job()])
        self.assertEqual(first[0]["match_score"],second[0]["match_score"])

    async def test_run_deadline_records_failure_and_releases_lease(self):
        db=MemoryDB({"jobs":[{**job().model_dump(),"fetched_at":datetime.now(timezone.utc).isoformat()}]})
        async def slow():
            await asyncio.sleep(10)
        with patch.object(jf,"_get_supabase_client",return_value=db), \
             patch.object(jf,"fetch_remoteok_jobs",slow), \
             patch.object(jf,"fetch_remotive_jobs",AsyncMock(return_value=src.Feed())), \
             patch.object(jf,"fetch_himalayas_jobs",AsyncMock(return_value=src.Feed())), \
             patch.object(jf,"fetch_jobicy_jobs",AsyncMock(return_value=src.Feed())), \
             patch.object(jf.settings,"ADZUNA_APP_ID",None), \
             patch.object(jf.settings,"JOB_REFRESH_TIMEOUT_SECONDS",.02):
            await ingestion.refresh_jobs()
        state=db.rows["job_ingestion_state"][0]
        self.assertIsNone(state["lease_owner"])
        self.assertEqual(state["sources"]["remoteok"]["status"],"failed")
        self.assertEqual(db.rows["job_fetch_runs"][0]["status"],"partial")
        self.assertEqual(len(jf.get_all_jobs()),1)

    async def test_failed_persistence_does_not_publish_unsaved_replacement(self):
        db=MemoryDB({"jobs":[{**job().model_dump(),"fetched_at":datetime.now(timezone.utc).isoformat()}]})
        db.fail_insert.add("jobs")
        with patch.object(jf,"_get_supabase_client",return_value=db), \
             patch.object(jf,"fetch_remoteok_jobs",AsyncMock(return_value=src.Feed([job(title="Unsaved Python Engineer")]))), \
             patch.object(jf,"fetch_remotive_jobs",AsyncMock(return_value=src.Feed())), \
             patch.object(jf,"fetch_himalayas_jobs",AsyncMock(return_value=src.Feed())), \
             patch.object(jf,"fetch_jobicy_jobs",AsyncMock(return_value=src.Feed())), \
             patch.object(jf.settings,"ADZUNA_APP_ID",None):
            await ingestion.refresh_jobs()
        self.assertEqual(jf.get_all_jobs()[0].title,"Python Engineer")
        self.assertEqual(db.rows["job_ingestion_state"][0]["sources"]["remoteok"]["status"],"failed")

    async def test_closed_provider_status_preserves_archived_detail(self):
        old=job("jobicy_1",source="jobicy",provider_id="1")
        db=MemoryDB({"jobs":[{**old.model_dump(),"fetched_at":datetime.now(timezone.utc).isoformat()}]})
        with patch.object(jf,"_get_supabase_client",return_value=db), \
             patch.object(jf,"fetch_remoteok_jobs",AsyncMock(return_value=src.Feed())), \
             patch.object(jf,"fetch_remotive_jobs",AsyncMock(return_value=src.Feed())), \
             patch.object(jf,"fetch_himalayas_jobs",AsyncMock(return_value=src.Feed())), \
             patch.object(jf,"fetch_jobicy_jobs",AsyncMock(return_value=src.Feed())), \
             patch.object(ingestion,"jobicy_status",AsyncMock(return_value={"jobicy_1":"closed"})), \
             patch.object(jf.settings,"ADZUNA_APP_ID",None):
            await ingestion.refresh_jobs()
            self.assertEqual(jf.get_all_jobs(),[])
            self.assertFalse((await jf.get_archived_job_by_id("jobicy_1")).is_active)
        self.assertEqual(db.deletes,[])

    def test_warming_is_503_and_both_search_routes_apply_filters(self):
        app=FastAPI(); app.include_router(jobs.router)
        client=TestClient(app)
        self.assertEqual(client.get('/api/jobs').status_code,503)
        jf.publish_snapshot([job("a",job_type="remote",description="Python full-time"),job("b",job_type="remote",description="Python part-time")])
        first=client.get('/api/jobs',params={"job_type":"remote","employment_type":"fulltime"}).json()
        alias=client.get('/api/jobs/search',params={"type":"remote","employment_type":"fulltime"}).json()
        self.assertEqual(first["total"],1)
        self.assertEqual([j["id"] for j in first["jobs"]],[j["id"] for j in alias["jobs"]])
