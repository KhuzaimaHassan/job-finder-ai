import asyncio
import io
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

from fastapi import HTTPException, UploadFile
from starlette.datastructures import Headers
from app.services import job_fetcher as jf, embeddings as em, resume_parser
from app.routers import resume
from app.schemas.jobs import Job
from tests.support import MemoryDB, make_pdf
from app.services import job_sources as sources, ingestion
from app.services.job_sources import Feed


def job(id="python", title="Python Engineer", **kwargs):
    kwargs.setdefault("posted_date", datetime.now(timezone.utc).isoformat())
    return Job(**{"id": id, "title": title, "company": "Local Test", "location": "Remote",
                  "description": "Python and FastAPI engineering", "url": "https://example.com/job",
                  "source": "remoteok", **kwargs})


class ReliabilityTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        jf._job_store = {}
        jf._cache_loaded = False
        jf._refresh_finished = False
        em._job_embeddings.clear()
        em._user_embeddings.clear()

    def test_real_pdf_extraction(self):
        self.assertIn("Python", resume_parser.extract_text_from_pdf(make_pdf()))
        with self.assertRaises(ValueError):
            resume_parser.extract_text_from_pdf(b"%PDF-invalid")

    async def test_himalayas_current_schema_and_bad_record_isolation(self):
        payload = {"title": "Python Engineer", "companyName": "Local Test", "pubDate": 1793109598,
                   "guid": "https://himalayas.app/companies/local/jobs/python", "description": "Python role",
                   "applicationLink": "https://example.com/apply", "minSalary": 100, "maxSalary": 200,
                   "currency": "USD", "salaryPeriod": "hourly", "locationRestrictions": ["Pakistan"]}
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        from httpx import Response, Request
        mock_client.get.return_value = Response(200, request=Request("GET", "https://himalayas.app/jobs/api/search"),
            json={"jobs": [None, {"title": ""}, {**payload, "expiryDate": 1}, payload]})
        with patch.object(sources.httpx, "AsyncClient", return_value=mock_client), patch.object(sources.asyncio, "sleep", AsyncMock()):
            results = await jf.fetch_himalayas_jobs("python")
        self.assertEqual(len(results), 1)
        self.assertTrue(results[0].posted_date.startswith("2026-10-27"))
        self.assertEqual(results[0].salary, "USD 100 - 200 / hourly")
        self.assertEqual(mock_client.get.call_args.kwargs["params"]["q"], "python")
        self.assertEqual(results[0].id, jf._parse_himalayas_job({**payload, "title": "Updated"}).id)

    async def test_existing_jobs_persist_and_warm_cache_precedes_provider(self):
        gate = asyncio.Event()
        original, fresh = job(), job(title="Updated Python Engineer")
        async def slow():
            await gate.wait()
            return [fresh]
        db = MemoryDB({"jobs": [{**original.model_dump(), "fetched_at": datetime.now(timezone.utc).isoformat()}]})
        with patch.object(jf, "fetch_jobs_from_supabase", AsyncMock(return_value=[original])), \
             patch.object(jf, "fetch_remoteok_jobs", slow), \
             patch.object(jf, "fetch_remotive_jobs", AsyncMock(return_value=Feed())), \
             patch.object(jf, "fetch_himalayas_jobs", AsyncMock(return_value=Feed())), \
             patch.object(jf, "fetch_jobicy_jobs", AsyncMock(return_value=Feed())), \
             patch.object(jf, "fetch_adzuna_jobs", AsyncMock(return_value=Feed())), \
             patch.object(jf, "_get_supabase_client", return_value=db):
            task = asyncio.create_task(jf.fetch_all_jobs())
            await asyncio.sleep(.01)
            self.assertEqual(jf.get_all_jobs()[0].title, original.title)
            gate.set()
            await task
        self.assertEqual(db.rows["jobs"][0]["title"], fresh.title)

    async def test_stale_database_jobs_are_archived_but_tracker_links_survive(self):
        now = datetime.now(timezone.utc)
        rows = [{**job("fresh").model_dump(exclude={"is_active"}), "fetched_at": now.isoformat()},
                {**job("old").model_dump(exclude={"is_active"}), "fetched_at": (now - timedelta(days=90)).isoformat()}]
        db = MemoryDB({"jobs": rows})
        with patch.object(jf, "_get_supabase_client", return_value=db):
            self.assertEqual([j.id for j in await jf.fetch_jobs_from_supabase()], ["fresh"])
            old = await jf.get_archived_job_by_id("old")
            self.assertEqual(old.id, "old")
            self.assertFalse(old.is_active)
            await jf.persist_jobs_to_supabase([job("old", title="Reopened Python Engineer")])
            self.assertEqual(len(await jf.fetch_jobs_from_supabase()), 2)
        self.assertEqual(db.deletes, [])

    async def test_resume_insert_failure_preserves_old_row_and_pdf(self):
        db = MemoryDB({"resumes": [{"id": "old", "user_id": "local", "raw_text": "old"}]})
        db.storage.files["local/old.pdf"] = b"old PDF"
        db.fail_insert.add("resumes")
        file = UploadFile(io.BytesIO(make_pdf()), filename="resume.pdf", headers=Headers({"content-type": "application/pdf"}))
        with patch.object(resume, "get_user_supabase", return_value=db), \
             patch.object(resume, "parse_resume_with_gemini", AsyncMock(return_value={"skills": ["Python"]})):
            with self.assertRaises(HTTPException):
                await resume.upload_and_parse_resume(file, {"id": "local", "token": "local"})
        self.assertEqual(db.rows["resumes"][0]["raw_text"], "old")
        self.assertEqual(db.storage.files, {"local/old.pdf": b"old PDF"})
        self.assertNotIn("resumes", db.deletes)

    async def test_successful_replacement_versions_pdf_and_returns_current_text(self):
        db = MemoryDB({"resumes": [{"id": "old", "user_id": "local", "raw_text": "old"}]})
        with patch.object(resume, "get_user_supabase", return_value=db), \
             patch.object(resume, "parse_resume_with_gemini", AsyncMock(return_value={"skills": ["Python"]})):
            for _ in range(2):
                file = UploadFile(io.BytesIO(make_pdf()), filename="resume.pdf", headers=Headers({"content-type": "application/pdf"}))
                result = await resume.upload_and_parse_resume(file, {"id": "local", "token": "local"})
                self.assertIn("Python", result["raw_text"])
        self.assertEqual(len(db.rows["resumes"]), 3)
        self.assertEqual(len(db.storage.files), 2)

    async def test_provider_failure_returns_consistent_keyword_scores(self):
        with patch.object(em.settings, "GEMINI_API_KEY", "synthetic"), \
             patch.object(em, "get_user_embedding", AsyncMock(return_value=[1., 0.])), \
             patch.object(em, "get_embeddings", AsyncMock(side_effect=ValueError("synthetic failure"))):
            ranked = await em.rank_jobs_for_user("local", {"skills": ["Python"]}, None, [job()])
        self.assertEqual(ranked[0]["match_score"], 50)
        self.assertEqual(ranked[0]["match_method"], "keyword")

    async def test_embedding_http_contract_uses_configured_supported_model(self):
        from httpx import Response, Request
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.post.return_value = Response(200, request=Request("POST", "https://example.invalid"),
                                                 json={"embeddings": [{"values": [1., 0.]}]})
        with patch.object(em.settings, "GEMINI_API_KEY", "synthetic"), \
             patch.object(em.settings, "GEMINI_EMBEDDING_MODEL", "gemini-embedding-001"), \
             patch.object(em.httpx, "AsyncClient", return_value=mock_client):
            self.assertEqual(await em.get_embedding("Python"), [1., 0.])
        args = mock_client.post.call_args
        self.assertIn("models/gemini-embedding-001:batchEmbedContents", args.args[0])
        self.assertEqual(args.kwargs["json"]["requests"][0]["content"]["parts"][0]["text"], "Python")
        self.assertNotIn("synthetic", args.args[0])

    async def test_incomplete_embedding_response_is_rejected(self):
        from httpx import Response, Request
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.post.return_value = Response(200, request=Request("POST", "https://example.invalid"),
                                                 json={"embeddings": []})
        with patch.object(em.settings, "GEMINI_API_KEY", "synthetic"), \
             patch.object(em.httpx, "AsyncClient", return_value=mock_client):
            with self.assertRaises(ValueError):
                await em.get_embedding("Python")

    async def test_semantic_matching_is_batched_bounded_and_content_cached(self):
        requests = []
        async def vectors(texts):
            requests.append(texts)
            return [[1., 0.] for _ in texts]
        jobs = [job(str(i)) for i in range(300)]
        with patch.object(em.settings, "GEMINI_API_KEY", "synthetic"), \
             patch.object(em.settings, "MATCH_CANDIDATE_LIMIT", 10), \
             patch.object(em, "get_embeddings", vectors):
            first = await em.rank_jobs_for_user("local", {"skills": ["Python"]}, None, jobs)
            await em.rank_jobs_for_user("local", {"skills": ["Python"]}, None, jobs)
            self.assertEqual([len(r) for r in requests], [1, 10])
            self.assertEqual(len(first), 10)
            self.assertEqual(first[0]["match_method"], "semantic")
            jobs[0] = job("0", title="Changed Python Engineer")
            await em.rank_jobs_for_user("local", {"skills": ["Python"]}, None, jobs)
            self.assertEqual(len(requests[-1]), 1)

    async def test_matching_timeout_returns_fallback(self):
        async def slow(*_args):
            await asyncio.sleep(10)
        with patch.object(em.settings, "GEMINI_API_KEY", "synthetic"), \
             patch.object(em.settings, "MATCH_TIMEOUT_SECONDS", .01), \
             patch.object(em, "get_user_embedding", slow):
            ranked = await em.rank_jobs_for_user("local", {"skills": ["Python"]}, None, [job()])
        self.assertEqual(ranked[0]["match_method"], "keyword")

    def test_different_embedding_dimensions_are_rejected(self):
        with self.assertRaises(ValueError):
            em._cosine_similarity([1.], [1., 0.])


if __name__ == "__main__":
    unittest.main()
