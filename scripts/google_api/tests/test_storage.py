import os
import time
import unittest

from collector.errors import DuplicateKeyError
from collector.storage import (DatasetFiles, SnapshotTable, place_no_overwrite, read_csv, read_raw,
                               write_if_changed, write_raw)

from .fakes import TempDir, d

HEADER = ["date", "scope_id", "page", "clicks", "impressions", "extra_metric", "tz", "is_final", "fetched_at"]
KEYS = ["date", "scope_id", "page"]


def rows(date, *pages, clicks="1"):
    return [{"date": date, "scope_id": "S", "page": p, "clicks": clicks, "impressions": "2"} for p in pages]


class RawTests(unittest.TestCase):
    def test_write_and_read_gzip(self):
        with TempDir() as tmp:
            p = write_raw(tmp / "a" / "x.json.gz", {"k": "值", "n": [1, 2]})
            self.assertEqual(read_raw(p), {"k": "值", "n": [1, 2]})
            self.assertFalse((tmp / "a" / "x.json.gz.partial").exists())

    def test_never_overwrite(self):
        with TempDir() as tmp:
            p = write_raw(tmp / "x.json.gz", {"v": 1})
            with self.assertRaises(FileExistsError):
                write_raw(p, {"v": 2})
            self.assertEqual(read_raw(p), {"v": 1})

    def test_place_no_overwrite_keeps_partial(self):
        with TempDir() as tmp:
            src = tmp / "a.partial"
            dst = tmp / "a"
            src.write_bytes(b"new")
            dst.write_bytes(b"old")
            with self.assertRaises(FileExistsError):
                place_no_overwrite(src, dst)
            self.assertEqual(dst.read_bytes(), b"old")
            self.assertTrue(src.exists())


class DatasetFilesTests(unittest.TestCase):
    def files(self, tmp, layout="daily"):
        return DatasetFiles(tmp, "ds", layout, HEADER, KEYS)

    def test_daily_layout_touches_only_that_day(self):
        with TempDir() as tmp:
            f = self.files(tmp)
            f.apply("S", [d("2026-10-01")], rows("2026-10-01", "/a"))
            f.apply("S", [d("2026-10-02")], rows("2026-10-02", "/b"))
            p1 = f.file_for(d("2026-10-01"))
            m1 = os.path.getmtime(p1)
            time.sleep(0.01)
            f.apply("S", [d("2026-10-02")], rows("2026-10-02", "/c"))
            self.assertEqual(os.path.getmtime(p1), m1)
            _, r2 = read_csv(f.file_for(d("2026-10-02")))
            self.assertEqual([r["page"] for r in r2], ["/c"])

    def test_monthly_replaces_only_unit_dates(self):
        with TempDir() as tmp:
            f = self.files(tmp, "monthly")
            f.apply("S", [d("2026-10-01"), d("2026-10-02")], rows("2026-10-01", "/a") + rows("2026-10-02", "/b"))
            f.apply("S", [d("2026-10-02")], rows("2026-10-02", "/x", clicks="9"))
            _, r = read_csv(f.file_for(d("2026-10-01")))
            self.assertEqual([(x["date"], x["page"], x["clicks"]) for x in r],
                             [("2026-10-01", "/a", "1"), ("2026-10-02", "/x", "9")])

    def test_rerun_does_not_duplicate(self):
        with TempDir() as tmp:
            f = self.files(tmp, "monthly")
            for _ in range(3):
                f.apply("S", [d("2026-10-01")], rows("2026-10-01", "/a", "/b"))
            self.assertEqual(f.stats("S")["row_count"], 2)

    def test_empty_when_no_previous_rows(self):
        with TempDir() as tmp:
            f = self.files(tmp)
            res = f.apply("S", [d("2026-10-01")], [])
            self.assertEqual(res["regression_dates"], [])
            self.assertFalse(f.file_for(d("2026-10-01")).exists())

    def test_regression_to_empty_keeps_old_rows(self):
        with TempDir() as tmp:
            f = self.files(tmp)
            f.apply("S", [d("2026-10-01")], rows("2026-10-01", "/a"))
            res = f.apply("S", [d("2026-10-01")], [])
            self.assertEqual(res["regression_dates"], ["2026-10-01"])
            _, r = read_csv(f.file_for(d("2026-10-01")))
            self.assertEqual(len(r), 1)

    def test_accept_empty_clears(self):
        with TempDir() as tmp:
            f = self.files(tmp)
            f.apply("S", [d("2026-10-01")], rows("2026-10-01", "/a"))
            res = f.apply("S", [d("2026-10-01")], [], accept_empty=True)
            self.assertEqual(res["regression_dates"], [])
            _, r = read_csv(f.file_for(d("2026-10-01")))
            self.assertEqual(r, [])

    def test_other_scope_untouched(self):
        with TempDir() as tmp:
            f = self.files(tmp, "monthly")
            other = [{"date": "2026-10-01", "scope_id": "T", "page": "/z", "clicks": "5"}]
            f.apply("T", [d("2026-10-01")], other)
            f.apply("S", [d("2026-10-01")], rows("2026-10-01", "/a"))
            _, r = read_csv(f.file_for(d("2026-10-01")))
            self.assertEqual(sorted(x["scope_id"] for x in r), ["S", "T"])

    def test_duplicate_key_refused(self):
        with TempDir() as tmp:
            f = self.files(tmp)
            with self.assertRaises(DuplicateKeyError):
                f.apply("S", [d("2026-10-01")], rows("2026-10-01", "/a", "/a"))
            self.assertFalse(f.file_for(d("2026-10-01")).exists())

    def test_fixed_columns_and_bom(self):
        with TempDir() as tmp:
            f = self.files(tmp)
            f.apply("S", [d("2026-10-01")], rows("2026-10-01", "/a"))
            raw = f.file_for(d("2026-10-01")).read_bytes()
            self.assertTrue(raw.startswith(b"\xef\xbb\xbf"))
            header, r = read_csv(f.file_for(d("2026-10-01")))
            self.assertEqual(header, HEADER)
            self.assertEqual(r[0]["extra_metric"], "")

    def test_rows_outside_unit_rejected(self):
        with TempDir() as tmp:
            f = self.files(tmp)
            with self.assertRaises(ValueError):
                f.apply("S", [d("2026-10-01")], rows("2026-10-05", "/a"))

    def test_backup_only_when_changed_and_keeps_three(self):
        with TempDir() as tmp:
            f = self.files(tmp, "monthly")
            f.apply("S", [d("2026-10-01")], rows("2026-10-01", "/a"))
            f.apply("S", [d("2026-10-01")], rows("2026-10-01", "/a"))     # 內容相同 → 不備份
            self.assertFalse(f.backup_dir.exists() and any(f.backup_dir.iterdir()))
            for i in range(5):
                time.sleep(0.002)
                f.apply("S", [d("2026-10-01")], rows("2026-10-01", "/a", clicks=str(10 + i)))
            backups = list(f.backup_dir.glob("*.csv"))
            self.assertEqual(len(backups), 3)


class WriteIfChangedTests(unittest.TestCase):
    def test_unchanged(self):
        with TempDir() as tmp:
            p = tmp / "x.csv"
            self.assertEqual(write_if_changed(p, b"a"), "created")
            self.assertEqual(write_if_changed(p, b"a"), "unchanged")
            self.assertEqual(write_if_changed(p, b"b"), "replaced")


class SnapshotTableTests(unittest.TestCase):
    def test_upsert(self):
        with TempDir() as tmp:
            t = SnapshotTable(tmp / "t.csv", ["k", "v"], ["k"])
            t.upsert([{"k": "a", "v": 1}, {"k": "b", "v": 2}])
            t.upsert([{"k": "a", "v": 3}])
            _, r = read_csv(tmp / "t.csv")
            self.assertEqual({x["k"]: x["v"] for x in r}, {"a": "3", "b": "2"})


if __name__ == "__main__":
    unittest.main()
