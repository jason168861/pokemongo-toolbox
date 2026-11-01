"""所有出口都不能洩漏祕密值（設計 §7.2、M4）。"""
import io
import json
import logging
import socket
import sys
import unittest
import urllib.error
import warnings

from collector import redact as R
from collector import runlog
from collector.checkpoint import Checkpoints
from collector.manifest import Manifest
from collector.runlog import RedactingStream, RunLog, emit_console, error_text
from collector.storage import read_raw

from .fakes import FAKE_ACCESS, FAKE_API_KEY, FAKE_REFRESH, TempDir, make_ctx, make_http_error

SECRET_URL = f"https://www.googleapis.com/pagespeedonline/v5/runPagespeed?url=x&key={FAKE_API_KEY}"
SECRETS = (FAKE_API_KEY, FAKE_ACCESS, FAKE_REFRESH)


def _exceptions():
    out = []
    he = make_http_error(403, content=f'{{"error": {{"message": "Bearer {FAKE_ACCESS}"}}}}'.encode(),
                         uri=SECRET_URL)
    if he is not None:
        out.append(he)
    h2 = urllib.error.HTTPError(SECRET_URL, 400, f"bad {FAKE_REFRESH}", {}, None)
    h2._collector_body = f"refresh_token={FAKE_REFRESH}".encode()
    out.append(h2)
    out.append(urllib.error.URLError(f"cannot reach {SECRET_URL}"))
    out.append(socket.timeout(f"timeout Bearer {FAKE_ACCESS} {SECRET_URL}"))
    return out


class OutputRedactionTests(unittest.TestCase):
    def tearDown(self):
        R.clear_registered()

    def assertClean(self, text):
        for s in SECRETS:
            self.assertNotIn(s, text)

    def test_error_text_for_all_exception_types(self):
        for exc in _exceptions():
            self.assertClean(error_text(exc))

    def test_files_do_not_contain_secrets(self):
        with TempDir() as tmp:
            ctx = make_ctx(tmp)
            for i, exc in enumerate(_exceptions()):
                msg = error_text(exc)
                ctx.event("unit_failed", "error", message=msg, nested={"deep": [str(exc)]})
                ctx.checkpoints.set(f"x/ds/s/2026-01-0{i + 1}_2026-01-0{i + 1}", "failed", is_final=True, error=msg)
                ctx.manifest.update_dataset("x/ds/s", checkpoints=ctx.checkpoints, stopped_reason=msg)
                path = ctx.save_raw("adsense", ["t"], ["err", str(i)],
                                    {"api": "t", "request": {}, "response": {"error": msg}})
                self.assertClean(json.dumps(read_raw(path)))
            for p in tmp.rglob("*"):
                if p.is_file() and not p.name.endswith(".gz"):
                    self.assertClean(p.read_text(encoding="utf-8"))
            # collection_log 每行都是合法 JSON
            for line in (tmp / "collection_log.jsonl").read_text(encoding="utf-8").splitlines():
                json.loads(line)

    def test_emit_event_nested_and_valid_json(self):
        with TempDir() as tmp:
            log = RunLog(str(tmp / "log.jsonl"), "test")
            log.emit_event("x", payload={"a": [f"Bearer {FAKE_ACCESS}\"}}", {"k": FAKE_API_KEY}]})
            line = (tmp / "log.jsonl").read_text(encoding="utf-8").strip()
            json.loads(line)
            self.assertClean(line)

    def test_redacting_stream_split_writes(self):
        buf = io.StringIO()
        s = RedactingStream(buf)
        half = len(FAKE_API_KEY) // 2
        s.write("key " + FAKE_API_KEY[:half])
        s.write(FAKE_API_KEY[half:] + " end\n")
        s.flush()
        self.assertClean(buf.getvalue())
        self.assertIn("end", buf.getvalue())

    def test_stdout_stderr_and_warnings(self):
        out, err = io.StringIO(), io.StringIO()
        old_out, old_err, old_show = sys.stdout, sys.stderr, warnings.showwarning
        try:
            sys.stdout, sys.stderr = RedactingStream(out), RedactingStream(err)
            warnings.showwarning = runlog._showwarning
            emit_console(f"console {SECRET_URL}")
            emit_console(f"err {FAKE_REFRESH}", err=True)
            print(f"raw print {FAKE_ACCESS}")
            sys.stderr.write(f"lib wrote {SECRET_URL}\n")
            with warnings.catch_warnings():
                warnings.simplefilter("always")
                warnings.showwarning = runlog._showwarning
                warnings.warn(f"warn {FAKE_API_KEY}")
            sys.stdout.flush()
            sys.stderr.flush()
        finally:
            sys.stdout, sys.stderr, warnings.showwarning = old_out, old_err, old_show
        self.assertClean(out.getvalue())
        self.assertClean(err.getvalue())
        self.assertIn("console", out.getvalue())

    def test_logging_is_redacted(self):
        err = io.StringIO()
        old_err = sys.stderr
        try:
            sys.stderr = RedactingStream(err)
            runlog.configure_logging(verbose=True, debug=True)
            logging.getLogger("collector.test").warning("leak %s", FAKE_API_KEY)
            logging.getLogger("googleapiclient.discovery").warning("uri %s", SECRET_URL)
            sys.stderr.flush()
        finally:
            sys.stderr = old_err
            runlog.configure_logging()
        self.assertClean(err.getvalue())

    def test_debug_does_not_lower_third_party_loggers(self):
        runlog.configure_logging(verbose=True, debug=True)
        for name in runlog.THIRD_PARTY_LOGGERS:
            self.assertEqual(logging.getLogger(name).level, logging.WARNING, name)
        try:
            import httplib2  # type: ignore
            self.assertEqual(httplib2.debuglevel, 0)
        except ImportError:
            pass
        runlog.configure_logging()


if __name__ == "__main__":
    unittest.main()
