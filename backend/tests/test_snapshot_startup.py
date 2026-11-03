import asyncio
import threading
from datetime import datetime, timedelta, timezone
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, patch

from app.services import job_fetcher as jf
from app.services.job_normalization import contains_skill
from tests.support import MemoryDB
from tests.test_reliability import job


class SnapshotStartupTests(IsolatedAsyncioTestCase):
    def setUp(self):
        jf._job_store, jf._cache_loaded, jf._refresh_finished = {}, False, False
        jf._snapshot_task, jf._last_snapshot_load = None, 0.0

    async def test_timeout_does_not_start_a_second_database_worker(self):
        started, release = threading.Event(), threading.Event()
        calls = []

        def load():
            calls.append(True)
            started.set()
            if not release.wait(3):
                raise RuntimeError("test worker was not released")
            return [job()]

        with patch.object(jf, "_load_persisted_jobs", load):
            first = asyncio.create_task(jf.reload_snapshot())
            try:
                self.assertTrue(await asyncio.to_thread(started.wait, 2))
                first.cancel()  # Same cancellation used by wait_for's deadline.
                with self.assertRaises(asyncio.CancelledError):
                    await first
                second = asyncio.create_task(jf.reload_snapshot())
                await asyncio.sleep(0)
                self.assertEqual(len(calls), 1)
                release.set()
                await second
                self.assertTrue(jf.cache_ready())
                self.assertEqual(len(calls), 1)
            finally:
                release.set()
                if jf._snapshot_task:
                    await asyncio.gather(jf._snapshot_task, return_exceptions=True)

    async def test_refresh_ticks_reuse_snapshot_but_expiry_and_force_reload_work(self):
        loader = AsyncMock(return_value=[job()])
        with patch.object(jf, "fetch_jobs_from_supabase", loader):
            await jf.reload_snapshot()
            await jf.reload_snapshot()
            self.assertEqual(loader.await_count, 1)
            jf._last_snapshot_load -= jf.settings.JOB_SNAPSHOT_RELOAD_SECONDS + 1
            await jf.reload_snapshot()
            self.assertEqual(loader.await_count, 2)
            await jf.reload_snapshot(force=True)
            self.assertEqual(loader.await_count, 3)

    async def test_failed_reload_retains_data_and_can_retry(self):
        jf.publish_snapshot([job("last-good")])
        loader = AsyncMock(side_effect=[RuntimeError("database unavailable"), [job("recovered")]])
        with patch.object(jf, "fetch_jobs_from_supabase", loader):
            with self.assertRaises(RuntimeError):
                await jf.reload_snapshot(force=True)
            self.assertEqual(list(jf._job_store), ["last-good"])
            await jf.reload_snapshot(force=True)
            self.assertEqual(list(jf._job_store), ["recovered"])

    async def test_freshness_filtered_before_hydration_and_archives_preserved(self):
        now = datetime.now(timezone.utc)
        rows = [job("fresh"), job("old", posted_date=(now - timedelta(days=31)).isoformat()),
                job("expired", expires_at=(now - timedelta(seconds=1)).isoformat()),
                job("closed", availability="closed"), job("unknown", availability="unknown"),
                job("future", posted_date=(now + timedelta(days=5)).isoformat())]
        db = MemoryDB({"jobs": [{**record.model_dump(), "fetched_at": now.isoformat()} for record in rows]})
        with patch.object(jf, "_get_supabase_client", return_value=db), \
             patch.object(jf, "_job_from_row", wraps=jf._job_from_row) as hydrate:
            self.assertEqual([record.id for record in await jf.fetch_jobs_from_supabase()], ["fresh"])
            self.assertEqual(hydrate.call_count, 1)
        self.assertEqual(len(db.rows["jobs"]), 6)
        self.assertEqual(db.deletes, [])

    async def test_small_pages_load_every_row_including_last_page(self):
        now = datetime.now(timezone.utc).isoformat()
        rows = [{**job(str(i), title=f"Python Engineer {i}").model_dump(), "fetched_at": now}
                for i in range(jf.SNAPSHOT_PAGE_SIZE + 1)]
        with patch.object(jf, "_get_supabase_client", return_value=MemoryDB({"jobs": rows})):
            self.assertEqual(len(await jf.fetch_jobs_from_supabase()), len(rows))

    def test_single_pass_tags_preserve_skill_boundaries_and_order(self):
        for text in ("<p>Python &amp; SQL, FastAPI, TypeScript, C++</p>",
                     "Go engineer with R, rstudio, golang, Rust and JavaScript",
                     "We go to work, are reliable, and use Java not JavaScript.",
                     "<b>" + " / ".join(jf.KNOWN_TAGS) + "</b>"):
            expected = [tag for tag in jf.KNOWN_TAGS if contains_skill(text, tag)][:10]
            self.assertEqual(jf._extract_tags(text), expected)

    def test_publication_discards_expired_memory_rows_without_deleting_history(self):
        jf.publish_snapshot([job("live"), job("closed", availability="closed"),
                             job("old", fetched_at=(datetime.now(timezone.utc) - timedelta(days=15)).isoformat())])
        self.assertEqual(list(jf._job_store), ["live"])
