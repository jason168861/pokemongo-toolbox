import unittest

from collector import quality as Q
from collector.errors import QueryInDimension


class QualityTests(unittest.TestCase):
    def test_ratio_gap(self):
        self.assertEqual(Q.ratio_gap(100, 70), 0.3)
        self.assertIsNone(Q.ratio_gap(0, 0))          # 除以零 → None，不是 0
        self.assertIsNone(Q.ratio_gap(None, 5))

    def test_ga4_other(self):
        rows = [{"pagePath": "/a", "screenPageViews": "90"}, {"pagePath": "(other)", "screenPageViews": "10"}]
        self.assertEqual(Q.ga4_other_stats(rows, ["pagePath"], "screenPageViews"), (1, 0.1))
        self.assertEqual(Q.ga4_other_stats([], ["pagePath"], "screenPageViews"), (0, None))

    def test_scan_rules(self):
        self.assertEqual(Q.scan_values(["/a", "/b?x=1", "/t/?s=abc", "/u/123456789012"], Q.GA4_PATH_RULES),
                         {"question_mark": 2, "share_id_param": 1, "digits12": 1})
        self.assertEqual(Q.scan_values(["https://x/?tab=a&mon=b", "https://x/?mons=1"], Q.URL_RULES), {})
        self.assertEqual(Q.scan_values(["https://x/?a=1&s=2"], Q.URL_RULES), {"share_id_param": 1})

    def test_guard_message_has_no_values(self):
        with self.assertRaises(QueryInDimension) as cm:
            Q.guard_dimension("ds", "landingPage", ["/t/?s=SECRETSHARE"], Q.GA4_PATH_RULES)
        self.assertNotIn("SECRETSHARE", str(cm.exception))

    def test_home_query(self):
        Q.guard_home_query("h", ["/", "/?tab=cp-checker-app&mon=%E7%9A%AE"])
        for bad in (["/trade-list/?s=1"], ["/?s=1"], ["/x"]):
            with self.assertRaises(QueryInDimension):
                Q.guard_home_query("h", bad)

    def test_filter_rows(self):
        rows = [{"p": "/?tab=a"}, {"p": "/?s=x"}, {"p": "/?m=" + "9" * 13}, {"p": "/?s=" + "9" * 12}]
        kept, dropped = Q.filter_rows(rows, "p", Q.URL_RULES)
        self.assertEqual(kept, [{"p": "/?tab=a"}])
        self.assertEqual(dropped, {"share_id_param": 2, "digits12": 2})

    def test_check_home_paths(self):
        Q.check_home_paths("h", ["/", "/?x=1"])
        with self.assertRaises(QueryInDimension):
            Q.check_home_paths("h", ["/trade-list/?s=1"])

    def test_check_drop_stop_thresholds(self):
        def day(total, dropped):
            return [{"date": "2026-09-01", "total_rows": total, "dropped_rows": dropped}]
        Q.check_drop_stop("h", day(59, 1), 0.01, 20, 3)          # 1.7% 但只有 1 列 → 不停
        Q.check_drop_stop("h", day(59, 2), 0.01, 20, 3)          # 3.4% 但只有 2 列 → 不停
        Q.check_drop_stop("h", day(400, 3), 0.01, 20, 3)         # 3 列但 0.75% → 不停
        for args in (day(100, 3), day(5000, 21)):                # 3%／> 20 列 → 停
            with self.assertRaises(QueryInDimension) as cm:
                Q.check_drop_stop("h", args, 0.01, 20, 3)
            self.assertEqual(list(cm.exception.hits), ["drop_stop"])

    def test_drop_stop_is_per_day_not_diluted_by_month(self):
        """同一個月：某一天 100 列中排除 3 列（3%），整月合計 3／3000 = 0.1%。仍然要停（按日判斷）。"""
        rows, removed = [], []
        for day in range(1, 31):
            date = f"2026-09-{day:02d}"
            for i in range(100):
                r = {"date": date, "screenPageViews": "1", "eventCount": "2", "userEngagementDuration": "3"}
                rows.append(r)
                if day == 8 and i < 3:
                    removed.append(r)
        daily = Q.dropped_daily_stats(rows, removed, ("screenPageViews", "eventCount", "userEngagementDuration"))
        self.assertEqual(daily, [{"date": "2026-09-08", "total_rows": 100, "dropped_rows": 3,
                                  "screenPageViews": 3.0, "eventCount": 6.0, "userEngagementDuration": 9.0}])
        self.assertLess(len(removed) / len(rows), 0.01)            # 整月合計低於 1%
        with self.assertRaises(QueryInDimension) as cm:
            Q.check_drop_stop("h", daily, 0.01, 20, 3)
        self.assertIn("2026-09-08", str(cm.exception))

    def test_drop_stop_20_rows_is_per_day(self):
        """21 列分散在 3 天（每天 7 列、各占 0.7%）→ 不停；同一天 21 列 → 停。"""
        def daily(spec):
            return [{"date": d, "total_rows": t, "dropped_rows": n} for d, t, n in spec]
        Q.check_drop_stop("h", daily([("2026-09-01", 1000, 7), ("2026-09-02", 1000, 7), ("2026-09-03", 1000, 7)]),
                          0.01, 20, 3)
        with self.assertRaises(QueryInDimension):
            Q.check_drop_stop("h", daily([("2026-09-01", 100000, 21)]), 0.01, 20, 3)

    def test_median(self):
        self.assertEqual(Q.median([3, 1, 2]), 2)
        self.assertEqual(Q.median([1, 2, 3, 4]), 2.5)
        self.assertIsNone(Q.median([None]))


if __name__ == "__main__":
    unittest.main()
