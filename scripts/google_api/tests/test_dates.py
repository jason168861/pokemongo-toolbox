import datetime as dt
import unittest

from collector import dates as D

from .fakes import d


class DatesTests(unittest.TestCase):
    def test_month_chunks_mid_month_and_year_boundary(self):
        got = D.month_chunks("2025-11-15", "2026-02-10")
        self.assertEqual(got, [(d("2025-11-15"), d("2025-11-30")), (d("2025-12-01"), d("2025-12-31")),
                               (d("2026-01-01"), d("2026-01-31")), (d("2026-02-01"), d("2026-02-10"))])

    def test_month_chunks_leap_year(self):
        got = D.month_chunks("2024-02-01", "2024-03-01")
        self.assertEqual(got[0], (d("2024-02-01"), d("2024-02-29")))

    def test_empty_when_start_after_end(self):
        self.assertEqual(D.month_chunks("2026-02-01", "2026-01-01"), [])

    def test_year_chunks(self):
        self.assertEqual(D.year_chunks("2024-06-01", "2025-02-01"),
                         [(d("2024-06-01"), d("2024-12-31")), (d("2025-01-01"), d("2025-02-01"))])

    def test_day_units(self):
        self.assertEqual(len(D.day_units("2026-10-01", "2026-10-31")), 31)

    def test_split_half(self):
        self.assertEqual(D.split_half("2026-10-01", "2026-10-31"),
                         ((d("2026-10-01"), d("2026-10-16")), (d("2026-10-17"), d("2026-10-31"))))
        self.assertEqual(D.split_half("2026-10-01", "2026-10-02"),
                         ((d("2026-10-01"), d("2026-10-01")), (d("2026-10-02"), d("2026-10-02"))))
        self.assertIsNone(D.split_half("2026-10-01", "2026-10-01"))

    def test_add_months_clamps(self):
        self.assertEqual(D.add_months("2026-03-31", -1), d("2026-02-28"))
        self.assertEqual(D.add_months("2024-03-31", -1), d("2024-02-29"))

    def test_utc_yesterday(self):
        now = dt.datetime(2026, 11, 1, 0, 30, tzinfo=dt.timezone(dt.timedelta(hours=8)))   # = 10/31 16:30 UTC
        self.assertEqual(D.default_end(now), d("2026-10-30"))

    def test_refetch_windows(self):
        cfg = {"gsc_days": 10, "ga4_days": 7, "adsense_min_days": 35}
        end = d("2026-10-30")
        self.assertEqual(D.refetch_start("gsc", end, cfg), d("2026-10-21"))
        self.assertEqual(D.refetch_start("ga4", end, cfg), d("2026-10-24"))
        # 本月＋上月 = 9/1；35 天 = 9/26 → 取較早的 9/1
        self.assertEqual(D.refetch_start("adsense", end, cfg), d("2026-09-01"))
        # 月初時，上月 1 日比 35 天晚 → 取 35 天
        self.assertEqual(D.refetch_start("adsense", d("2026-03-01"), cfg), d("2026-01-26"))

    def test_backfill_floors(self):
        end = d("2026-10-30")
        self.assertEqual(D.backfill_floor("gsc", end), d("2025-07-01"))
        self.assertEqual(D.backfill_floor("adsense", end), d("2023-10-31"))
        self.assertEqual(D.backfill_floor("adsense", end, "2025-01-15"), d("2025-01-15"))
        self.assertEqual(D.backfill_floor("ga4", end), d("2015-08-14"))
        self.assertEqual(D.backfill_floor("ga4", end, "2024-05-01"), d("2024-05-01"))

    def test_ga4_date_format(self):
        self.assertEqual(D.to_date("20261030"), d("2026-10-30"))

    def test_provisional(self):
        cfg = {"gsc_provisional_min_days": 4, "ga4_provisional_days": 3}
        end = d("2026-10-30")
        self.assertEqual(D.provisional_from("gsc", end, cfg), d("2026-10-27"))
        self.assertEqual(D.provisional_from("gsc", end, cfg, "2026-10-25"), d("2026-10-25"))
        self.assertEqual(D.provisional_from("ga4", end, cfg), d("2026-10-28"))
        self.assertEqual(D.provisional_from("adsense", end, cfg), d("2026-09-01"))


if __name__ == "__main__":
    unittest.main()
