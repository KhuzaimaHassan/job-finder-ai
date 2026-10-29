import asyncio
import threading
import time
from datetime import datetime, timezone
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, Mock, patch

import httpx

from app.services import db_retry, ingestion, job_fetcher as jf, job_sources as src
from tests.support import MemoryDB, MemoryQuery
from tests.test_reliability import job


class IngestionRecoveryTests(IsolatedAsyncioTestCase):
    def setUp(self):
        jf._job_store, jf._cache_loaded, jf._refresh_finished = {}, False, False
        ingestion._status = {"running": False, "sources": {}, "last_completed_at": None}

    def providers(self, db, remote=None, remotive=None):
        overrides = [patch.object(jf, "_get_supabase_client", return_value=db),
            patch.object(jf, "fetch_remoteok_jobs", remote or AsyncMock(return_value=src.Feed())),
            patch.object(jf, "fetch_remotive_jobs", remotive or AsyncMock(return_value=src.Feed())),
            patch.object(jf, "fetch_himalayas_jobs", AsyncMock(return_value=src.Feed())),
            patch.object(jf, "fetch_jobicy_jobs", AsyncMock(return_value=src.Feed())),
            patch.object(jf.settings, "ADZUNA_APP_ID", None)]
        for override in overrides:
            override.start()
            self.addCleanup(override.stop)

    async def test_transport_retries_are_opt_in_bounded_and_not_for_validation_errors(self):
        callback = Mock(side_effect=[httpx.RemoteProtocolError("lost response"), httpx.ReadTimeout("timeout"), "ok"])
        with patch.object(db_retry.asyncio, "sleep", AsyncMock()) as pause:
            self.assertEqual(await db_retry.db_call(callback, attempts=3), "ok")
        self.assertEqual(callback.call_count, 3)
        self.assertEqual(pause.await_count, 2)
        callback = Mock(side_effect=httpx.RemoteProtocolError("lost response"))
        with self.assertRaises(httpx.RemoteProtocolError):
            await db_retry.db_call(callback)  # RPC/insert calls are not replayed.
        self.assertEqual(callback.call_count, 1)
        callback = Mock(side_effect=ValueError("invalid data"))
        with self.assertRaises(ValueError):
            await db_retry.db_call(callback, attempts=3)
        self.assertEqual(callback.call_count, 1)

    async def test_lost_upsert_response_recovers_without_duplicate_jobs(self):
        class LostResponseQuery(MemoryQuery):
            def execute(self):
                result = super().execute()
                if self.name == "jobs" and self.operation == "upsert":
                    self.db.attempts += 1
                    if self.db.attempts == 1:
                        raise httpx.RemoteProtocolError("response lost after commit")
                return result
        class LostResponseDB(MemoryDB):
            attempts = 0
            def table(self, name): return LostResponseQuery(self, name)
        db = LostResponseDB()
        with patch.object(jf, "_get_supabase_client", return_value=db), \
             patch.object(db_retry.asyncio, "sleep", AsyncMock()):
            await jf.persist_jobs_to_supabase([job("recovered")])
        self.assertEqual(db.attempts, 2)
        self.assertEqual([row["id"] for row in db.rows["jobs"]], ["recovered"])
        self.assertEqual(db.deletes, [])

    async def test_failed_checkpoint_does_not_cancel_other_providers_and_final_state_recovers(self):
        class CheckpointQuery(MemoryQuery):
            def execute(self):
                checkpoint = (self.name == "job_ingestion_state" and self.operation == "update"
                    and "lease_owner" not in self.payload
                    and self.payload["sources"].get("remoteok", {}).get("status") == "success")
                if not checkpoint:
                    return super().execute()
                with self.db.guard:
                    self.db.active += 1
                    self.db.maximum = max(self.db.maximum, self.db.active)
                    self.db.attempts += 1
                    fail = self.db.attempts <= 3
                try:
                    time.sleep(.005)
                    if fail:
                        raise httpx.RemoteProtocolError("status response lost")
                    return super().execute()
                finally:
                    with self.db.guard: self.db.active -= 1
        class CheckpointDB(MemoryDB):
            attempts = active = maximum = 0
            guard = threading.Lock()
            def table(self, name): return CheckpointQuery(self, name)
        db = CheckpointDB()
        finished = []
        async def slower_provider():
            await asyncio.sleep(.03)
            finished.append("remotive")
            return src.Feed([job("other-source", source="remotive")])
        self.providers(db, AsyncMock(return_value=src.Feed([job("remote-result")])), slower_provider)
        await ingestion.refresh_jobs()
        state = db.rows["job_ingestion_state"][0]
        self.assertEqual(finished, ["remotive"])
        self.assertEqual(db.maximum, 1)
        self.assertGreaterEqual(db.attempts, 4)
        self.assertTrue(all(value["status"] == "success" for value in state["sources"].values()))
        self.assertIsNone(state["lease_owner"])
        self.assertEqual(db.rows["job_fetch_runs"][0]["status"], "success")
        self.assertIsNone(ingestion.status().get("error"))
        self.assertEqual({row["id"] for row in db.rows["jobs"]}, {"remote-result", "other-source"})

    async def test_run_history_failure_still_releases_lease_and_reports_error(self):
        class HistoryQuery(MemoryQuery):
            def execute(self):
                if self.name == "job_fetch_runs" and self.operation == "update":
                    raise RuntimeError("history write failure")
                return super().execute()
        class HistoryDB(MemoryDB):
            def table(self, name): return HistoryQuery(self, name)
        db = HistoryDB({"jobs": [{**job().model_dump(), "fetched_at": datetime.now(timezone.utc).isoformat()}]})
        self.providers(db)
        await ingestion.refresh_jobs()
        self.assertIsNone(db.rows["job_ingestion_state"][0]["lease_owner"])
        self.assertIn("history persistence failed", ingestion.status()["error"])
        self.assertEqual(len(jf.get_all_jobs()), 1)
        self.assertEqual(db.deletes, [])

    async def test_availability_write_cannot_replace_another_providers_new_jobs(self):
        started = threading.Event()
        class AvailabilityQuery(MemoryQuery):
            def execute(self):
                if self.name == "jobs" and self.operation == "update" and "availability" in self.payload:
                    started.set()
                    time.sleep(.05)
                return super().execute()
        class AvailabilityDB(MemoryDB):
            def table(self, name): return AvailabilityQuery(self, name)
        old = job("jobicy_1", source="jobicy", provider_id="1")
        db = AvailabilityDB({"jobs": [{**old.model_dump(), "fetched_at": datetime.now(timezone.utc).isoformat()}]})
        async def concurrent_provider():
            self.assertTrue(await asyncio.to_thread(started.wait, 2))
            return src.Feed([job("concurrent", title="Concurrent Python Engineer")])
        self.providers(db, concurrent_provider)
        with patch.object(jf, "fetch_jobicy_jobs", AsyncMock(return_value=src.Feed([
                job("jobicy_2", title="New Jobicy Python Engineer", source="jobicy", provider_id="2")]))), \
             patch.object(ingestion, "jobicy_status", AsyncMock(return_value={"jobicy_1": "closed"})):
            await ingestion.refresh_jobs()
        self.assertEqual({item.id for item in jf.get_all_jobs()}, {"concurrent", "jobicy_2"})
        self.assertEqual(db.deletes, [])
