import unittest

from collector import checkpoint as cp
from collector.checkpoint import Checkpoints
from collector.errors import ConfigError, LockBusy
from collector.manifest import Manifest, overall_status, unit_stats
from collector.runlog import RunLock
from collector.storage import DatasetFiles

from .fakes import TempDir, d

P = "gsc/ds/S/"


class CheckpointTests(unittest.TestCase):
    def test_is_done_rules(self):
        self.assertTrue(Checkpoints.is_done({"status": cp.OK, "is_final": True}))
        self.assertTrue(Checkpoints.is_done({"status": cp.EMPTY, "is_final": True}))
        self.assertTrue(Checkpoints.is_done({"status": cp.TRUNCATED, "is_final": True}))   # 審查第 (3) 點
        self.assertFalse(Checkpoints.is_done({"status": cp.OK, "is_final": False}))
        self.assertFalse(Checkpoints.is_done({"status": cp.FAILED, "is_final": True}))
        self.assertFalse(Checkpoints.is_done({"status": cp.REGRESSION, "is_final": True}))
        self.assertFalse(Checkpoints.is_done(None))

    def test_persist_and_reload(self):
        with TempDir() as tmp:
            c = Checkpoints(tmp / "c.json")
            c.set(P + "2026-10-01_2026-10-01", cp.OK, is_final=True, rows=3)
            c2 = Checkpoints(tmp / "c.json")
            self.assertEqual(c2.get(P + "2026-10-01_2026-10-01")["rows"], 3)

    def test_corrupt_file_backed_up_and_stops(self):
        with TempDir() as tmp:
            (tmp / "c.json").write_text("{not json", encoding="utf-8")
            with self.assertRaises(ConfigError):
                Checkpoints(tmp / "c.json")
            self.assertFalse((tmp / "c.json").exists())
            self.assertTrue(any(p.name.startswith("c.json.corrupt-") for p in tmp.iterdir()))

    def test_last_done_and_pending(self):
        with TempDir() as tmp:
            c = Checkpoints(tmp / "c.json")
            c.set(P + "2026-10-01_2026-10-01", cp.OK, is_final=True)
            c.set(P + "2026-10-02_2026-10-02", cp.FAILED, is_final=True)
            c.set(P + "2026-10-03_2026-10-03", cp.OK, is_final=False)
            c.set(P + "2026-10-04_2026-10-04", cp.REGRESSION, is_final=True)
            c.set(P + "2026-10-05_2026-10-05", cp.NO_DATA, is_final=True)
            self.assertEqual(c.last_done_end(P), "2026-10-03")
            self.assertEqual([u.rsplit("/", 1)[-1] for u in c.pending(P)],
                             ["2026-10-02_2026-10-02", "2026-10-03_2026-10-03", "2026-10-04_2026-10-04"])

    def test_lock(self):
        with TempDir() as tmp:
            a = RunLock(str(tmp / "state" / "run.lock"))
            a.acquire("x")
            b = RunLock(str(tmp / "state" / "run.lock"))
            with self.assertRaises(LockBusy):
                b.acquire("y")
            b.acquire("y", force=True)
            self.assertTrue(b.held)
            b.release()
            self.assertFalse((tmp / "state" / "run.lock").exists())


class ManifestTests(unittest.TestCase):
    def test_empty_final_vs_provisional(self):
        with TempDir() as tmp:
            c = Checkpoints(tmp / "c.json")
            c.set(P + "2026-10-01_2026-10-01", cp.EMPTY, is_final=True)
            c.set(P + "2026-10-02_2026-10-02", cp.EMPTY, is_final=False)
            stats, failed, reg = unit_stats(c, P)
            self.assertEqual(stats["empty_final"], 1)
            self.assertEqual(stats["empty_provisional"], 1)

    def test_row_count_recomputed_not_accumulated(self):
        with TempDir() as tmp:
            c = Checkpoints(tmp / "c.json")
            m = Manifest(tmp / "manifest.json")
            f = DatasetFiles(tmp, "ds", "monthly", ["date", "scope_id", "k", "v"], ["date", "scope_id", "k"])
            for _ in range(3):
                f.apply("S", [d("2026-10-01")], [{"date": "2026-10-01", "scope_id": "S", "k": "a", "v": "1"}])
                c.set(P + "2026-10-01_2026-10-01", cp.OK, is_final=True)
                rec = m.update_dataset("gsc/ds/S", checkpoints=c, files=f, scope_id="S", success=True)
            self.assertEqual(rec["row_count"], 1)
            self.assertEqual(rec["coverage"]["first_date_with_rows"], "2026-10-01")
            self.assertEqual(rec["status"], "ok")
            self.assertIn("last_success_at", rec)

    def test_failed_does_not_move_coverage(self):
        with TempDir() as tmp:
            c = Checkpoints(tmp / "c.json")
            m = Manifest(tmp / "manifest.json")
            c.set(P + "2026-10-01_2026-10-01", cp.FAILED, is_final=True)
            rec = m.update_dataset("gsc/ds/S", checkpoints=c)
            self.assertEqual(rec["status"], "failed")
            self.assertNotIn("coverage", rec)
            self.assertEqual(rec["failed_units"], ["2026-10-01_2026-10-01"])

    def test_stopped_and_skipped(self):
        with TempDir() as tmp:
            c = Checkpoints(tmp / "c.json")
            m = Manifest(tmp / "manifest.json")
            m.set_skipped("gsc", [{"scope_id": "https://example.com/", "reason": "子集合"}])
            rec = m.update_dataset("gsc/ds/S", checkpoints=c, stopped_reason="query_in_dimension")
            self.assertEqual(rec["status"], "stopped")
            m2 = Manifest(tmp / "manifest.json")
            self.assertEqual(m2.data["skipped_scopes"]["gsc"][0]["reason"], "子集合")

    def test_overall_status(self):
        base = {k: 0 for k in ("ok", "empty_final", "empty_provisional", "failed", "unsupported", "no_data",
                               "truncated", "provisional", "regression_to_empty")}
        self.assertEqual(overall_status(base), "not_started")
        self.assertEqual(overall_status(dict(base, ok=2, failed=1)), "partial")
        self.assertEqual(overall_status(dict(base, unsupported=1)), "unsupported")


if __name__ == "__main__":
    unittest.main()
