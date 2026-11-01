import contextlib
import io
import json
import shutil
import unittest

from collector import cli
from collector.storage import write_json_atomic

from .fakes import TempDir

# CLI 測試走真實的 defaults.json（gsc.site_domain = pogokit.com）。網域本身是公開資訊。
FAKE_SITE = "sc-domain:pogokit.com"


def run(argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = cli.main(argv)
    return code, out.getvalue(), err.getvalue()


class PartialCountTests(unittest.TestCase):
    """f：check 指令列出 .partial 檔數量。"""

    def test_count_partials(self):
        with TempDir() as tmp:
            self.assertEqual(cli.count_partials(tmp / "missing"), 0)
            (tmp / "adsense" / "raw").mkdir(parents=True)
            (tmp / "adsense" / "raw" / "a.json.gz.partial").write_bytes(b"x")
            (tmp / "adsense" / "raw" / "b.json.gz").write_bytes(b"x")
            (tmp / "gsc").mkdir()
            (tmp / "gsc" / "c.json.gz.partial").write_bytes(b"x")
            self.assertEqual(cli.count_partials(tmp), 2)


FAKE_KEY = "AIza" + "K" * 35
OTHER_KEY = "AIza" + "Z" * 35          # 例如網站公開的 Firebase key：不是我們的 key
FAKE_CLIENT_SECRET = "GOCSPX-FAKEsecretFORscanTEST"


def seed_scan_files(data_dir):
    import gzip
    from urllib.parse import quote
    raw = data_dir / "pagespeed" / "raw" / "2026-10"
    raw.mkdir(parents=True)
    with gzip.open(raw / "a.json.gz", "wb") as f:              # 含我們的 key（gz）
        f.write(json.dumps({"x": f"https://example.invalid/?key={FAKE_KEY}"}).encode())
    with gzip.open(raw / "b.json.gz", "wb") as f:              # 只含別人的 key
        f.write(json.dumps({"x": OTHER_KEY}).encode())
    with gzip.open(raw / "c.json.gz", "wb") as f:              # URL 編碼後的 client_secret
        f.write(quote(FAKE_CLIENT_SECRET, safe="").encode() + b"x")
    (data_dir / "plain.txt").write_text(f"plain {FAKE_KEY}", encoding="utf-8")   # 含我們的 key（非 gz）
    (data_dir / "clean.csv").write_text("nothing here", encoding="utf-8")


class ScanForKeyTests(unittest.TestCase):
    def test_counts_files_only(self):
        with TempDir() as tmp:
            seed_scan_files(tmp)
            counts, scanned, unreadable = cli.scan_files_for_secrets(
                tmp, {"api_key": FAKE_KEY, "client_secret": FAKE_CLIENT_SECRET})
            self.assertEqual(counts, {"api_key": 2, "client_secret": 1})
            self.assertEqual((scanned, unreadable), (5, 0))

    def test_missing_dir(self):
        with TempDir() as tmp:
            self.assertEqual(cli.scan_files_for_secrets(tmp / "nope", {"api_key": FAKE_KEY}), ({"api_key": 0}, 0, 0))


@unittest.skipUnless(shutil.which("git"), "找不到 git（資料目錄檢查需要 git）")
class CliTests(unittest.TestCase):
    def test_check_scan_raw_for_key_outputs_counts_only(self):
        """F2：只輸出檔案數，絕不輸出 key 或片段。"""
        from collector import redact as R
        with TempDir() as tmp:
            (tmp / "data").mkdir()
            seed_scan_files(tmp / "data")
            creds = tmp / "creds"
            creds.mkdir()
            (creds / "api_key.txt").write_text(FAKE_KEY + "\n", encoding="utf-8")
            (creds / "client_secret.json").write_text(json.dumps(
                {"installed": {"client_id": "x.apps.example", "client_secret": FAKE_CLIENT_SECRET}}), encoding="utf-8")
            try:
                code, out, err = run(self.base(tmp) + ["check", "--scan-raw-for-key"])
            finally:
                R.clear_registered()
            self.assertEqual(code, 1)                 # 有找到 → exit 1，提醒要處理
            self.assertIn("含有本 Collector API key 的檔案數：2", out)
            self.assertIn("含有本 Collector client_secret 的檔案數：1", out)
            for text in (out, err):
                self.assertNotIn(FAKE_KEY, text)
                self.assertNotIn(FAKE_KEY[4:20], text)
                self.assertNotIn(FAKE_CLIENT_SECRET, text)
            # 只有別人的 key → 0
            for p in (tmp / "data").rglob("*"):
                if p.is_file():
                    p.unlink()
            raw = tmp / "data" / "x.txt"
            raw.write_text(OTHER_KEY, encoding="utf-8")
            try:
                code, out, _ = run(self.base(tmp) + ["check", "--scan-raw-for-key"])
            finally:
                R.clear_registered()
            self.assertEqual(code, 0)
            self.assertIn("含有本 Collector API key 的檔案數：0", out)
    def base(self, tmp):
        return ["--data-dir", str(tmp / "data"), "--cred-dir", str(tmp / "creds")]

    def seed_gsc(self, tmp):
        state = tmp / "data" / "state"
        write_json_atomic(state / "inventory.json",
                          {"gsc": {"sites": [{"scope_id": FAKE_SITE, "permission": "siteOwner"}]}})
        probes = {f"gsc/type/{t}/{FAKE_SITE}": {"status": "no_data"}
                  for t in ("image", "video", "news", "discover", "googleNews")}
        probes[f"gsc/type/web/{FAKE_SITE}"] = {"status": "supported", "first_date": "2026-10-01"}
        write_json_atomic(state / "probe.json", probes)

    def test_parser(self):
        p = cli.build_parser()
        a = p.parse_args(["--dry-run", "backfill", "--source", "gsc", "--start", "2026-10-01"])
        self.assertTrue(a.dry_run)
        self.assertEqual(a.cmd, "backfill")

    def test_status_on_empty_dir(self):
        with TempDir() as tmp:
            code, out, err = run(self.base(tmp) + ["status"])
            self.assertEqual(code, 0, err)
            self.assertTrue((tmp / "data" / ".gitignore").exists())

    def test_dry_run_requires_inventory(self):
        with TempDir() as tmp:
            code, out, err = run(self.base(tmp) + ["--dry-run", "backfill", "--source", "gsc"])
            self.assertEqual(code, 2)

    def test_dry_run_plans_without_requests_or_writes(self):
        with TempDir() as tmp:
            (tmp / "data").mkdir()
            self.seed_gsc(tmp)
            before = sorted(p.name for p in (tmp / "data").rglob("*"))
            code, out, err = run(self.base(tmp) + ["--dry-run", "backfill", "--source", "gsc",
                                                   "--start", "2026-10-01", "--end", "2026-10-10"])
            self.assertEqual(code, 0, err)
            self.assertIn("[dry-run]", out)
            self.assertIn("gsc/gsc_web_date_query/", out)
            after = sorted(p.name for p in (tmp / "data").rglob("*"))
            self.assertEqual(before, after)

    def test_missing_token_is_exit_3(self):
        with TempDir() as tmp:
            (tmp / "data").mkdir()
            self.seed_gsc(tmp)
            code, out, err = run(self.base(tmp) + ["update", "--source", "gsc", "--end", "2026-10-10"])
            self.assertEqual(code, 3)
            self.assertIn("auth", err)
            log = (tmp / "data" / "collection_log.jsonl").read_text(encoding="utf-8").splitlines()
            self.assertEqual(json.loads(log[-1])["event"], "run_end")
            self.assertFalse((tmp / "data" / "state" / "run.lock").exists())

    def test_auth_scope_unchecked_exit_3(self):
        from unittest import mock

        from collector import credentials
        from collector.errors import AuthRequired

        def fake_flow(cred_dir):
            raise AuthRequired("授權時沒有勾選全部權限。請重新執行 auth，並勾選全部三個權限後再試一次。")

        with TempDir() as tmp:
            with mock.patch.object(credentials, "run_auth_flow", fake_flow):
                code, out, err = run(self.base(tmp) + ["auth"])
            self.assertEqual(code, 3)
            self.assertIn("勾選全部三個權限", err)

    def test_snapshot_skips_sources_without_snapshot(self):
        """GA4 沒有快照：snapshot --source ga4 要略過、exit 0，不能丟 AttributeError。"""
        with TempDir() as tmp:
            code, out, err = run(self.base(tmp) + ["snapshot", "--source", "ga4"])
            self.assertEqual(code, 0, err)
            self.assertIn("[ga4] 沒有快照，略過", out)
            log = (tmp / "data" / "collection_log.jsonl").read_text(encoding="utf-8")
            self.assertIn("snapshot_skipped", log)
            self.assertFalse((tmp / "data" / "ga4").exists())        # 沒有任何寫入
            self.assertFalse((tmp / "data" / "state" / "run.lock").exists())

    def test_snapshot_source_selection(self):
        """--source 只跑指定的來源：其他來源的物件不會被呼叫。"""
        from unittest import mock
        calls = []

        class FakeSrc:
            def __init__(self, name):
                self.name = name

            def snapshot(self):
                calls.append(self.name)

        def fake_objects(ctx, names):
            return [(n, FakeSrc(n)) for n in names]

        with TempDir() as tmp:
            with mock.patch.object(cli, "source_objects", fake_objects):
                code, _, err = run(self.base(tmp) + ["snapshot", "--source", "gsc"])
            self.assertEqual(code, 0, err)
            self.assertEqual(calls, ["gsc"])

    def test_refetch_requires_args(self):
        with TempDir() as tmp:
            code, _, _ = run(self.base(tmp) + ["refetch", "--source", "gsc"])
            self.assertEqual(code, 2)

    def test_refetch_days_requires_single_source(self):
        with TempDir() as tmp:
            code, _, _ = run(self.base(tmp) + ["update", "--refetch-days", "5"])
            self.assertEqual(code, 2)

    def test_psi_max_tests_refused_before_key(self):
        with TempDir() as tmp:
            urls = tmp / "urls.json"
            urls.write_text(json.dumps({"urls": [f"https://example.com/{i}" for i in range(40)]}), encoding="utf-8")
            code, out, err = run(self.base(tmp) + ["--dry-run", "psi", "--urls", str(urls)])
            self.assertEqual(code, 2)
            self.assertIn("max-tests", err)


if __name__ == "__main__":
    unittest.main()
