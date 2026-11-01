import json
import unittest

from collector import redact as R

from .fakes import FAKE_ACCESS, FAKE_API_KEY, FAKE_REFRESH, FAKE_SECRET


class RedactTests(unittest.TestCase):
    def tearDown(self):
        R.clear_registered()

    def test_registered_value(self):
        R.register_secret("my-very-private-value-123")
        self.assertEqual(R.redact("x my-very-private-value-123 y"), "x *** y")

    def test_registered_urlencoded_variant(self):
        R.register_secret("abc/def+ghi=jkl")
        self.assertNotIn("abc%2Fdef", R.redact("v=abc%2Fdef%2Bghi%3Djkl"))

    def test_short_values_not_registered(self):
        R.register_secret("abc")
        self.assertEqual(R.redact("abc"), "abc")

    def test_patterns(self):
        cases = [
            FAKE_API_KEY, FAKE_ACCESS, FAKE_REFRESH, FAKE_SECRET,
            "eyJhbGciOiJSUzI1NiJ9.eyJzdWIiOiIxMjMifQ.c2lnbmF0dXJl",
        ]
        for c in cases:
            out = R.redact(f"before {c} after")
            self.assertNotIn(c, out, c)
            self.assertIn("***", out)

    def test_bearer(self):
        self.assertNotIn("abcdefghijklmnopqrstuvwxyz", R.redact("Authorization: Bearer abcdefghijklmnopqrstuvwxyz"))
        self.assertNotIn("abcdefghijklmnopqrstuvwxyz", R.redact("bearer abcdefghijklmnopqrstuvwxyz"))

    def test_query_params(self):
        for k in ("key", "api_key", "apikey", "access_token", "refresh_token", "client_secret", "token",
                  "id_token", "code"):
            url = f"https://example.invalid/x?a=1&{k}=SECRETVALUE123&b=2"
            out = R.redact(url)
            self.assertNotIn("SECRETVALUE123", out, k)
            self.assertIn("a=1", out)
            self.assertIn("b=2", out)

    def test_json_fields(self):
        for k in ("refresh_token", "access_token", "client_secret", "token", "id_token", "api_key", "code"):
            text = json.dumps({k: "SECRETVALUE123", "other": "keep"})
            out = R.redact(text)
            self.assertNotIn("SECRETVALUE123", out, k)
            self.assertEqual(json.loads(out)["other"], "keep")

    def test_idempotent(self):
        once = R.redact(f"?key={FAKE_API_KEY} {FAKE_ACCESS}")
        self.assertEqual(R.redact(once), once)

    def test_multiple_secrets(self):
        out = R.redact(f"{FAKE_API_KEY} and {FAKE_REFRESH} and {FAKE_SECRET}")
        for s in (FAKE_API_KEY, FAKE_REFRESH, FAKE_SECRET):
            self.assertNotIn(s, out)

    def test_redact_obj_keeps_json_valid(self):
        obj = {"a": "Bearer " + FAKE_ACCESS + "\"}", "nested": [{"t": FAKE_API_KEY}], "n": 3}
        safe = R.redact_obj(obj)
        text = json.dumps(safe)
        self.assertEqual(json.loads(text)["n"], 3)
        self.assertNotIn(FAKE_ACCESS, text)
        self.assertNotIn(FAKE_API_KEY, text)


if __name__ == "__main__":
    unittest.main()
