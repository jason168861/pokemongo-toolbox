import unittest

from collector import errors as E
from collector.breaker import CircuitBreaker
from collector.ratelimit import RateLimiter
from collector.transport import Budget, check_key_host

from .fakes import FakeClock, api_error, make_transport


class TransportTests(unittest.TestCase):
    def test_retries_then_succeeds(self):
        clock = FakeClock()
        t = make_transport(clock=clock)
        calls = {"n": 0}

        def fn():
            calls["n"] += 1
            if calls["n"] < 3:
                raise api_error(E.TRANSIENT, 503)
            return "ok"

        self.assertEqual(t.call(fn), "ok")
        self.assertEqual(calls["n"], 3)
        self.assertEqual(clock.slept, [1.0, 2.0])     # 2**0 × 1.0、2**1 × 1.0

    def test_max_retries(self):
        t = make_transport(max_retries=5)
        calls = {"n": 0}

        def fn():
            calls["n"] += 1
            raise api_error(E.QUOTA_RATE, 429)

        with self.assertRaises(E.ApiError):
            t.call(fn)
        self.assertEqual(calls["n"], 6)

    def test_retry_after_wins(self):
        clock = FakeClock()
        t = make_transport(clock=clock)
        calls = {"n": 0}

        def fn():
            calls["n"] += 1
            if calls["n"] == 1:
                raise E.ApiError(E.QUOTA_RATE, 429, [], "", retry_after=30)
            return 1

        t.call(fn)
        self.assertEqual(clock.slept, [30.0])

    def test_no_retry_for_bad_request_and_permission(self):
        for cat, status in ((E.BAD_REQUEST, 400), (E.PERMISSION, 403), (E.NOT_FOUND, 404)):
            t = make_transport()
            calls = {"n": 0}

            def fn():
                calls["n"] += 1
                raise api_error(cat, status)

            with self.assertRaises(E.ApiError):
                t.call(fn)
            self.assertEqual(calls["n"], 1, cat)

    def test_total_time_cap(self):
        clock = FakeClock()
        t = make_transport(clock=clock, max_total=5)
        calls = {"n": 0}

        def fn():
            calls["n"] += 1
            raise api_error(E.TRANSIENT, 500)

        with self.assertRaises(E.ApiError):
            t.call(fn)
        self.assertLessEqual(sum(clock.slept), 5)

    def test_auth_required_propagates(self):
        t = make_transport()

        def fn():
            raise E.AuthRequired()

        with self.assertRaises(E.AuthRequired):
            t.call(fn)

    def test_budget_max_requests(self):
        t = make_transport(budget=Budget(max_requests=2))
        t.call(lambda: 1)
        t.call(lambda: 1)
        with self.assertRaises(E.StopRun):
            t.call(lambda: 1)

    def test_key_host_whitelist(self):
        self.assertTrue(check_key_host("https://www.googleapis.com/pagespeedonline/v5/runPagespeed?url=x"))
        self.assertTrue(check_key_host("https://chromeuxreport.googleapis.com/v1/records:queryRecord"))
        for bad in ("https://evil.example/pagespeedonline/", "http://chromeuxreport.googleapis.com/v1/",
                    "https://www.googleapis.com/other/"):
            with self.assertRaises(E.ConfigError):
                check_key_host(bad)


class NoRedirectTests(unittest.TestCase):
    """R2：遇到 3xx 不跟隨，避免 X-Goog-Api-Key 被帶到其他主機。用本機 HTTP 伺服器實測。"""

    def test_redirect_is_not_followed(self):
        import http.server
        import threading
        import urllib.request

        from collector.transport import NoRedirectHandler, no_redirect_opener

        hits = []

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                hits.append((self.path, self.headers.get("X-Goog-Api-Key")))
                if self.path == "/start":
                    self.send_response(302)
                    self.send_header("Location", f"http://127.0.0.1:{self.server.server_port}/elsewhere")
                    self.end_headers()
                else:
                    self.send_response(200)
                    self.end_headers()
                    self.wfile.write(b"{}")

            def log_message(self, *a):
                pass

        server = http.server.HTTPServer(("127.0.0.1", 0), Handler)
        t = threading.Thread(target=server.serve_forever, daemon=True)
        t.start()
        try:
            req = urllib.request.Request(f"http://127.0.0.1:{server.server_port}/start",
                                         headers={"X-Goog-Api-Key": "FAKEKEY"})
            with self.assertRaises(E.ApiError) as cm:
                no_redirect_opener().open(req, timeout=5)
            self.assertIn("redirect", cm.exception.reasons)
            self.assertEqual([h[0] for h in hits], ["/start"])     # 沒有去第二個網址
        finally:
            server.shutdown()
            server.server_close()
        self.assertTrue(any(isinstance(h, NoRedirectHandler) for h in no_redirect_opener().handlers))

    def test_http_json_uses_no_redirect_opener_by_default(self):
        from unittest import mock

        from collector import transport

        class Sentinel(Exception):
            pass

        class FakeOpener:
            def open(self, req, timeout=None):
                raise Sentinel()

        # h：header 與 query 兩種 key_mode 都要走不跟隨重新導向的 opener
        for mode in ("header", "query"):
            with mock.patch.object(transport, "no_redirect_opener", return_value=FakeOpener()) as m:
                with self.assertRaises(Sentinel):
                    transport.http_json("GET", "https://chromeuxreport.googleapis.com/v1/records:queryRecord",
                                        api_key="FAKEKEY", key_mode=mode)
                m.assert_called_once()

    def test_redirect_error_not_retried(self):
        t = make_transport()
        calls = {"n": 0}

        def fn():
            calls["n"] += 1
            raise E.ApiError(E.UNKNOWN, 302, ["redirect"], "redirect")

        with self.assertRaises(E.ApiError):
            t.call(fn)
        self.assertEqual(calls["n"], 1)


class RateLimiterTests(unittest.TestCase):
    def test_spacing(self):
        clock = FakeClock(0.0)
        rl = RateLimiter(60, clock=clock, sleep=clock.sleep)
        for _ in range(3):
            rl.acquire()
        self.assertEqual(clock.slept, [1.0, 1.0])

    def test_no_sleep_when_spaced(self):
        clock = FakeClock(0.0)
        rl = RateLimiter(60, clock=clock, sleep=clock.sleep)
        rl.acquire()
        clock.t += 5
        rl.acquire()
        self.assertEqual(clock.slept, [])


class BreakerTests(unittest.TestCase):
    def test_opens_after_threshold(self):
        b = CircuitBreaker(3)
        for _ in range(2):
            b.record_failure(E.TRANSIENT)
        self.assertFalse(b.open)
        b.record_failure(E.QUOTA_RATE)
        self.assertTrue(b.open)

    def test_success_resets(self):
        b = CircuitBreaker(3)
        b.record_failure(E.TRANSIENT)
        b.record_failure(E.TRANSIENT)
        b.record_success()
        b.record_failure(E.TRANSIENT)
        self.assertFalse(b.open)

    def test_permission_and_bad_request_not_counted(self):
        b = CircuitBreaker(2)
        b.record_failure(E.TRANSIENT)
        b.record_failure(E.PERMISSION)
        b.record_failure(E.BAD_REQUEST)
        self.assertFalse(b.open)
        self.assertEqual(b.consecutive, 1)


if __name__ == "__main__":
    unittest.main()
