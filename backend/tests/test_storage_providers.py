import io
from datetime import datetime, timedelta, timezone
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, patch

import httpx
from fastapi import HTTPException, UploadFile
from starlette.datastructures import Headers

from app.routers import resume
from app.services import ingestion, job_sources as src, job_fetcher as jf
from tests.support import MemoryDB, make_pdf
from tests.test_reliability import job


def upload():
    return UploadFile(io.BytesIO(make_pdf()), filename="resume.pdf",
                      headers=Headers({"content-type": "application/pdf"}))


def rate_limit():
    response = httpx.Response(429, request=httpx.Request("GET", "https://example.invalid/?key=private"),
                              headers={"Retry-After": "172800"})
    return httpx.HTTPStatusError("private diagnostic", request=response.request, response=response)


def jobicy_item(identity):
    return {"id": identity, "jobTitle": "Python Engineer", "companyName": "Local",
            "pubDate": datetime.now(timezone.utc).isoformat()}


class StorageProviderTests(IsolatedAsyncioTestCase):
    def setUp(self):
        jf._job_store, jf._cache_loaded, jf._refresh_finished = {}, False, False
        ingestion._status = {"running": False, "sources": {}, "last_completed_at": None}

    async def test_storage_failure_does_not_save_partial_resume_or_replace_previous_version(self):
        db = MemoryDB({"resumes": [{"id": "old", "user_id": "local", "raw_text": "old", "file_path": "local/old.pdf"}]})
        db.storage.files["local/old.pdf"] = b"old PDF"
        db.storage.fail_upload = True
        with patch.object(resume, "get_user_supabase", return_value=db), \
             patch.object(resume, "parse_resume_with_gemini", AsyncMock(return_value={"skills": ["Python"]})), \
             patch.object(resume, "clear_user_embedding") as clear:
            with self.assertRaises(HTTPException) as caught:
                await resume.upload_and_parse_resume(upload(), {"id": "local", "token": "test"})
        self.assertEqual(caught.exception.status_code, 503)
        self.assertIn("previous resume is unchanged", caught.exception.detail)
        self.assertEqual(len(db.rows["resumes"]), 1)
        self.assertEqual(db.storage.files, {"local/old.pdf": b"old PDF"})
        clear.assert_not_called()

    async def test_saved_pdf_status_and_legacy_missing_file_status(self):
        db = MemoryDB({"resumes": [{"user_id": "local", "raw_text": "legacy", "parsed_at": "2020-01-01"}]})
        with patch.object(resume, "get_user_supabase", return_value=db), \
             patch.object(resume, "parse_resume_with_gemini", AsyncMock(return_value={"skills": ["Python"]})):
            self.assertFalse((await resume.get_resume({"id": "local", "token": "test"}))["pdf_stored"])
            saved = await resume.upload_and_parse_resume(upload(), {"id": "local", "token": "test"})
            self.assertTrue(saved["pdf_stored"])
            self.assertTrue((await resume.get_resume({"id": "local", "token": "test"}))["pdf_stored"])
        self.assertEqual(len(db.storage.files), 1)
        self.assertNotIn("file_path", saved)

    async def test_jobicy_next_pass_checks_newest_page_then_resumes_backfill(self):
        replies = [{"jobs": [jobicy_item(1)], "nextCursor": "a"},
                   {"jobs": [jobicy_item(2)], "nextCursor": "b"},
                   {"jobs": [jobicy_item(3)], "nextCursor": "new-head"},
                   {"jobs": [jobicy_item(4)], "nextCursor": None}]
        request = AsyncMock(side_effect=replies)
        with patch.object(src, "request_json", request), patch.object(src.asyncio, "sleep", AsyncMock()), \
             patch.object(src.settings, "JOB_PROVIDER_MAX_PAGES", 2):
            first = await src.fetch_jobicy_jobs()
            second = await src.fetch_jobicy_jobs(continuation=first.continuation)
        self.assertTrue(first.capped)
        self.assertEqual(first.continuation["cursor"], "b")
        self.assertNotIn("cursor", request.call_args_list[2].args[2])
        self.assertEqual(request.call_args_list[3].args[2]["cursor"], "b")
        self.assertEqual([item.id for item in second], ["jobicy_3", "jobicy_4"])
        self.assertFalse(second.capped)
        self.assertIsNone(second.continuation)

    async def test_expired_jobicy_cursor_is_not_replayed_and_repeated_cursor_is_not_success(self):
        request = AsyncMock(side_effect=[{"jobs": [jobicy_item(1)], "nextCursor": "new"},
                                         {"jobs": [jobicy_item(1)], "nextCursor": "new"}])
        saved = {"cursor": "expired", "started_at": (datetime.now(timezone.utc)-timedelta(days=2)).isoformat()}
        with patch.object(src, "request_json", request), patch.object(src.asyncio, "sleep", AsyncMock()):
            feed = await src.fetch_jobicy_jobs(continuation=saved)
        self.assertEqual(request.call_args_list[1].args[2]["cursor"], "new")
        self.assertEqual(len(feed), 1)
        self.assertEqual(feed.error, "Repeated pagination cursor")

    async def test_himalayas_advances_saved_page_without_losing_newest_jobs(self):
        payload = {"title": "Python Engineer", "companyName": "Local", "pubDate": datetime.now(timezone.utc).timestamp(),
                   "guid": "https://himalayas.app/companies/local/jobs/python", "applicationLink": "https://example.invalid/apply"}
        request = AsyncMock(side_effect=[{"jobs": [payload]}, {"jobs": [{**payload, "guid": "older"}]}])
        with patch.object(src, "request_json", request), patch.object(src.asyncio, "sleep", AsyncMock()), \
             patch.object(src.settings, "JOB_PROVIDER_MAX_PAGES", 2):
            feed = await src.fetch_himalayas_jobs(start_page=8)
        self.assertEqual([call.args[2]["page"] for call in request.call_args_list], [1, 8])
        self.assertEqual(feed.continuation, {"page": 9})
        self.assertEqual(len(feed), 2)

    async def test_partial_429_preserves_status_deadline_and_stops_later_queries(self):
        payload = {"title": "Python Engineer", "companyName": "Local", "pubDate": datetime.now(timezone.utc).timestamp(), "guid": "one"}
        request = AsyncMock(side_effect=[{"jobs": [payload]}, rate_limit()])
        with patch.object(src, "request_json", request), patch.object(src.asyncio, "sleep", AsyncMock()):
            feed = await src.fetch_himalayas_jobs()
        self.assertEqual(feed.error, "HTTP 429")
        self.assertNotIn("private", feed.error)
        self.assertGreater(datetime.fromisoformat(feed.retry_at), datetime.now(timezone.utc)+timedelta(days=1))
        fetch = AsyncMock(return_value=feed)
        with patch.object(jf, "fetch_himalayas_jobs", fetch):
            combined = await ingestion._himalayas()
        self.assertEqual(fetch.await_count, 1)
        self.assertEqual(combined.retry_at, feed.retry_at)
        self.assertEqual(combined.continuation["python"], 2)
        ingestion._status["sources"]["himalayas"] = {"continuation": combined.continuation}
        fetch = AsyncMock(return_value=src.Feed([job()], capped=True, error="HTTP 429", continuation={"page": 3}))
        with patch.object(jf, "fetch_himalayas_jobs", fetch):
            await ingestion._himalayas()
        self.assertEqual(fetch.call_args.args[0], "data science")

    async def test_partial_cooldown_and_progress_are_durable_but_continuations_are_private(self):
        db = MemoryDB()
        deadline = (datetime.now(timezone.utc)+timedelta(days=2)).isoformat()
        feed = src.Feed([job("jobicy_1", source="jobicy", provider_id="1")], capped=True,
                        error="HTTP 429", retry_at=deadline, continuation={"cursor": "opaque", "started_at": datetime.now(timezone.utc).isoformat()})
        status_check = AsyncMock()
        with patch.object(jf, "_get_supabase_client", return_value=db), \
             patch.object(jf, "fetch_remoteok_jobs", AsyncMock(return_value=src.Feed())), \
             patch.object(jf, "fetch_remotive_jobs", AsyncMock(return_value=src.Feed())), \
             patch.object(jf, "fetch_himalayas_jobs", AsyncMock(return_value=src.Feed())), \
             patch.object(jf, "fetch_jobicy_jobs", AsyncMock(return_value=feed)), \
             patch.object(ingestion, "jobicy_status", status_check), \
             patch.object(jf.settings, "ADZUNA_APP_ID", None):
            await ingestion.refresh_jobs()
        outcome = db.rows["job_ingestion_state"][0]["sources"]["jobicy"]
        self.assertEqual(outcome["next_due_at"], deadline)
        self.assertEqual(outcome["status"], "partial")
        self.assertEqual(outcome["continuation"], feed.continuation)
        self.assertTrue(outcome["backfill_pending"])
        self.assertNotIn("continuation", ingestion.status()["sources"]["jobicy"])
        status_check.assert_not_awaited()

    async def test_first_query_rate_limit_keeps_original_http_exception(self):
        with patch.object(jf, "fetch_himalayas_jobs", AsyncMock(side_effect=rate_limit())):
            with self.assertRaises(httpx.HTTPStatusError):
                await ingestion._himalayas()
