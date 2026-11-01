"""引擎：unit 跳過、0 列防護、斷路器、query_in_dimension、截斷完成判斷。"""
import json
import unittest

from collector import checkpoint as cp
from collector import errors as E
from collector.breaker import CircuitBreaker
from collector.engine import Dataset, SourceStop, UnitResult, plan_units, run_units, units_for_mode
from collector.errors import QueryInDimension
from collector.storage import DatasetFiles, read_csv

from .fakes import TempDir, api_error, d, make_ctx

DS = Dataset(source="gsc", name="t_ds", dims=["date", "page"], dim_cols=["page"], metrics=["clicks"],
             chunk="day", layout="daily")


def ok_rows(u, *pages):
    return UnitResult(rows=[{"date": u.start.isoformat(), "page": p, "clicks": "1"} for p in pages], pages=1)


class EngineTests(unittest.TestCase):
    def run_once(self, ctx, fetch, start="2026-10-01", end="2026-10-03", mode="backfill", prov=None, br=None):
        units = plan_units("gsc", DS, "S", start, end)
        return run_units(ctx, "gsc", DS, "S", units, fetch=fetch, breaker=br or CircuitBreaker(3),
                         provisional_from=prov, mode=mode)

    def test_done_units_skipped_and_refetch_forces(self):
        with TempDir() as tmp:
            ctx = make_ctx(tmp)
            calls = []

            def fetch(u):
                calls.append(u.start.isoformat())
                return ok_rows(u, "/a")

            self.run_once(ctx, fetch)
            self.run_once(ctx, fetch)
            self.assertEqual(len(calls), 3)
            self.run_once(ctx, fetch, mode="refetch")
            self.assertEqual(len(calls), 6)

    def test_provisional_units_rerun(self):
        with TempDir() as tmp:
            ctx = make_ctx(tmp)
            calls = []

            def fetch(u):
                calls.append(u.start.isoformat())
                return ok_rows(u, "/a")

            self.run_once(ctx, fetch, prov="2026-10-03")
            self.run_once(ctx, fetch, prov="2026-10-03")
            self.assertEqual(calls, ["2026-10-01", "2026-10-02", "2026-10-03", "2026-10-03"])

    def test_regression_to_empty(self):
        with TempDir() as tmp:
            ctx = make_ctx(tmp)
            self.run_once(ctx, lambda u: ok_rows(u, "/a"), start="2026-10-01", end="2026-10-01")
            self.run_once(ctx, lambda u: UnitResult(rows=[], pages=1), start="2026-10-01", end="2026-10-01",
                          mode="refetch")
            rec = ctx.checkpoints.get("gsc/t_ds/S/2026-10-01_2026-10-01")
            self.assertEqual(rec["status"], cp.REGRESSION)
            files = DatasetFiles(ctx.source_dir("gsc"), DS.name, DS.layout, DS.header, DS.key_fields)
            _, rows = read_csv(files.file_for(d("2026-10-01")))
            self.assertEqual(len(rows), 1)
            log = (tmp / "collection_log.jsonl").read_text(encoding="utf-8")
            self.assertIn("regression_to_empty", log)
            man = ctx.manifest.get("gsc/t_ds/S")
            self.assertEqual(man["units"]["regression_to_empty"], 1)

    def test_failure_does_not_touch_csv(self):
        with TempDir() as tmp:
            ctx = make_ctx(tmp)
            self.run_once(ctx, lambda u: ok_rows(u, "/a"), start="2026-10-01", end="2026-10-01")

            def fail(u):
                raise api_error(E.BAD_REQUEST, 400)

            self.run_once(ctx, fail, start="2026-10-01", end="2026-10-01", mode="refetch")
            files = DatasetFiles(ctx.source_dir("gsc"), DS.name, DS.layout, DS.header, DS.key_fields)
            _, rows = read_csv(files.file_for(d("2026-10-01")))
            self.assertEqual(len(rows), 1)
            self.assertEqual(ctx.checkpoints.get("gsc/t_ds/S/2026-10-01_2026-10-01")["status"], cp.FAILED)

    def test_breaker_stops_source(self):
        with TempDir() as tmp:
            ctx = make_ctx(tmp)
            calls = []

            def fail(u):
                calls.append(1)
                raise api_error(E.TRANSIENT, 503)

            with self.assertRaises(SourceStop):
                self.run_once(ctx, fail, start="2026-10-01", end="2026-10-10")
            self.assertEqual(len(calls), 3)
            self.assertIn("breaker_open", (tmp / "collection_log.jsonl").read_text(encoding="utf-8"))

    def test_daily_quota_stops_source(self):
        with TempDir() as tmp:
            ctx = make_ctx(tmp)

            def fail(u):
                raise api_error(E.QUOTA_DAILY, 403)

            with self.assertRaises(SourceStop):
                self.run_once(ctx, fail)

    def test_query_in_dimension_stops_dataset_without_csv(self):
        with TempDir() as tmp:
            ctx = make_ctx(tmp)
            calls = []

            def fetch(u):
                calls.append(1)
                raise QueryInDimension("t_ds 的 page 維度出現不該有的內容（digits12=2 列）",
                                       hits={"digits12": 2}, dimension="page")

            status, reason = self.run_once(ctx, fetch)
            self.assertEqual(status, "stopped")
            self.assertEqual(len(calls), 1)
            self.assertFalse((ctx.source_dir("gsc") / "csv" / DS.name).exists())
            man = ctx.manifest.get("gsc/t_ds/S")
            self.assertEqual(man["status"], "stopped")
            self.assertEqual(man["guard_hits"], {"digits12": 2})
            self.assertTrue(any("digits12（2 列）" in x and "誤報" in x for x in man["known_limits"]))

    def test_truncated_final_is_done(self):
        with TempDir() as tmp:
            ctx = make_ctx(tmp)
            calls = []

            def fetch(u):
                calls.append(1)
                r = ok_rows(u, "/a")
                r.status = cp.TRUNCATED
                return r

            self.run_once(ctx, fetch, start="2026-10-01", end="2026-10-01")
            self.run_once(ctx, fetch, start="2026-10-01", end="2026-10-01")
            self.assertEqual(len(calls), 1)
            self.run_once(ctx, fetch, start="2026-10-01", end="2026-10-01", mode="refetch")
            self.assertEqual(len(calls), 2)

    def test_unsupported_and_no_data_recorded(self):
        with TempDir() as tmp:
            ctx = make_ctx(tmp)
            self.run_once(ctx, lambda u: UnitResult(rows=[], status=cp.NO_DATA), start="2026-10-01", end="2026-10-01")
            self.assertEqual(ctx.checkpoints.get("gsc/t_ds/S/2026-10-01_2026-10-01")["status"], cp.NO_DATA)

    def test_update_includes_pending_and_window(self):
        with TempDir() as tmp:
            ctx = make_ctx(tmp, end="2026-10-30")
            ctx.checkpoints.set("gsc/t_ds/S/2026-09-01_2026-09-01", cp.FAILED, is_final=True)
            ctx.checkpoints.set("gsc/t_ds/S/2026-10-25_2026-10-25", cp.OK, is_final=True)
            units = units_for_mode(ctx, "gsc", DS, "S", "update", d("2025-07-01"), refetch_from=d("2026-10-21"))
            starts = [u.start.isoformat() for u in units]
            self.assertEqual(starts[0], "2026-09-01")
            self.assertIn("2026-10-21", starts)
            self.assertEqual(starts[-1], "2026-10-30")

    def test_dry_run_counts_without_writing(self):
        with TempDir() as tmp:
            ctx = make_ctx(tmp / "data", dry_run=True)
            self.run_once(ctx, lambda u: self.fail("不應該呼叫 API"))
            self.assertEqual(ctx.planned["gsc/t_ds/S"], 3)
            self.assertFalse((tmp / "data" / "state").exists())

    def test_rows_get_metadata_columns(self):
        with TempDir() as tmp:
            ctx = make_ctx(tmp)
            self.run_once(ctx, lambda u: ok_rows(u, "/a"), start="2026-10-01", end="2026-10-01", prov="2026-10-01")
            files = DatasetFiles(ctx.source_dir("gsc"), DS.name, DS.layout, DS.header, DS.key_fields)
            _, rows = read_csv(files.file_for(d("2026-10-01")))
            self.assertEqual(rows[0]["scope_id"], "S")
            self.assertEqual(rows[0]["is_final"], "false")
            self.assertTrue(rows[0]["fetched_at"])
            for line in (tmp / "collection_log.jsonl").read_text(encoding="utf-8").splitlines():
                json.loads(line)


if __name__ == "__main__":
    unittest.main()
