import json
import socket
import unittest

from collector import errors as E

from .fakes import make_http_error


class ClassifyTests(unittest.TestCase):
    def test_table(self):
        cases = [
            (401, [], E.AUTH),
            (403, [], E.PERMISSION),
            (403, ["forbidden"], E.PERMISSION),
            (403, ["rateLimitExceeded"], E.QUOTA_RATE),
            (403, ["userRateLimitExceeded"], E.QUOTA_RATE),
            (403, ["dailyLimitExceeded"], E.QUOTA_DAILY),
            (403, ["quotaExceeded"], E.QUOTA_DAILY),
            (429, [], E.QUOTA_RATE),
            (429, ["RESOURCE_EXHAUSTED"], E.QUOTA_RATE),
            (500, [], E.TRANSIENT),
            (503, [], E.TRANSIENT),
            (400, [], E.BAD_REQUEST),
            (404, [], E.NOT_FOUND),
        ]
        for status, reasons, want in cases:
            self.assertEqual(E.classify(status, reasons), want, (status, reasons))

    def test_daily_by_message(self):
        self.assertEqual(E.classify(429, ["RESOURCE_EXHAUSTED"], "Exhausted property tokens per day"), E.QUOTA_DAILY)

    def test_timeouts_are_transient(self):
        for exc in (socket.timeout("t"), TimeoutError("t"), ConnectionError("c")):
            err = E.from_exception(exc)
            self.assertIsInstance(err, E.ApiError)
            self.assertEqual(err.category, E.TRANSIENT)

    def test_non_json_error_page(self):
        reasons, msg = E._reasons_from_content(b"<html><body>502 Bad Gateway</body></html>")
        self.assertEqual(reasons, [])
        self.assertIn("502", msg)

    def test_http_error_mapping(self):
        he = make_http_error(403, json.dumps({"error": {"errors": [{"reason": "rateLimitExceeded"}],
                                                        "message": "slow down"}}).encode())
        if he is None:
            self.skipTest("googleapiclient 未安裝")
        err = E.from_exception(he)
        self.assertEqual(err.category, E.QUOTA_RATE)
        he401 = make_http_error(401, b"{}")
        self.assertIsInstance(E.from_exception(he401), E.AuthRequired)
        he_html = make_http_error(502, b"<html>bad gateway</html>")
        self.assertEqual(E.from_exception(he_html).category, E.TRANSIENT)

    def test_refresh_error_is_auth(self):
        try:
            from google.auth.exceptions import RefreshError  # type: ignore
        except ImportError:
            self.skipTest("google-auth 未安裝")
        self.assertIsInstance(E.from_exception(RefreshError("invalid_grant")), E.AuthRequired)


if __name__ == "__main__":
    unittest.main()
