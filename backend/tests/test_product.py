import asyncio
import threading
import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import AsyncMock, patch

from fastapi import HTTPException
from app.routers import applications, profile, ai
from app.services import job_fetcher as jf, ai_gemini
from app.services.learning_resources import for_skills
from app.services.resume_parser import ParsedResume
from tests.support import MemoryDB, MemoryQuery
from tests.test_reliability import job

USER = {"id": "local-user", "token": "synthetic"}


class ProductTests(unittest.IsolatedAsyncioTestCase):
    def test_live_frontend_alias_preflight_and_untrusted_origin_rejection(self):
        from fastapi.testclient import TestClient
        from app.main import app
        client = TestClient(app)
        for origin in ["https://ai-jobfinder.vercel.app", "https://job-finder-ai-kappa.vercel.app"]:
            response = client.options("/api/ai/ats-score", headers={
                "Origin": origin, "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "authorization,content-type"})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.headers["access-control-allow-origin"], origin)
        response = client.options("/api/ai/ats-score", headers={
            "Origin": "https://untrusted-project.vercel.app", "Access-Control-Request-Method": "POST"})
        self.assertEqual(response.status_code, 400)
        self.assertNotIn("access-control-allow-origin", response.headers)

    def test_precise_filters_can_combine_remote_and_employment(self):
        records = [job("partner", "Partner Solutions Engineer"), job("stack", "Full Stack Developer"),
                   job("remote-full", "Full-time Python Engineer", job_type="remote"),
                   job("part", "Part-time Python Engineer", job_type="remote")]
        jf._job_store = {j.id: j for j in records}
        self.assertEqual([j.id for j in jf.search_jobs(job_type="remote", employment_type="fulltime")[0]], ["remote-full"])
        self.assertEqual([j.id for j in jf.search_jobs(job_type="parttime")[0]], ["part"])

    def test_onsite_description_overrides_remote_default(self):
        from app.schemas.jobs import Job
        j = Job(id="office", title="Engineer", company="Local", location="USA", source="jobicy", url="",
                job_type="remote", description="We are an in-office company. Work on-site with customers.")
        self.assertEqual(j.job_type, "onsite")
        self.assertFalse(jf._is_relevant_job(j))

    def test_skill_words_do_not_match_inside_other_words(self):
        self.assertEqual(jf._extract_tags("Marketing manager: email campaigns and growth"), [])
        tags = jf._extract_tags("Python, JavaScript, Rust, R programming, Golang and AI development")
        self.assertIn("R", tags)
        self.assertIn("AI", tags)
        self.assertIn("Go", tags)
        self.assertNotIn("Java", tags)

    def test_resume_sync_preserves_preferences_and_merges_skills(self):
        db = MemoryDB({"profiles": [{"user_id": USER["id"], "skills": ["Docker"], "experience_years": 10, "target_roles": ["Architect"]}],
                       "resumes": [{"user_id": USER["id"], "skills": ["Python"], "experience": [{"title": "Engineer", "duration": "2016 - 2026"}]}]})
        with patch.object(profile, "get_user_supabase", return_value=db):
            result = profile.sync_from_resume(USER)
        self.assertEqual(result["experience_years"], 10)
        self.assertEqual(result["target_roles"], ["Architect"])
        self.assertEqual(result["skills"], ["Docker", "Python"])

    def test_tracker_notes_and_timestamps_and_ownership(self):
        db = MemoryDB()
        with patch.object(applications, "get_user_supabase", return_value=db):
            saved = applications.create_application(applications.ApplicationCreate(job_id="a", job_title="Python", company="Local"), USER)
            self.assertIsNone(saved["applied_date"])
            changed = applications.update_application(saved["id"], applications.ApplicationUpdate(status="Applied", notes="Interview Tuesday"), USER)
            self.assertEqual(changed["notes"], "Interview Tuesday")
            self.assertIsNotNone(changed["applied_date"])
            self.assertGreaterEqual(changed["updated_at"], saved["updated_at"])
            again = applications.create_application(applications.ApplicationCreate(job_id="a", job_title="Python", company="Local"), USER)
            self.assertEqual(again["status"], "Applied")
            self.assertEqual(len(db.rows["applications"]), 1)
            with self.assertRaises(HTTPException) as error:
                applications.update_application(saved["id"], applications.ApplicationUpdate(notes="other"), {**USER, "id": "other-user"})
            self.assertEqual(error.exception.status_code, 404)

    def test_concurrent_tracker_creates_are_idempotent(self):
        barrier, lock = threading.Barrier(2), threading.Lock()
        class RacingQuery(MemoryQuery):
            def execute(self):
                if self.operation == "select":
                    with lock:
                        self.db.reads += 1
                        n = self.db.reads
                        result = super().execute()
                    if n <= 2: barrier.wait(timeout=5)
                    return result
                with lock: return super().execute()
        class RacingDB(MemoryDB):
            reads = 0
            def table(self, name): return RacingQuery(self, name)
        db = RacingDB()
        body = applications.ApplicationCreate(job_id="same-job", job_title="Engineer", company="Local")
        with patch.object(applications, "get_user_supabase", return_value=db), ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: applications.create_application(body, USER), range(2)))
        self.assertEqual(results[0]["id"], results[1]["id"])
        self.assertEqual(len(db.rows["applications"]), 1)

    async def test_skill_gap_uses_description_and_reviewed_urls(self):
        fake = AsyncMock(return_value='{"missing_skills":["Docker"],"courses":[{"url":"javascript:evil()"}]}')
        with patch.object(ai_gemini, "_generate_text", fake):
            result = await ai_gemini.run_skill_gap("Python", "R", "This role needs Docker deployment experience")
        self.assertIn("Docker deployment", fake.call_args.args[1])
        self.assertEqual(result["courses"], for_skills(["Docker"]))
        self.assertTrue(result["courses"][0]["url"].startswith("https://docs.docker.com/"))
        self.assertEqual(ai.SkillGapRequest(job_required_skills="R").job_required_skills, "R")

    async def test_bad_ai_shapes_fail_instead_of_claiming_no_gaps(self):
        with patch.object(ai_gemini, "_generate_text", AsyncMock(return_value='{"missing_skills":"Docker"}')):
            with self.assertRaises(ValueError): await ai_gemini.run_skill_gap("Python", "Docker")
        with self.assertRaises(ValueError): ParsedResume.model_validate({"skills": "Python"})

    def test_coding_workflow_resource_does_not_recommend_known_language_basics(self):
        resources = for_skills(["Practical experience using AI coding assistants in a Python workflow", "Docker", "Python and SQL"])
        self.assertEqual(resources[0]["platform"], "GitHub Docs")
        self.assertEqual(len(resources), 4)
        self.assertEqual(len(for_skills(["Coding agents in Python", "AI coding assistants"])), 1)
        self.assertEqual(for_skills(["An unknown specialist skill"]), [])

    async def test_skill_and_interview_prompts_receive_resume_evidence(self):
        resume_text = "Completed BSc June 2026; internship April-September 2025. Built LangGraph agents."
        fake = AsyncMock(return_value='{"missing_skills":[]}')
        with patch.object(ai_gemini, "_generate_text", fake):
            await ai_gemini.run_skill_gap("Python", "Python", "Use AI coding tools in Python", resume_text)
        self.assertIn(resume_text, fake.call_args.args[1])
        fake = AsyncMock(return_value='{"questions":[{"question":"How would you test this?","answer_structure":"Outline checks."}]}')
        with patch.object(ai_gemini, "_generate_text", fake):
            await ai_gemini.run_interview_prep("ML Engineer", "Build models with Python", "Python", resume_text)
        self.assertIn(resume_text, fake.call_args.args[1])

    async def test_provider_receives_current_date_and_candidate_fact_rules(self):
        import google.generativeai as genai
        model = SimpleNamespace(generate_content_async=AsyncMock(return_value=SimpleNamespace(text="ok")))
        with patch.object(ai_gemini.settings, "GEMINI_API_KEY", "synthetic"), \
             patch.object(ai_gemini, "datetime") as clock, \
             patch.object(genai, "configure"), \
             patch.object(genai, "GenerativeModel", return_value=model) as factory:
            clock.now.return_value = datetime(2026, 10, 28, tzinfo=timezone.utc)
            self.assertEqual(await ai_gemini._generate_text("Career review", "BSc June 2026"), "ok")
        instruction = factory.call_args.kwargs["system_instruction"]
        self.assertIn("2026-10-28", instruction)
        self.assertIn("not your training cutoff", instruction)
        self.assertIn("Never turn a job requirement into a candidate fact", instruction)

    async def test_provider_quota_and_outages_return_safe_actionable_errors(self):
        import google.generativeai as genai
        from google.api_core.exceptions import ResourceExhausted, ServiceUnavailable, DeadlineExceeded
        for error, status in [(ResourceExhausted("private provider diagnostics"), 429),
                              (ServiceUnavailable("private provider diagnostics"), 503),
                              (DeadlineExceeded("private provider diagnostics"), 504)]:
            model = SimpleNamespace(generate_content_async=AsyncMock(side_effect=error))
            with self.subTest(status=status), \
                 patch.object(ai_gemini.settings, "GEMINI_API_KEY", "synthetic"), \
                 patch.object(genai, "configure"), \
                 patch.object(genai, "GenerativeModel", return_value=model):
                with self.assertRaises(ai_gemini.AIServiceError) as caught:
                    await ai_gemini._generate_text("Review", "Synthetic resume")
                response = ai._gemini_http(caught.exception)
                self.assertEqual(response.status_code, status)
                self.assertNotIn("private provider", response.detail)


if __name__ == "__main__":
    unittest.main()
