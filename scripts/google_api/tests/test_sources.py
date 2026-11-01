"""各來源：用假的 API client 驗證查詢、分頁、截斷、probe、守門。全部使用假值。"""
import json
import unittest

from collector import checkpoint as cp
from collector import errors as E
from collector.engine import SourceStop
from collector.errors import ConfigError, QueryInDimension
from collector.storage import read_csv

from .fakes import FAKE_ACCOUNT, FAKE_API_KEY, FAKE_PROPERTY, FAKE_SITE, FakeService, TempDir, api_error, d, make_ctx


# ------------------------------------------------------------------ AdSense

UNAVAILABLE_MSG = ("No reporting data is available for the requested date range. "
                   "Reporting is not available on data from before the retention window.")


def adsense_handler(rows_for=None, truncate_over_days=None, reject=(), unavailable_before=None, reject_filter=False):
    def handler(path, kw):
        if path == "accounts.list":
            return {"accounts": [{"name": FAKE_ACCOUNT}]}
        if path == "accounts.get":
            return {"name": FAKE_ACCOUNT, "timeZone": {"id": "Asia/Taipei"}, "createTime": "2020-01-01T00:00:00Z"}
        if path == "accounts.reports.generate":
            metrics = kw["metrics"]
            if reject_filter and kw.get("filters"):
                raise api_error(E.BAD_REQUEST, 400, "Invalid filter")
            if any(m in reject for m in metrics):
                raise api_error(E.BAD_REQUEST, 400, "metric not supported")
            s = d(f"{kw['startDate_year']:04d}-{kw['startDate_month']:02d}-{kw['startDate_day']:02d}")
            e = d(f"{kw['endDate_year']:04d}-{kw['endDate_month']:02d}-{kw['endDate_day']:02d}")
            if unavailable_before and s.isoformat() < unavailable_before:
                raise api_error(E.BAD_REQUEST, 400, UNAVAILABLE_MSG)
            days = (e - s).days + 1
            dims = kw["dimensions"]
            headers = [{"name": n, "type": "DIMENSION"} for n in dims] + \
                      [{"name": m, "type": "METRIC_CURRENCY" if m == "ESTIMATED_EARNINGS" else "METRIC_TALLY",
                        **({"currencyCode": "TWD"} if m == "ESTIMATED_EARNINGS" else {})} for m in metrics]
            rows = []
            if rows_for:
                for i in range(days):
                    day = s.fromordinal(s.toordinal() + i).isoformat()
                    for extra in rows_for(day, dims):
                        rows.append({"cells": [{"value": day}] + [{"value": v} for v in extra] +
                                              [{"value": "1"} for _ in metrics]})
            matched = len(rows)
            if truncate_over_days is not None and days > truncate_over_days:
                matched = len(rows) + 1
            return {"headers": headers, "rows": rows, "totalMatchedRows": str(matched)}
        raise AssertionError(path)
    return handler


class AdSenseTests(unittest.TestCase):
    def test_probe_fallback_and_unsupported(self):
        from collector.sources.adsense import CORE_METRICS, DATASETS, AdSenseSource
        with TempDir() as tmp:
            # 假回應要有列：這個測試驗證的是指標退回，不是 0 列（0 列見 supported_empty 的測試）
            svc = FakeService(adsense_handler(rows_for=lambda day, dims: [[]],
                                              reject=("ACTIVE_VIEW_VIEWABILITY",)))
            ctx = make_ctx(tmp, services={"adsense": svc})
            src = AdSenseSource(ctx)
            pr = src.probe(FAKE_ACCOUNT, DATASETS[0])
            self.assertEqual(pr["status"], "supported")
            self.assertEqual(pr["metrics"], CORE_METRICS)
            self.assertEqual(pr["probe_rows"], 7)
            svc2 = FakeService(adsense_handler(reject=("ESTIMATED_EARNINGS",)))
            ctx2 = make_ctx(tmp / "b", services={"adsense": svc2})
            pr2 = AdSenseSource(ctx2).probe(FAKE_ACCOUNT, DATASETS[0])
            self.assertEqual(pr2["status"], "unsupported")
            # 400 不重試：每組指標只呼叫一次
            self.assertEqual(len([c for c in svc2.calls if c[0] == "accounts.reports.generate"]), 3)

    def test_probe_records_counts_not_values(self):
        from collector.sources.adsense import DATASETS, AdSenseSource
        ds = [x for x in DATASETS if x.name == "adsense_date_country"][0]
        with TempDir() as tmp:
            svc = FakeService(adsense_handler(rows_for=lambda day, dims: [["QQSAMPLE1"], ["QQSAMPLE2"]]))
            ctx = make_ctx(tmp, services={"adsense": svc})
            pr = AdSenseSource(ctx).probe(FAKE_ACCOUNT, ds)
            self.assertEqual(pr["status"], "supported")
            self.assertEqual(pr["probe_rows"], 14)
            self.assertEqual(pr["dimension_value_counts"], {"country_code": 2})
            self.assertNotIn("QQSAMPLE", json.dumps(ctx.read_state("probe.json", {}), ensure_ascii=False))

    def test_probe_zero_rows_is_supported_empty_and_still_backfilled(self):
        """7 天試查 0 列不代表整段歷史沒有資料，AdSense 仍會回補。"""
        from collector.sources.adsense import AdSenseSource
        with TempDir() as tmp:
            svc = FakeService(adsense_handler(rows_for=None))
            ctx = make_ctx(tmp, services={"adsense": svc}, end="2026-10-03")
            AdSenseSource(ctx).run("backfill", start="2026-10-01", datasets={"adsense_date_country"})
            pr = ctx.read_state("probe.json", {})[f"adsense/adsense_date_country/{FAKE_ACCOUNT}"]
            self.assertEqual(pr["status"], "supported_empty")
            self.assertEqual(pr["probe_rows"], 0)
            reports = [c for c in svc.calls if c[0] == "accounts.reports.generate"]
            self.assertEqual(len(reports), 2)       # probe 1 次 + 回補 1 次

    def test_pageurl_unsupported_written_to_known_limits(self):
        from collector.sources.adsense import AdSenseSource
        with TempDir() as tmp:
            svc = FakeService(adsense_handler(reject=("ESTIMATED_EARNINGS",)))
            ctx = make_ctx(tmp, services={"adsense": svc})
            AdSenseSource(ctx).run("backfill", datasets={"adsense_date_pageurl"})
            rec = ctx.manifest.get(f"adsense/adsense_date_pageurl/{FAKE_ACCOUNT}")
            self.assertTrue(any("PAGE_URL" in x for x in rec["known_limits"]))

    def test_truncation_splits_to_single_day(self):
        from collector.engine import Unit
        from collector.sources.adsense import DATASETS, FULL_METRICS, AdSenseSource
        with TempDir() as tmp:
            svc = FakeService(adsense_handler(rows_for=lambda day, dims: [["TW"]], truncate_over_days=2))
            ctx = make_ctx(tmp, services={"adsense": svc})
            src = AdSenseSource(ctx)
            ds = [x for x in DATASETS if x.name == "adsense_date_country"][0]
            res, info = src.fetch_unit(FAKE_ACCOUNT, ds, FULL_METRICS, Unit("adsense", ds.name, FAKE_ACCOUNT,
                                                                             d("2026-10-01"), d("2026-10-08")))
            self.assertEqual(res.status, cp.OK)
            self.assertEqual(len(res.rows), 8)
            svc3 = FakeService(adsense_handler(rows_for=lambda day, dims: [["TW"]], truncate_over_days=0))
            ctx3 = make_ctx(tmp / "c", services={"adsense": svc3})
            res3, _ = AdSenseSource(ctx3).fetch_unit(FAKE_ACCOUNT, ds, FULL_METRICS,
                                                     Unit("adsense", ds.name, FAKE_ACCOUNT, d("2026-10-01"), d("2026-10-02")))
            self.assertEqual(res3.status, cp.TRUNCATED)
            self.assertEqual(res3.info["truncated_dates"], ["2026-10-01", "2026-10-02"])

    def test_retention_unavailable(self):
        """A：PAGE_URL 對較早月份回 400「No reporting data is available」→ unavailable（已定案、不算失敗、不觸發斷路器）。"""
        from collector.sources.adsense import AdSenseSource, is_retention_unavailable
        with TempDir() as tmp:
            svc = FakeService(adsense_handler(rows_for=lambda day, dims: [["https://example.com/x"]],
                                              unavailable_before="2026-09-01"))
            ctx = make_ctx(tmp, services={"adsense": svc}, end="2026-10-30")
            AdSenseSource(ctx).run("backfill", start="2026-03-01", datasets={"adsense_date_pageurl"})
            key = f"adsense/adsense_date_pageurl/{FAKE_ACCOUNT}"
            units = ctx.checkpoints.with_prefix(key + "/")
            st = {uid.rsplit("/", 1)[-1][:7]: rec["status"] for uid, rec in units.items()}
            self.assertEqual(st["2026-03"], cp.UNAVAILABLE)          # 6 個月都 unavailable，斷路器沒有開
            self.assertEqual(st["2026-08"], cp.UNAVAILABLE)
            self.assertEqual(st["2026-09"], cp.OK)
            self.assertTrue(all(r["is_final"] for r in units.values() if r["status"] == cp.UNAVAILABLE))
            rec = ctx.manifest.get(key)
            self.assertEqual(rec["units"]["unavailable"], 6)
            self.assertEqual(rec["units"]["failed"], 0)
            self.assertEqual(rec["earliest_available_month"], "2026-09")
            self.assertEqual(rec["first_unavailable_month"], "2026-03")
            self.assertEqual(rec["latest_unavailable_month"], "2026-08")
            self.assertIn("【推論】", rec["unavailable_boundary_note"])
            note = [x for x in rec["known_limits"] if "No reporting data is available" in x]
            self.assertTrue(note)
            self.assertIn("截至", note[0])           # 不寫成永久結論
            self.assertIn("不是 API 保證", note[0])
            log = (tmp / "collection_log.jsonl").read_text(encoding="utf-8")
            self.assertNotIn("unit_failed", log)
            # 再跑 backfill：unavailable 的 unit 不重抓
            n_before = len([c for c in svc.calls if c[0] == "accounts.reports.generate"])
            AdSenseSource(ctx).run("backfill", start="2026-03-01", datasets={"adsense_date_pageurl"})
            gen = [c for c in svc.calls if c[0] == "accounts.reports.generate"][n_before:]
            starts = {f"{kw['startDate_year']:04d}-{kw['startDate_month']:02d}" for _, kw in gen}
            self.assertFalse(starts & {"2026-03", "2026-04", "2026-05", "2026-06", "2026-07", "2026-08"})
            # refetch 會重試
            n_before = len([c for c in svc.calls if c[0] == "accounts.reports.generate"])
            AdSenseSource(ctx).run("refetch", start="2026-03-01", end="2026-03-31", datasets={"adsense_date_pageurl"})
            self.assertGreater(len([c for c in svc.calls if c[0] == "accounts.reports.generate"]), n_before)
        self.assertFalse(is_retention_unavailable(api_error(E.BAD_REQUEST, 400, "Invalid metric")))
        self.assertFalse(is_retention_unavailable(api_error(E.TRANSIENT, 503, UNAVAILABLE_MSG)))
        self.assertFalse(is_retention_unavailable(api_error(E.BAD_REQUEST, 400, UNAVAILABLE_MSG.lower())))

    def test_unavailable_only_for_pageurl(self):
        """其他資料集即使收到同樣的 400，也照原本規則記 failed。"""
        from collector.sources.adsense import AdSenseSource
        with TempDir() as tmp:
            svc = FakeService(adsense_handler(rows_for=lambda day, dims: [["X"]], unavailable_before="2026-09-01"))
            ctx = make_ctx(tmp, services={"adsense": svc}, end="2026-10-30")
            AdSenseSource(ctx).run("backfill", start="2026-07-01", datasets={"adsense_date_country"})
            units = ctx.checkpoints.with_prefix(f"adsense/adsense_date_country/{FAKE_ACCOUNT}/")
            st = {uid.rsplit("/", 1)[-1][:7]: rec["status"] for uid, rec in units.items()}
            self.assertEqual(st["2026-07"], cp.FAILED)
            self.assertEqual(st["2026-08"], cp.FAILED)
            self.assertEqual(st["2026-09"], cp.OK)

    def test_recent_unavailable_month_is_refetched_on_update(self):
        """本月、上月即使是 unavailable 也不算定案，update 時照常重抓（邊界會移動）。"""
        from collector.sources.adsense import AdSenseSource
        with TempDir() as tmp:
            svc = FakeService(adsense_handler(rows_for=lambda day, dims: [["https://example.com/x"]],
                                              unavailable_before="2026-10-15"))
            ctx = make_ctx(tmp, services={"adsense": svc}, end="2026-10-30")
            AdSenseSource(ctx).run("backfill", start="2026-10-01", datasets={"adsense_date_pageurl"})
            rec = ctx.checkpoints.get(f"adsense/adsense_date_pageurl/{FAKE_ACCOUNT}/2026-10-01_2026-10-30")
            self.assertEqual(rec["status"], cp.UNAVAILABLE)
            self.assertFalse(rec["is_final"])
            n = len([c for c in svc.calls if c[0] == "accounts.reports.generate"])
            AdSenseSource(ctx).run("update", datasets={"adsense_date_pageurl"})
            self.assertGreater(len([c for c in svc.calls if c[0] == "accounts.reports.generate"]), n)

    def test_multisite_known_limits_from_domain_data(self):
        """帳戶底下多個網站：網域與期間取自 adsense_date_domain 的資料，寫進帳戶層級資料集的 known_limits。"""
        from collector.sources.adsense import MULTISITE_PREFIX, AdSenseSource

        def rows_for(day, dims):
            if dims == ["DATE", "DOMAIN_NAME"]:
                return [["old.example"]] if day <= "2026-09-15" else [["new.example"]]
            if dims == ["DATE"]:
                return [[]]
            return [["X"]]

        with TempDir() as tmp:
            svc = FakeService(adsense_handler(rows_for=rows_for))
            ctx = make_ctx(tmp, services={"adsense": svc}, end="2026-10-03",
                           settings_override={"adsense": {"site_domain": "new.example"}})
            src = AdSenseSource(ctx)
            src.run("backfill", start="2026-09-01",
                    datasets={"adsense_date_domain", "adsense_date_country", "adsense_date_country_site",
                              "adsense_date_urlchannel", "adsense_date_pageurl"})
            country = ctx.manifest.get(f"adsense/adsense_date_country/{FAKE_ACCOUNT}")
            notes = [x for x in country["known_limits"] if x.startswith(MULTISITE_PREFIX)]
            self.assertEqual(len(notes), 1)
            self.assertIn("old.example 2026-09-01～2026-09-15", notes[0])
            self.assertIn("new.example 2026-09-16～2026-10-03", notes[0])
            self.assertIn("2026-09-16 前含其他網站", notes[0])          # 本站第一個有資料的日期，取自資料
            self.assertIn("分析本站請用 adsense_date_country_site 版本", notes[0])
            self.assertEqual([p["domain"] for p in country["account_domains"]], ["new.example", "old.example"])
            # 沒有 _site 版本的帳戶層級資料集：指向 adsense_date_domain 的 domain_name
            urlch = ctx.manifest.get(f"adsense/adsense_date_urlchannel/{FAKE_ACCOUNT}")
            unotes = [x for x in urlch["known_limits"] if x.startswith(MULTISITE_PREFIX)]
            self.assertEqual(len(unotes), 1)
            self.assertIn("domain_name", unotes[0])
            # 本身能區分網域的資料集、以及 _site 版本，都不加「帳戶層級」說明
            for name in ("adsense_date_domain", "adsense_date_pageurl", "adsense_date_country_site"):
                rec = ctx.manifest.get(f"adsense/{name}/{FAKE_ACCOUNT}")
                self.assertFalse(any(str(x).startswith(MULTISITE_PREFIX) for x in rec.get("known_limits") or []), name)
            # 重跑不會重複加
            src.run("update", datasets={"adsense_date_country"})
            country = ctx.manifest.get(f"adsense/adsense_date_country/{FAKE_ACCOUNT}")
            self.assertEqual(len([x for x in country["known_limits"] if x.startswith(MULTISITE_PREFIX)]), 1)

    def test_site_datasets_naming(self):
        from collector.datadoc import DATA_README
        from collector.sources.adsense import DATASETS, SITE_BASES
        names = [ds.name for ds in DATASETS]
        for base in SITE_BASES:
            self.assertIn(base, names)                        # 帳戶層級版本保留
            self.assertIn(base + "_site", names)
            site = [ds for ds in DATASETS if ds.name == base + "_site"][0]
            self.assertTrue(site.options.get("site_filter"))
        for name in ("adsense_date_urlchannel_site", "adsense_date_pageurl_site", "adsense_date_domain_site"):
            self.assertNotIn(name, names)
        self.assertIn("adsense_date_site", DATA_README)
        self.assertIn("site_method", DATA_README)

    def test_site_only_crosstab_datasets(self):
        """兩個只做本站版本的交叉資料集：維度正確、帶 filter、沒有帳戶層級版本、不加帳戶層級說明。"""
        from collector.sources.adsense import DATASETS, MULTISITE_PREFIX, AdSenseSource
        by = {ds.name: ds for ds in DATASETS}
        expect = {"adsense_date_adformat_placement_site": ["DATE", "AD_FORMAT_CODE", "AD_PLACEMENT_CODE"],
                  "adsense_date_country_platform_site": ["DATE", "COUNTRY_CODE", "PLATFORM_TYPE_CODE"]}
        for name, dims in expect.items():
            self.assertIn(name, by)
            self.assertEqual(by[name].dims, dims)
            self.assertTrue(by[name].options.get("site_filter"))
            self.assertNotIn(name[:-len("_site")], by)              # 沒有帳戶層級版本
            self.assertEqual(by[name].metrics, by["adsense_date_site"].metrics)
        with TempDir() as tmp:
            svc = FakeService(adsense_handler(rows_for=lambda day, dims: [["INTERSTITIAL", "AUTO"]]
                                              if "AD_FORMAT_CODE" in dims else [["TW", "DESKTOP"]]))
            ctx = make_ctx(tmp, services={"adsense": svc}, end="2026-10-03",
                           settings_override={"adsense": {"site_domain": "example.com"}})
            AdSenseSource(ctx).run("backfill", start="2026-10-01", datasets=set(expect))
            gens = [kw for path, kw in svc.calls if path == "accounts.reports.generate"]
            self.assertTrue(gens)
            for kw in gens:
                self.assertEqual(kw["filters"], ["DOMAIN_NAME==example.com"])
                self.assertIn(kw["dimensions"], list(expect.values()))
            for name in expect:
                rec = ctx.manifest.get(f"adsense/{name}/{FAKE_ACCOUNT}")
                self.assertEqual(rec["site_method"], "filter")
                self.assertTrue(any("沒有對應的帳戶層級版本" in x for x in rec["known_limits"]))
                self.assertFalse(any(str(x).startswith(MULTISITE_PREFIX) for x in rec["known_limits"]))
                _, rows = read_csv(ctx.source_dir("adsense") / "csv" / name / "2026-10.csv")
                self.assertEqual(len(rows), 3)
            header, rows = read_csv(ctx.source_dir("adsense") / "csv" / "adsense_date_adformat_placement_site" / "2026-10.csv")
            self.assertEqual((rows[0]["ad_format_code"], rows[0]["ad_placement_code"]), ("INTERSTITIAL", "AUTO"))

    def test_site_dataset_sends_domain_filter(self):
        """*_site 帶 filters=DOMAIN_NAME==<adsense.site_domain>，維度不變；manifest 註明 site_method=filter。"""
        from collector.sources.adsense import MULTISITE_PREFIX, AdSenseSource
        with TempDir() as tmp:
            svc = FakeService(adsense_handler(rows_for=lambda day, dims: [[]]))
            ctx = make_ctx(tmp, services={"adsense": svc}, end="2026-10-03",
                           settings_override={"adsense": {"site_domain": "example.com"}})
            AdSenseSource(ctx).run("backfill", start="2026-10-01", datasets={"adsense_date_site"})
            gens = [kw for path, kw in svc.calls if path == "accounts.reports.generate"]
            self.assertTrue(gens)
            for kw in gens:
                self.assertEqual(kw["filters"], ["DOMAIN_NAME==example.com"])
                self.assertEqual(kw["dimensions"], ["DATE"])
            rec = ctx.manifest.get(f"adsense/adsense_date_site/{FAKE_ACCOUNT}")
            self.assertEqual(rec["site_method"], "filter")
            self.assertEqual(rec["site_domain"], "example.com")
            self.assertTrue(any("只含 example.com" in x and "filters=DOMAIN_NAME==example.com" in x
                                for x in rec["known_limits"]))
            self.assertFalse(any(str(x).startswith(MULTISITE_PREFIX) for x in rec["known_limits"]))
            _, rows = read_csv(ctx.source_dir("adsense") / "csv" / "adsense_date_site" / "2026-10.csv")
            self.assertEqual(len(rows), 3)
            # 帳戶層級版本不帶 filter
            svc2 = FakeService(adsense_handler(rows_for=lambda day, dims: [[]]))
            ctx2 = make_ctx(tmp / "b", services={"adsense": svc2}, end="2026-10-03")
            AdSenseSource(ctx2).run("backfill", start="2026-10-01", datasets={"adsense_date"})
            self.assertTrue(all("filters" not in kw for p, kw in svc2.calls if p == "accounts.reports.generate"))

    def test_site_filter_rejected_falls_back_to_dimension(self):
        """API 不接受 filter → 退回「維度加 DOMAIN_NAME、下載後篩選」；manifest 註明 site_method=dimension。"""
        from collector.sources.adsense import AdSenseSource

        def rows_for(day, dims):
            if dims == ["DATE", "COUNTRY_CODE", "DOMAIN_NAME"]:
                return [["TW", "example.com"], ["JP", "example.com"], ["TW", "other.example"]]
            return [["X"]]

        with TempDir() as tmp:
            svc = FakeService(adsense_handler(rows_for=rows_for, reject_filter=True))
            ctx = make_ctx(tmp, services={"adsense": svc}, end="2026-10-03",
                           settings_override={"adsense": {"site_domain": "example.com"}})
            AdSenseSource(ctx).run("backfill", start="2026-10-01", datasets={"adsense_date_country_site"})
            pr = ctx.read_state("probe.json", {})[f"adsense/adsense_date_country_site/{FAKE_ACCOUNT}"]
            self.assertEqual(pr["site_mode"], "dimension")
            self.assertTrue(pr["filter_rejected"])
            gens = [kw for path, kw in svc.calls if path == "accounts.reports.generate"]
            unit_calls = [kw for kw in gens if not kw.get("filters")]
            self.assertTrue(unit_calls)
            self.assertTrue(all(kw["dimensions"] == ["DATE", "COUNTRY_CODE", "DOMAIN_NAME"] for kw in unit_calls))
            rec = ctx.manifest.get(f"adsense/adsense_date_country_site/{FAKE_ACCOUNT}")
            self.assertEqual(rec["site_method"], "dimension")
            self.assertTrue(any("改用退路" in x for x in rec["known_limits"]))
            header, rows = read_csv(ctx.source_dir("adsense") / "csv" / "adsense_date_country_site" / "2026-10.csv")
            self.assertNotIn("domain_name", header)                # CSV 欄位與帳戶層級版本相同
            self.assertEqual(len(rows), 6)                          # 3 天 × 本站 2 列，other.example 被濾掉
            self.assertEqual(sorted({r["country_code"] for r in rows}), ["JP", "TW"])

    def test_truncation_manifest_consistency(self):
        """c：截斷記在父 unit；manifest 的 units.truncated 與 truncated_dates 必須一致。"""
        from collector.sources.adsense import AdSenseSource
        with TempDir() as tmp:
            svc = FakeService(adsense_handler(rows_for=lambda day, dims: [[]] if dims == ["DATE"] else [["TW"]],
                                              truncate_over_days=0))
            ctx = make_ctx(tmp, services={"adsense": svc}, end="2026-10-03")
            AdSenseSource(ctx).run("backfill", start="2026-10-01", datasets={"adsense_date_country"})
            key = f"adsense/adsense_date_country/{FAKE_ACCOUNT}"
            rec = ctx.manifest.get(key)
            self.assertEqual(rec["units"]["truncated"], 1)
            self.assertEqual(rec["truncated_dates"], ["2026-10-01", "2026-10-02", "2026-10-03"])
            # 每個 truncated unit 都有 truncated_dates，而且日期都落在該 unit 範圍內；彙總與 manifest 相同
            union = set()
            for uid, cprec in ctx.checkpoints.with_prefix(key + "/").items():
                if cprec["status"] == cp.TRUNCATED:
                    a, b = uid.rsplit("/", 1)[-1].split("_")
                    self.assertTrue(cprec.get("truncated_dates"))
                    self.assertTrue(all(a <= x <= b for x in cprec["truncated_dates"]))
                    union.update(cprec["truncated_dates"])
            self.assertEqual(sorted(union), rec["truncated_dates"])

    def test_pageurl_guard(self):
        from collector.engine import Unit
        from collector.sources.adsense import DATASETS, FULL_METRICS, AdSenseSource
        ds = [x for x in DATASETS if x.name == "adsense_date_pageurl"][0]
        with TempDir() as tmp:
            svc = FakeService(adsense_handler(rows_for=lambda day, dims: [["https://example.com/?tab=x&mon=y"]]))
            ctx = make_ctx(tmp, services={"adsense": svc})
            res, _ = AdSenseSource(ctx).fetch_unit(FAKE_ACCOUNT, ds, FULL_METRICS,
                                                   Unit("adsense", ds.name, FAKE_ACCOUNT, d("2026-10-01"), d("2026-10-01")))
            self.assertEqual(len(res.rows), 1)        # ?tab= / ?mon= 是正常的
            svc2 = FakeService(adsense_handler(rows_for=lambda day, dims: [["https://example.com/trade-list/?s=abc"]]))
            ctx2 = make_ctx(tmp / "b", services={"adsense": svc2})
            with self.assertRaises(QueryInDimension) as cm:
                AdSenseSource(ctx2).fetch_unit(FAKE_ACCOUNT, ds, FULL_METRICS,
                                               Unit("adsense", ds.name, FAKE_ACCOUNT, d("2026-10-01"), d("2026-10-01")))
            self.assertNotIn("abc", str(cm.exception))

    def test_backfill_writes_currency_and_tz(self):
        from collector.sources.adsense import AdSenseSource
        with TempDir() as tmp:
            svc = FakeService(adsense_handler(rows_for=lambda day, dims: [[]] if dims == ["DATE"] else [["X"]]))
            ctx = make_ctx(tmp, services={"adsense": svc}, end="2026-10-03")
            AdSenseSource(ctx).run("backfill", start="2026-10-01", datasets={"adsense_date"})
            _, rows = read_csv(ctx.source_dir("adsense") / "csv" / "adsense_date" / "2026-10.csv")
            self.assertEqual(len(rows), 3)
            self.assertEqual(rows[0]["currency"], "TWD")
            self.assertEqual(rows[0]["tz"], "Asia/Taipei")
            self.assertEqual(rows[0]["is_final"], "false")      # 本月＋上月是暫定


# ------------------------------------------------------------------ GSC

def gsc_handler(rows_per_day=1, unsupported_types=(), empty_types=(), page_value="https://example.com/a",
                sites=None, zero_types=(), active_from=None):
    def handler(path, kw):
        if path == "sites.list":
            return {"siteEntry": sites or [{"siteUrl": "https://example.com/", "permissionLevel": "siteOwner"},
                                           {"siteUrl": FAKE_SITE, "permissionLevel": "siteOwner"}]}
        if path == "searchanalytics.query":
            b = kw["body"]
            if b["type"] in unsupported_types:
                raise api_error(E.BAD_REQUEST, 400)
            if b["type"] in empty_types:
                return {"rows": []}
            s, e = d(b["startDate"]), d(b["endDate"])
            out = []
            n = (e - s).days + 1
            for i in range(n):
                day = s.fromordinal(s.toordinal() + i).isoformat()
                for j in range(rows_per_day):
                    keys = [day]
                    for dim in b["dimensions"][1:]:
                        keys.append(page_value if dim == "page" else f"{dim}-{j}")
                    zero = b["type"] in zero_types or (active_from is not None and day < active_from)
                    out.append({"keys": keys, "clicks": 0 if zero else 1, "impressions": 0 if zero else 10,
                                "ctr": 0 if zero else 0.1, "position": 0 if zero else 3})
            start = b.get("startRow", 0)
            page = out[start:start + b["rowLimit"]]
            return {"rows": page, "responseAggregationType": "byPage" if "page" in b["dimensions"] else "byProperty",
                    "metadata": {"firstIncompleteDate": "2026-10-29"}}
        raise AssertionError(path)
    return handler


GSC_EXAMPLE = {"gsc": {"site_domain": "example.com"}}


class GscTests(unittest.TestCase):
    def test_prefers_sc_domain_and_records_skipped(self):
        from collector.sources.gsc import GscSource
        with TempDir() as tmp:
            ctx = make_ctx(tmp, services={"searchconsole": FakeService(gsc_handler())}, settings_override=GSC_EXAMPLE)
            src = GscSource(ctx)
            self.assertEqual(src.select_sites(src.discover()), [FAKE_SITE])
            skipped = ctx.manifest.data["skipped_scopes"]["gsc"]
            self.assertEqual(skipped[0]["scope_id"], "https://example.com/")
            self.assertIn("重複", skipped[0]["reason"])

    def test_other_domains_never_selected_regardless_of_order(self):
        """API 回傳順序沒有保證：其他網域（例如私人部落格）排在最前面也不能被選到。"""
        from collector.sources.gsc import GscSource
        sites = [
            {"siteUrl": "sc-domain:someone.blogspot.example", "permissionLevel": "siteOwner"},
            {"siteUrl": "https://a.blogspot.example/", "permissionLevel": "siteOwner"},
            {"siteUrl": "https://someone.github.example/pokemongo-toolbox/", "permissionLevel": "siteOwner"},
            {"siteUrl": "https://example.com/", "permissionLevel": "siteOwner"},
            {"siteUrl": FAKE_SITE, "permissionLevel": "siteOwner"},
            {"siteUrl": "https://notexample.com/", "permissionLevel": "siteOwner"},
        ]
        with TempDir() as tmp:
            ctx = make_ctx(tmp, services={"searchconsole": FakeService(gsc_handler(sites=sites))},
                           settings_override=GSC_EXAMPLE)
            src = GscSource(ctx)
            self.assertEqual(src.select_sites(src.discover()), [FAKE_SITE])
            skipped = {s["scope_id"]: s for s in ctx.manifest.data["skipped_scopes"]["gsc"]}
            for sid in ("sc-domain:someone.blogspot.example", "https://a.blogspot.example/",
                        "https://notexample.com/", "https://someone.github.example/pokemongo-toolbox/"):
                self.assertEqual(skipped[sid]["reason"], "不是 example.com")
            self.assertEqual(skipped["https://someone.github.example/pokemongo-toolbox/"]["note"], "舊網域")
            self.assertTrue(any("舊網域歷史" in x and "同意" in x for x in src.extra_limits))
            # 不帶 sc-domain 時，選該網域的 URL-prefix，不會退回其他網域
            ctx2 = make_ctx(tmp / "b", services={"searchconsole": FakeService(
                gsc_handler(sites=[s for s in sites if s["siteUrl"] != FAKE_SITE]))}, settings_override=GSC_EXAMPLE)
            src2 = GscSource(ctx2)
            self.assertEqual(src2.select_sites(src2.discover()), ["https://example.com/"])

    def test_no_matching_site_stops(self):
        from collector.sources.gsc import GscSource
        sites = [{"siteUrl": "sc-domain:someone.blogspot.example", "permissionLevel": "siteOwner"}]
        with TempDir() as tmp:
            ctx = make_ctx(tmp, services={"searchconsole": FakeService(gsc_handler(sites=sites))},
                           settings_override=GSC_EXAMPLE)
            src = GscSource(ctx)
            with self.assertRaises(SourceStop):
                src.select_sites(src.discover())
            self.assertEqual(ctx.manifest.data["skipped_scopes"]["gsc"][0]["reason"], "不是 example.com")

    def test_default_domain_is_pogokit(self):
        from collector.settings import load_settings
        from collector.sources.gsc import site_matches
        self.assertEqual(load_settings()["gsc"]["site_domain"], "pogokit.com")
        self.assertTrue(site_matches("sc-domain:pogokit.com", "pogokit.com"))
        self.assertTrue(site_matches("https://www.pogokit.com/", "pogokit.com"))
        self.assertFalse(site_matches("https://pogokit.com.evil.example/", "pogokit.com"))
        self.assertFalse(site_matches("sc-domain:notpogokit.com", "pogokit.com"))

    def test_type_probe(self):
        from collector.sources.gsc import GscSource
        with TempDir() as tmp:
            ctx = make_ctx(tmp, services={"searchconsole": FakeService(
                gsc_handler(unsupported_types=("news",), empty_types=("video",)))})
            src = GscSource(ctx)
            self.assertEqual(src.type_probe(FAKE_SITE, "news", d("2026-10-01"), d("2026-10-02"))["status"], "unsupported")
            self.assertEqual(src.type_probe(FAKE_SITE, "video", d("2026-10-01"), d("2026-10-02"))["status"], "no_data")
            self.assertEqual(src.type_probe(FAKE_SITE, "web", d("2026-10-01"), d("2026-10-02"))["status"], "supported")

    def test_type_probe_rows_but_zero_impressions_is_no_data(self):
        """API 對沒有資料的搜尋類型也可能逐日回列，但 clicks/impressions 全是 0 → 要判成 no_data。"""
        from collector.sources.gsc import GscSource
        with TempDir() as tmp:
            ctx = make_ctx(tmp, services={"searchconsole": FakeService(gsc_handler(zero_types=("video",)))})
            pr = GscSource(ctx).type_probe(FAKE_SITE, "video", d("2026-08-01"), d("2026-10-30"))
            self.assertEqual(pr["status"], "no_data")
            self.assertEqual(pr["rows_returned"], 91)
            self.assertEqual(pr["impressions"], 0)
            self.assertIn("impressions 總和為 0", pr["reason"])

    def test_type_probe_first_date_uses_first_impression(self):
        from collector.sources.gsc import GscSource
        with TempDir() as tmp:
            ctx = make_ctx(tmp, services={"searchconsole": FakeService(gsc_handler(active_from="2026-08-02"))})
            pr = GscSource(ctx).type_probe(FAKE_SITE, "web", d("2025-07-01"), d("2026-10-30"))
            self.assertEqual(pr["status"], "supported")
            self.assertEqual(pr["first_date"], "2026-08-02")

    def test_backfill_starts_at_first_impression_date(self):
        """回補起點用 probe 的 first_date，不是固定 16 個月；range 的 date 資料集也一樣。"""
        from collector.sources.gsc import GscSource
        with TempDir() as tmp:
            svc = FakeService(gsc_handler(active_from="2026-10-28",
                                          empty_types=("image", "video", "news", "discover", "googleNews")))
            ctx = make_ctx(tmp, services={"searchconsole": svc}, end="2026-10-30", settings_override=GSC_EXAMPLE)
            GscSource(ctx).run("backfill")
            web = [kw["body"] for path, kw in svc.calls
                   if path == "searchanalytics.query" and kw["body"]["type"] == "web"]
            probe, rest = web[0], web[1:]
            self.assertEqual(probe["startDate"], "2025-07-01")             # type probe 查整段
            self.assertTrue(rest)
            self.assertTrue(all(b["startDate"] >= "2026-10-28" for b in rest))

    def test_legacy_probe_record_is_reprobed(self):
        """舊版紀錄（只看有沒有列、沒有 impressions 欄位）在 backfill 時會重新 probe。"""
        from collector.sources import probe_set
        from collector.sources.gsc import GscSource
        with TempDir() as tmp:
            svc = FakeService(gsc_handler(zero_types=("video",),
                                          empty_types=("web", "image", "news", "discover", "googleNews")))
            ctx = make_ctx(tmp, services={"searchconsole": svc}, end="2026-10-30", settings_override=GSC_EXAMPLE)
            probe_set(ctx, f"gsc/type/video/{FAKE_SITE}", status="supported", first_date="2025-07-01")
            GscSource(ctx).run("backfill")
            pr = ctx.read_state("probe.json", {})[f"gsc/type/video/{FAKE_SITE}"]
            self.assertEqual(pr["status"], "no_data")
            video = [kw for path, kw in svc.calls if path == "searchanalytics.query" and kw["body"]["type"] == "video"]
            self.assertEqual(len(video), 1)

    def test_zero_impression_types_not_backfilled_and_recorded(self):
        from collector.sources.gsc import GscSource
        zero = ("video", "news", "discover", "googleNews")
        with TempDir() as tmp:
            svc = FakeService(gsc_handler(zero_types=zero, empty_types=("image",)))
            ctx = make_ctx(tmp, services={"searchconsole": svc}, end="2026-10-30", settings_override=GSC_EXAMPLE)
            GscSource(ctx).run("backfill", start="2026-10-29")
            types_queried = [kw["body"]["type"] for path, kw in svc.calls if path == "searchanalytics.query"]
            for t in zero + ("image",):
                self.assertEqual(types_queried.count(t), 1, t)      # 只有 type probe 那 1 次
            self.assertGreater(types_queried.count("web"), 1)
            for t in zero:
                rec = ctx.manifest.get(f"gsc/gsc_{t}_date/{FAKE_SITE}")
                self.assertEqual(rec["status"], "no_data")
                self.assertTrue(any("impressions 為 0" in x for x in rec["known_limits"]))
            # update 時會再確認一次（每種 1 次請求），仍是 0 就繼續跳過
            svc.calls.clear()
            GscSource(ctx).run("update")
            types_queried = [kw["body"]["type"] for path, kw in svc.calls if path == "searchanalytics.query"]
            for t in zero:
                self.assertEqual(types_queried.count(t), 1, t)

    def test_pagination(self):
        from collector.engine import Unit
        from collector.sources import gsc as G
        with TempDir() as tmp:
            old = G.ROW_LIMIT
            G.ROW_LIMIT = 10
            old_cap = G.DAILY_CAP
            G.DAILY_CAP = 20
            try:
                svc = FakeService(gsc_handler(rows_per_day=25))
                ctx = make_ctx(tmp, services={"searchconsole": svc})
                src = G.GscSource(ctx)
                ds = G.dataset_for("web", "date_query", ["query"], "day", "daily")
                res = src.fetch(FAKE_SITE, ds, Unit("gsc", ds.name, FAKE_SITE, d("2026-10-01"), d("2026-10-01")))
                self.assertEqual(res.pages, 2)
                self.assertEqual(len(res.rows), 20)
                self.assertTrue(res.info["hit_daily_cap"])
                svc2 = FakeService(gsc_handler(rows_per_day=15))
                ctx2 = make_ctx(tmp / "b", services={"searchconsole": svc2})
                res2 = G.GscSource(ctx2).fetch(FAKE_SITE, ds, Unit("gsc", ds.name, FAKE_SITE, d("2026-10-01"), d("2026-10-01")))
                self.assertEqual(res2.pages, 2)
                self.assertEqual(len(res2.rows), 15)
                self.assertNotIn("hit_daily_cap", res2.info)
            finally:
                G.ROW_LIMIT, G.DAILY_CAP = old, old_cap

    def test_no_query_datasets_for_discover(self):
        from collector.settings import load_settings
        from collector.sources.gsc import datasets_for_type
        names = [ds.name for ds in datasets_for_type("discover", load_settings())]
        self.assertFalse(any("query" in n for n in names))
        self.assertIn("gsc_web_date_query_country", [ds.name for ds in datasets_for_type("web", load_settings())])
        self.assertNotIn("gsc_image_date_query_country", [ds.name for ds in datasets_for_type("image", load_settings())])

    def test_page_guard(self):
        from collector.engine import Unit
        from collector.sources import gsc as G
        with TempDir() as tmp:
            ctx = make_ctx(tmp, services={"searchconsole": FakeService(
                gsc_handler(page_value="https://example.com/trade-list/?s=SHAREID"))})
            ds = G.dataset_for("web", "date_page", ["page"], "day", "daily")
            with self.assertRaises(QueryInDimension) as cm:
                G.GscSource(ctx).fetch(FAKE_SITE, ds, Unit("gsc", ds.name, FAKE_SITE, d("2026-10-01"), d("2026-10-01")))
            self.assertNotIn("SHAREID", str(cm.exception))

    def test_backfill_small_range_with_quality(self):
        from collector.sources.gsc import GscSource
        with TempDir() as tmp:
            ctx = make_ctx(tmp, services={"searchconsole": FakeService(
                gsc_handler(empty_types=("image", "video", "news", "discover", "googleNews")))}, end="2026-10-30",
                settings_override=GSC_EXAMPLE)
            GscSource(ctx).run("backfill", start="2026-10-28")
            q = ctx.source_dir("gsc") / "csv" / "gsc_quality_web" / "2026-10.csv"
            _, rows = read_csv(q)
            self.assertTrue(rows)
            self.assertEqual(rows[0]["click_gap_ratio"], "0.0")
            _, daily = read_csv(ctx.source_dir("gsc") / "csv" / "gsc_web_date_query" / "2026-10" / "2026-10-30.csv")
            self.assertEqual(daily[0]["is_final"], "false")   # firstIncompleteDate = 10-29


# ------------------------------------------------------------------ GA4

def ga4_handler(pages=("/", "/trade-list/"), home=("/?tab=cp-checker-app&mon=x",), landing=("/",),
                compat_drop=(), quota_remaining=150000, web_uri="https://www.example.com", home_from=None):
    def handler(path, kw):
        if path == "accountSummaries.list":
            return {"accountSummaries": [{"account": "accounts/1", "propertySummaries": [
                {"property": FAKE_PROPERTY}, {"property": "properties/999"}]}]}
        if path == "properties.get":
            return {"name": kw["name"], "timeZone": "Asia/Taipei", "currencyCode": "TWD",
                    "createTime": "2024-01-01T00:00:00Z"}
        if path == "properties.dataStreams.list":
            uri = web_uri if kw["parent"] == FAKE_PROPERTY else "https://notexample.com"
            mid = "G-FAKE00001" if kw["parent"] == FAKE_PROPERTY else "G-FAKE00002"
            return {"dataStreams": [{"type": "WEB_DATA_STREAM",
                                     "webStreamData": {"defaultUri": uri, "measurementId": mid}}]}
        if path == "properties.checkCompatibility":
            b = kw["body"]
            return {"dimensionCompatibilities": [{"dimensionMetadata": {"apiName": x["name"]}} for x in b["dimensions"]],
                    "metricCompatibilities": [{"metricMetadata": {"apiName": x["name"]}} for x in b["metrics"]
                                              if x["name"] not in compat_drop]}
        if path == "properties.runReport":
            b = kw["body"]
            dims = [x["name"] for x in b["dimensions"]]
            mets = [x["name"] for x in b["metrics"]]
            s = d(b["dateRanges"][0]["startDate"])
            home_vals = () if home_from and s.isoformat() < home_from else home
            vals = {"pagePath": pages, "pagePathPlusQueryString": home_vals, "landingPage": landing}
            rows = []
            for v in vals.get(dims[1], ("v",)) if len(dims) > 1 else ("",):
                dv = [{"value": s.strftime("%Y%m%d")}] + ([{"value": v}] if len(dims) > 1 else [])
                dv += [{"value": "x"} for _ in dims[2:]]
                rows.append({"dimensionValues": dv, "metricValues": [{"value": "5"} for _ in mets]})
            return {"dimensionHeaders": [{"name": n} for n in dims], "metricHeaders": [{"name": n} for n in mets],
                    "rows": rows, "rowCount": len(rows), "metadata": {"currencyCode": "TWD"},
                    "propertyQuota": {"tokensPerDay": {"consumed": 10, "remaining": quota_remaining},
                                      "tokensPerHour": {"consumed": 10, "remaining": 39000}}}
        raise AssertionError(path)
    return handler


def ga4_services(handler):
    svc = FakeService(handler)
    return {"analyticsadmin": svc, "analyticsdata": svc}


class Ga4Tests(unittest.TestCase):
    def test_forbidden_dimensions(self):
        from collector.engine import Dataset
        from collector.sources import ga4 as G
        bad = Dataset(source="ga4", name="x", dims=["date", "pagePathPlusQueryString"], dim_cols=["pagePathPlusQueryString"],
                      metrics=["eventCount"], chunk="month", layout="monthly")
        with self.assertRaises(ConfigError):
            G.validate_dataset(bad)
        home_no_filter = Dataset(source="ga4", name=G.HOME_DATASET, dims=["date", "pagePathPlusQueryString"],
                                 dim_cols=["pagePathPlusQueryString"], metrics=["eventCount"], chunk="month",
                                 layout="monthly")
        with self.assertRaises(ConfigError):
            G.validate_dataset(home_no_filter)
        for ds in G.DATASETS:
            G.validate_dataset(ds)
        home = [ds for ds in G.DATASETS if ds.name == G.HOME_DATASET][0]
        self.assertEqual(home.options["dimension_filter"]["filter"]["stringFilter"],
                         {"matchType": "EXACT", "value": "/"})

    def test_host_matching_and_selection(self):
        from collector.sources import ga4 as G
        self.assertTrue(G.host_matches("https://www.pogokit.com/", "pogokit.com"))
        self.assertTrue(G.host_matches("https://pogokit.com", "pogokit.com"))
        self.assertFalse(G.host_matches("https://notpogokit.com", "pogokit.com"))
        self.assertFalse(G.host_matches("https://pogokit.com.evil.example", "pogokit.com"))
        with TempDir() as tmp:
            ctx = make_ctx(tmp, services=ga4_services(ga4_handler()),
                           settings_override={"ga4": {"site_domain": "example.com"}})
            src = G.Ga4Source(ctx)
            props = src.select_properties(src.discover())
            self.assertEqual([p["scope_id"] for p in props], [FAKE_PROPERTY])
            self.assertEqual(ctx.manifest.data["skipped_scopes"]["ga4"][0]["scope_id"], "properties/999")

    def test_measurement_id_in_inventory_and_history_limit(self):
        from collector.sources import ga4 as G
        with TempDir() as tmp:
            ctx = self._run_ds(tmp, "ga4_date")
            inv = ctx.read_state("inventory.json", {})["ga4"]
            by = {p["scope_id"]: p for p in inv["properties"]}
            self.assertEqual(by[FAKE_PROPERTY]["measurement_ids"], ["G-FAKE00001"])
            rec = ctx.manifest.get(f"ga4/ga4_date/{FAKE_PROPERTY}")
            self.assertTrue(any("2024-01-01" in x and "歷史只從" in x for x in rec["known_limits"]))
        self.assertEqual(G.history_limits({}), [])

    def test_zero_row_probe_is_no_data_and_skipped(self):
        """GA4 試查 0 列（例如 ga4_date_ads：GA4 未連結 AdSense）→ no_data，backfill 跳過。"""
        from collector.sources import ga4 as G
        with TempDir() as tmp:
            svc = FakeService(ga4_handler(pages=()))
            ctx = make_ctx(tmp, services={"analyticsadmin": svc, "analyticsdata": svc}, end="2026-10-03",
                           settings_override={"ga4": {"site_domain": "example.com"}})
            G.Ga4Source(ctx).run("backfill", start="2026-10-01", datasets={"ga4_date_ads"})
            reports = [kw for path, kw in svc.calls if path == "properties.runReport"]
            self.assertEqual(len(reports), 1)           # 只有 probe
            pr = ctx.read_state("probe.json", {})[f"ga4/ga4_date_ads/{FAKE_PROPERTY}"]
            self.assertEqual((pr["status"], pr["probe_rows"]), ("no_data", 0))
            rec = ctx.manifest.get(f"ga4/ga4_date_ads/{FAKE_PROPERTY}")
            self.assertEqual(rec["status"], "no_data")
            self.assertTrue(any("廣告收益請看 AdSense" in x for x in rec["known_limits"]))

    def test_legacy_supported_zero_rows_treated_as_no_data(self):
        from collector.sources import ga4 as G
        self.assertEqual(G.probe_status({"status": "supported", "probe_rows": 0}), "no_data")
        self.assertEqual(G.probe_status({"status": "supported", "probe_rows": 3}), "supported")
        self.assertEqual(G.probe_status({"status": "supported"}), "supported")

    def test_no_matching_property_stops(self):
        from collector.sources import ga4 as G
        with TempDir() as tmp:
            ctx = make_ctx(tmp, services=ga4_services(ga4_handler(web_uri="https://other.invalid")),
                           settings_override={"ga4": {"site_domain": "example.com"}})
            src = G.Ga4Source(ctx)
            with self.assertRaises(SourceStop):
                src.select_properties(src.discover())

    def _run_ds(self, tmp, name, ga4_settings=None, **handler_kw):
        from collector.sources import ga4 as G
        ga4_cfg = {"site_domain": "example.com"}
        ga4_cfg.update(ga4_settings or {})
        ctx = make_ctx(tmp, services=ga4_services(ga4_handler(**handler_kw)), end="2026-10-03",
                       settings_override={"ga4": ga4_cfg})
        G.Ga4Source(ctx).run("backfill", start="2026-10-01", datasets={name})
        return ctx

    def test_landing_with_query_stops_dataset(self):
        with TempDir() as tmp:
            ctx = self._run_ds(tmp, "ga4_date_landing", landing=("/trade-list/?s=SHARE123",))
            rec = ctx.manifest.get(f"ga4/ga4_date_landing/{FAKE_PROPERTY}")
            self.assertEqual(rec["status"], "stopped")
            self.assertIn("share_id_param", rec["guard_hits"])
            self.assertTrue(any("share_id_param" in x for x in rec["known_limits"]))
            self.assertFalse((ctx.source_dir("ga4") / "csv" / "ga4_date_landing").exists())
            for p in (tmp / "manifest.json", tmp / "collection_log.jsonl"):
                self.assertNotIn("SHARE123", p.read_text(encoding="utf-8"))

    def test_pagepath_with_question_mark_or_digits_stops(self):
        for bad in ("/x?y=1", "/u/123456789012"):
            with TempDir() as tmp:
                ctx = self._run_ds(tmp, "ga4_date_page", pages=(bad,))
                self.assertEqual(ctx.manifest.get(f"ga4/ga4_date_page/{FAKE_PROPERTY}")["status"], "stopped")

    def test_home_query_exact_filter_and_client_check(self):
        with TempDir() as tmp:
            ctx = self._run_ds(tmp, "ga4_date_home_query")
            _, rows = read_csv(ctx.source_dir("ga4") / "csv" / "ga4_date_home_query" / "2026-10.csv")
            self.assertEqual(rows[0]["pagePathPlusQueryString"], "/?tab=cp-checker-app&mon=x")
        with TempDir() as tmp:
            ctx = self._run_ds(tmp, "ga4_date_home_query", home=("/?tab=x", "/trade-list/?s=x"))
            self.assertEqual(ctx.manifest.get(f"ga4/ga4_date_home_query/{FAKE_PROPERTY}")["status"], "stopped")
    def test_home_query_drops_rows_instead_of_stopping(self):
        """B：首頁 query 命中 s= 或 digits12 的列逐列排除，資料集繼續；只記規則與列數。"""
        tracking = "/?media_id=" + "1" * 19 + "&media_author_id=" + "2" * 17 + "&ranking_info_token=x"
        typed = "/?tab=cp-checker-app&mon=" + "3" * 15
        share = "/?s=SHAREVALUE"
        ok = "/?tab=cp-checker-app&mon=%E7%9A%AE%E5%8D%A1%E4%B8%98"
        lenient = {"home_drop_stop": {"max_ratio": 0.9, "max_rows": 20}}    # 假資料每天只有 4 列，放寬停損
        with TempDir() as tmp:
            ctx = self._run_ds(tmp, "ga4_date_home_query", ga4_settings=lenient, home=(tracking, typed, share, ok))
            rec = ctx.manifest.get(f"ga4/ga4_date_home_query/{FAKE_PROPERTY}")
            self.assertNotEqual(rec["status"], "stopped")
            # 每天被排除列的合計：只有數字，沒有維度值
            _, dd = read_csv(ctx.source_dir("ga4") / "csv" / "ga4_quality_dropped_daily.csv")
            self.assertEqual(len(dd), 1)
            self.assertEqual((dd[0]["date"], dd[0]["total_rows"], dd[0]["dropped_rows"]), ("2026-10-01", "4", "3"))
            self.assertEqual(float(dd[0]["screenPageViews"]), 15.0)
            self.assertEqual(float(dd[0]["eventCount"]), 15.0)
            self.assertEqual(float(dd[0]["userEngagementDuration"]), 15.0)
            self.assertNotIn("pagePathPlusQueryString", dd[0])
            self.assertEqual(rec["dropped_rows_by_rule"], {"digits12": 2, "share_id_param": 1})
            self.assertTrue(any("逐列排除" in x and "下限估計" in x for x in rec["known_limits"]))
            _, rows = read_csv(ctx.source_dir("ga4") / "csv" / "ga4_date_home_query" / "2026-10.csv")
            self.assertEqual([r["pagePathPlusQueryString"] for r in rows], [ok])
            _, q = read_csv(ctx.source_dir("ga4") / "csv" / "ga4_quality.csv")
            home_q = [x for x in q if x["dataset"] == "ga4_date_home_query"]
            self.assertEqual(json.loads(home_q[0]["dropped_rows_by_rule"]), {"digits12": 2, "share_id_param": 1})
            for p in (tmp / "manifest.json", tmp / "collection_log.jsonl", tmp / "state" / "checkpoints.json"):
                text = p.read_text(encoding="utf-8")
                for v in ("1" * 19, "3" * 15, "SHAREVALUE"):
                    self.assertNotIn(v, text)
            self.assertIn("rows_dropped", (tmp / "collection_log.jsonl").read_text(encoding="utf-8"))

    def test_home_query_drop_stop_loss(self):
        """停損：單日排除列數 > 20，或 > 該日總列數 1%（預設值）→ 整個停止，不寫 CSV。"""
        from collector.settings import load_settings
        stop = load_settings()["ga4"]["home_drop_stop"]
        self.assertEqual((stop["max_ratio"], stop["max_rows"], stop["min_rows_for_ratio"]), (0.01, 20, 3))
        # 59 列中排除 1 列（1.7%）→ 排除列數 < 3，不看比例 → 不停
        with TempDir() as tmp:
            ctx = self._run_ds(tmp, "ga4_date_home_query",
                               home=tuple(f"/?tab=a&mon=n{i}" for i in range(58)) + ("/?s=A",))
            self.assertNotEqual(ctx.manifest.get(f"ga4/ga4_date_home_query/{FAKE_PROPERTY}")["status"], "stopped")
        # 100 列中排除 3 列（3%）→ 停
        with TempDir() as tmp:
            ctx = self._run_ds(tmp, "ga4_date_home_query",
                               home=tuple(f"/?tab=a&mon=n{i}" for i in range(97)) + ("/?s=A", "/?s=B", "/?s=C"))
            self.assertEqual(ctx.manifest.get(f"ga4/ga4_date_home_query/{FAKE_PROPERTY}")["status"], "stopped")
        ok = tuple(f"/?tab=cp-checker-app&mon=m{i}" for i in range(199))
        # 199 列正常 + 1 列命中 = 0.5% → 不停
        with TempDir() as tmp:
            ctx = self._run_ds(tmp, "ga4_date_home_query", home=ok + ("/?s=A",))
            self.assertNotEqual(ctx.manifest.get(f"ga4/ga4_date_home_query/{FAKE_PROPERTY}")["status"], "stopped")
        # 199 列正常 + 3 列命中 ≈ 1.5% → 停
        with TempDir() as tmp:
            ctx = self._run_ds(tmp, "ga4_date_home_query", home=ok + ("/?s=A", "/?s=B", "/?s=C"))
            rec = ctx.manifest.get(f"ga4/ga4_date_home_query/{FAKE_PROPERTY}")
            self.assertEqual(rec["status"], "stopped")
            self.assertIn("drop_stop", rec["guard_hits"])
            self.assertFalse((ctx.source_dir("ga4") / "csv" / "ga4_date_home_query").exists())
        # 比例放寬到 100%，但命中 21 列 > 20 → 停
        with TempDir() as tmp:
            ctx = self._run_ds(tmp, "ga4_date_home_query", ga4_settings={"home_drop_stop": {"max_ratio": 1.0}},
                               home=tuple(f"/?s=x{i}" for i in range(21)) + ok)
            self.assertEqual(ctx.manifest.get(f"ga4/ga4_date_home_query/{FAKE_PROPERTY}")["status"], "stopped")
            for p in (tmp / "manifest.json", tmp / "collection_log.jsonl"):
                self.assertNotIn("s=x1", p.read_text(encoding="utf-8"))

    def test_home_query_gap_note_from_data(self):
        """首頁 query 第一個有列的日期晚於 property 第一天 → known_limits 說明落差（日期取自資料）。"""
        from collector.sources import ga4 as G
        with TempDir() as tmp:
            ctx = make_ctx(tmp, services=ga4_services(ga4_handler(home_from="2026-10-01")), end="2026-10-20",
                           settings_override={"ga4": {"site_domain": "example.com"}})
            G.Ga4Source(ctx).run("backfill", start="2026-09-29", datasets={"ga4_date", G.HOME_DATASET})
            rec = ctx.manifest.get(f"ga4/{G.HOME_DATASET}/{FAKE_PROPERTY}")
            self.assertEqual(rec["home_query_first_date"], "2026-10-01")
            notes = [x for x in rec["known_limits"] if x.startswith("首頁 query 資料自")]
            self.assertEqual(len(notes), 1)
            self.assertIn("首頁 query 資料自 2026-10-01 起；2026-09-29～2026-09-30 API 回傳 0 列", notes[0])
            self.assertIn("原因【未知】", notes[0])
            self.assertIn("ga4_date_page", notes[0])
        # 首頁 query 與 property 同一天開始 → 不加說明
        with TempDir() as tmp:
            ctx = make_ctx(tmp, services=ga4_services(ga4_handler()), end="2026-10-20",
                           settings_override={"ga4": {"site_domain": "example.com"}})
            G.Ga4Source(ctx).run("backfill", start="2026-09-29", datasets={"ga4_date", G.HOME_DATASET})
            rec = ctx.manifest.get(f"ga4/{G.HOME_DATASET}/{FAKE_PROPERTY}")
            self.assertFalse(any(x.startswith("首頁 query 資料自") for x in rec["known_limits"]))

    def test_page_and_landing_still_stop(self):
        with TempDir() as tmp:
            ctx = self._run_ds(tmp, "ga4_date_page", pages=("/", "/u/" + "4" * 12))
            self.assertEqual(ctx.manifest.get(f"ga4/ga4_date_page/{FAKE_PROPERTY}")["status"], "stopped")

    def test_request_body_has_exact_filter(self):
        from collector.sources import ga4 as G
        with TempDir() as tmp:
            svc = FakeService(ga4_handler())
            ctx = make_ctx(tmp, services={"analyticsadmin": svc, "analyticsdata": svc}, end="2026-10-03",
                           settings_override={"ga4": {"site_domain": "example.com"}})
            G.Ga4Source(ctx).run("backfill", start="2026-10-01", datasets={G.HOME_DATASET})
            bodies = [kw["body"] for path, kw in svc.calls if path == "properties.runReport"]
            self.assertTrue(bodies)
            for b in bodies:
                self.assertEqual(b["dimensionFilter"], G.HOME_FILTER)

    def test_compat_removes_metric_but_keeps_column(self):
        with TempDir() as tmp:
            ctx = self._run_ds(tmp, "ga4_date", compat_drop=("newUsers",))
            header, rows = read_csv(ctx.source_dir("ga4") / "csv" / "ga4_date" / "2026-10.csv")
            self.assertIn("newUsers", header)
            self.assertEqual(rows[0]["newUsers"], "")
            self.assertEqual(rows[0]["totalUsers"], "5")

    def test_quota_stop(self):
        from collector.sources import ga4 as G
        with TempDir() as tmp:
            ctx = make_ctx(tmp, services=ga4_services(ga4_handler(quota_remaining=5)), end="2026-12-03",
                           settings_override={"ga4": {"site_domain": "example.com"}})
            with self.assertRaises(SourceStop):
                G.Ga4Source(ctx).run("backfill", start="2026-10-01", datasets={"ga4_date"})


# ------------------------------------------------------------------ CrUX / PSI

class FakeHttp:
    def __init__(self, responder):
        self.responder = responder
        self.calls = []

    def __call__(self, method, url, *, api_key, key_mode="header", body=None, timeout=60):
        self.calls.append({"method": method, "url": url, "body": body, "key_mode": key_mode})
        return self.responder(method, url, body)


class CruxPsiTests(unittest.TestCase):
    def test_crux_404_is_no_data(self):
        from collector.sources.crux import run_crux

        def responder(method, url, body):
            if body.get("url"):
                raise api_error(E.NOT_FOUND, 404)
            if "History" in url:
                return 200, {"record": {"collectionPeriods": [
                    {"firstDate": {"year": 2026, "month": 9, "day": 1}, "lastDate": {"year": 2026, "month": 9, "day": 28}},
                    {"firstDate": {"year": 2026, "month": 9, "day": 8}, "lastDate": {"year": 2026, "month": 10, "day": 5}}],
                    "metrics": {"largest_contentful_paint": {"percentilesTimeseries": {"p75s": [2100, "NaN"]},
                                                             "histogramTimeseries": [{"densities": [0.8, None]}]}}}}
            return 200, {"record": {"collectionPeriod": {"firstDate": {"year": 2026, "month": 10, "day": 1},
                                                         "lastDate": {"year": 2026, "month": 10, "day": 28}},
                                    "metrics": {"cumulative_layout_shift": {"percentiles": {"p75": "0.05"},
                                                "histogram": [{"density": 0.9}, {"density": 0.07}, {"density": 0.03}]}}}}

        with TempDir() as tmp:
            ctx = make_ctx(tmp)
            http = FakeHttp(responder)
            run_crux(ctx, ["https://example.com/a"], origin="https://example.com", form_factors=["PHONE"],
                     history_periods=40, api_key=FAKE_API_KEY, http=http)
            _, cur = read_csv(ctx.source_dir("crux") / "csv" / "crux_current.csv")
            nd = [r for r in cur if r["status"] == "no_data"]
            self.assertEqual(len(nd), 1)
            self.assertEqual(nd[0]["p75"], "")
            self.assertEqual(nd[0]["good_density"], "")
            _, hist = read_csv(ctx.source_dir("crux") / "csv" / "crux_history.csv")
            ok = [r for r in hist if r["status"] == "ok"]
            self.assertEqual([r["p75_missing"] for r in ok], ["false", "true"])
            self.assertEqual(ok[1]["p75"], "")
            self.assertEqual(http.calls[0]["body"]["formFactor"], "PHONE")
            self.assertEqual([c["body"].get("collectionPeriodCount") for c in http.calls if "History" in c["url"]], [40, 40])

    def test_crux_data_replaces_no_data(self):
        """g：之前是 no_data 的 (target, form_factor)，之後拿到資料時，舊的 no_data 列要刪掉。"""
        from collector.sources.crux import run_crux
        state = {"has_data": False}

        def responder(method, url, body):
            if body.get("url") and not state["has_data"]:
                raise api_error(E.NOT_FOUND, 404)
            return 200, {"record": {"collectionPeriod": {"firstDate": {"year": 2026, "month": 10, "day": 1},
                                                         "lastDate": {"year": 2026, "month": 10, "day": 28}},
                                    "metrics": {"cumulative_layout_shift": {"percentiles": {"p75": "0.05"},
                                                "histogram": [{"density": 0.9}, {"density": 0.07}, {"density": 0.03}]}}}}

        with TempDir() as tmp:
            ctx = make_ctx(tmp)
            kw = dict(origin="https://example.com", form_factors=["PHONE", "DESKTOP"], history_periods=40,
                      api_key=FAKE_API_KEY, with_history=False)
            run_crux(ctx, ["https://example.com/a"], http=FakeHttp(responder), **kw)
            _, cur = read_csv(ctx.source_dir("crux") / "csv" / "crux_current.csv")
            self.assertEqual(len([r for r in cur if r["status"] == "no_data"]), 2)
            state["has_data"] = True
            run_crux(ctx, ["https://example.com/a"], http=FakeHttp(responder), **kw)
            _, cur = read_csv(ctx.source_dir("crux") / "csv" / "crux_current.csv")
            url_rows = [r for r in cur if r["target"] == "https://example.com/a"]
            self.assertEqual([r["status"] for r in url_rows], ["ok", "ok"])
            self.assertEqual(sorted(r["form_factor"] for r in url_rows), ["DESKTOP", "PHONE"])

    def test_crux_no_data_kept_for_other_pairs(self):
        from collector.sources.crux import stale_no_data
        drop = stale_no_data([{"target": "A", "form_factor": "PHONE", "metric": "lcp", "status": "ok"}])
        self.assertTrue(drop({"target": "A", "form_factor": "PHONE", "metric": "", "status": "no_data"}))
        self.assertFalse(drop({"target": "A", "form_factor": "DESKTOP", "metric": "", "status": "no_data"}))
        self.assertFalse(drop({"target": "B", "form_factor": "PHONE", "metric": "", "status": "no_data"}))
        self.assertFalse(drop({"target": "A", "form_factor": "PHONE", "metric": "lcp", "status": "ok"}))

    def test_psi_max_tests_and_parse(self):
        from collector.sources.psi import parse_result, run_psi
        with TempDir() as tmp:
            ctx = make_ctx(tmp)
            with self.assertRaises(ConfigError):
                run_psi(ctx, ["https://example.com/"] * 31, strategies=["mobile", "desktop"], runs=1, max_tests=60,
                        api_key=FAKE_API_KEY, http=FakeHttp(lambda *a: self.fail("不應呼叫")))
        ok = parse_result({"lighthouseResult": {"fetchTime": "t", "lighthouseVersion": "12",
                                                "categories": {"performance": {"score": 0.9}},
                                                "audits": {"largest-contentful-paint": {"numericValue": 2000}}},
                           "loadingExperience": {"metrics": {"INTERACTION_TO_NEXT_PAINT": {"percentile": 120}}}})
        self.assertEqual(ok["status"], "ok")
        self.assertEqual(ok["lcp_ms"], 2000)
        self.assertEqual(ok["has_field_data"], "true")
        err = parse_result({"lighthouseResult": {"runtimeError": {"code": "FAILED_DOCUMENT_REQUEST", "message": "x"},
                                                 "categories": {"performance": {"score": None}}}})
        self.assertEqual(err["status"], "lh_error")
        self.assertNotIn("perf_score", err)

    def test_psi_run_median_and_no_key_in_outputs(self):
        from collector.sources.psi import run_psi
        scores = iter([0.5, 0.9, 0.7])

        def responder(method, url, body):
            return 200, {"lighthouseResult": {"fetchTime": "2026-10-31T00:00:01Z",
                                              "categories": {"performance": {"score": next(scores)}}}}

        with TempDir() as tmp:
            ctx = make_ctx(tmp)
            http = FakeHttp(responder)
            rows = run_psi(ctx, ["https://example.com/"], strategies=["mobile"], runs=3, max_tests=60,
                           api_key=FAKE_API_KEY, http=http)
            self.assertEqual(len(rows), 3)
            _, summ = read_csv(ctx.source_dir("psi") / "csv" / "psi_summary.csv")
            self.assertEqual(summ[0]["perf_score"], "0.7")
            for c in http.calls:
                self.assertNotIn(FAKE_API_KEY, c["url"])
            for p in tmp.rglob("*"):
                if p.is_file() and not p.name.endswith(".gz"):
                    self.assertNotIn(FAKE_API_KEY, p.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
