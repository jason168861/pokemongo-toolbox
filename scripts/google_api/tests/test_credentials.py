import json
import unittest

from collector import credentials as C
from collector import redact as R
from collector.errors import AuthRequired, ConfigError

from .fakes import FAKE_ACCESS, FAKE_API_KEY, FAKE_REFRESH, FAKE_SECRET, TempDir


def token_doc(scopes=None, refresh=FAKE_REFRESH):
    return {"token": FAKE_ACCESS, "refresh_token": refresh, "client_id": "fake-client-id.apps.example",
            "client_secret": FAKE_SECRET, "token_uri": "https://oauth2.example.invalid/token",
            "scopes": list(C.SCOPES) if scopes is None else scopes}


class FakeCreds:
    instances = []

    def __init__(self, info):
        self.info = info
        self.token = info.get("token")
        self.refresh_token = info.get("refresh_token")
        self.valid = False
        self.granted_scopes = None
        self.refresh_calls = 0
        self.fail_with = None
        FakeCreds.instances.append(self)

    @classmethod
    def from_authorized_user_info(cls, info, scopes):
        return cls(info)

    def refresh(self, request):
        self.refresh_calls += 1
        if self.fail_with:
            raise self.fail_with
        self.token = "ya29.NEWtokenAFTERrefresh123456"
        self.valid = True

    def to_json(self):
        d = dict(self.info)
        d["token"] = self.token
        return json.dumps(d)


class FakeFlow:
    last = None

    def __init__(self, creds):
        self.creds = creds
        self.kwargs = None

    @classmethod
    def from_client_secrets_file(cls, path, scopes):
        cls.last_scopes = scopes
        return cls.instance

    def run_local_server(self, **kwargs):
        self.kwargs = kwargs
        FakeFlow.last = self
        return self.creds


class FlowCreds:
    def __init__(self, refresh_token=FAKE_REFRESH, scopes=None):
        self.token = FAKE_ACCESS
        self.refresh_token = refresh_token
        self.granted_scopes = list(C.SCOPES) if scopes is None else scopes
        self.scopes = self.granted_scopes

    def to_json(self):
        return json.dumps({"token": self.token, "refresh_token": self.refresh_token,
                           "scopes": self.granted_scopes})


class ScopeTests(unittest.TestCase):
    def test_exact_three(self):
        C.check_scopes(list(C.SCOPES))
        C.check_scopes(" ".join(C.SCOPES))
        with self.assertRaises(AuthRequired):
            C.check_scopes(list(C.SCOPES) + ["https://www.googleapis.com/auth/adsense"])
        with self.assertRaises(AuthRequired):
            C.check_scopes(list(C.SCOPES)[:2])
        with self.assertRaises(AuthRequired):
            C.check_scopes(None)


class LoadTests(unittest.TestCase):
    def tearDown(self):
        R.clear_registered()

    def write_token(self, tmp, doc):
        (tmp / C.TOKEN_FILE).write_text(json.dumps(doc), encoding="utf-8")

    def test_missing_token(self):
        with TempDir() as tmp:
            with self.assertRaises(AuthRequired):
                C.load_oauth_credentials(tmp, credentials_cls=FakeCreds)

    def test_extra_scope_refused(self):
        with TempDir() as tmp:
            self.write_token(tmp, token_doc(scopes=list(C.SCOPES) + ["https://www.googleapis.com/auth/drive"]))
            with self.assertRaises(AuthRequired):
                C.load_oauth_credentials(tmp, credentials_cls=FakeCreds)

    def test_missing_refresh_token(self):
        with TempDir() as tmp:
            self.write_token(tmp, token_doc(refresh=None))
            with self.assertRaises(AuthRequired):
                C.load_oauth_credentials(tmp, credentials_cls=FakeCreds)

    def test_refresh_registers_new_token_and_saves(self):
        with TempDir() as tmp:
            self.write_token(tmp, token_doc())
            creds = C.load_oauth_credentials(tmp, credentials_cls=FakeCreds, request_factory=lambda: None)
            self.assertEqual(creds.refresh_calls, 1)
            self.assertEqual(R.redact("x ya29.NEWtokenAFTERrefresh123456"), "x ***")
            saved = json.loads((tmp / C.TOKEN_FILE).read_text(encoding="utf-8"))
            self.assertEqual(saved["token"], "ya29.NEWtokenAFTERrefresh123456")
            # 之前載入的祕密值都已登記；client_id 不登記（公開資訊）
            for s in (FAKE_REFRESH, FAKE_SECRET):
                self.assertEqual(R.redact(s), "***")
            self.assertEqual(R.redact("fake-client-id.apps.example"), "fake-client-id.apps.example")

    def test_refresh_error_is_auth_required_without_flow(self):
        try:
            from google.auth.exceptions import RefreshError  # type: ignore
        except ImportError:
            self.skipTest("google-auth 未安裝")
        with TempDir() as tmp:
            self.write_token(tmp, token_doc())
            creds = C.load_oauth_credentials(tmp, credentials_cls=FakeCreds, refresh_now=False)
            creds.fail_with = None
            orig_cls_refresh = FakeCreds.refresh

            def boom(self, request):
                raise RefreshError("invalid_grant: Token has been expired or revoked.")
            FakeCreds.refresh = boom
            try:
                creds2 = C.load_oauth_credentials(tmp, credentials_cls=FakeCreds, refresh_now=False)
                with self.assertRaises(AuthRequired):
                    creds2.refresh(None)
            finally:
                FakeCreds.refresh = orig_cls_refresh
            self.assertIsNone(FakeFlow.last)       # 沒有呼叫授權流程（不會開瀏覽器）

    def test_granted_scopes_checked_after_refresh(self):
        with TempDir() as tmp:
            self.write_token(tmp, token_doc())
            creds = C.load_oauth_credentials(tmp, credentials_cls=FakeCreds, refresh_now=False)
            orig = FakeCreds.refresh

            def refresh_with_extra(self, request):
                self.token = "ya29.ANOTHERtoken1234567890"
                self.granted_scopes = list(C.SCOPES) + ["https://www.googleapis.com/auth/drive"]
            FakeCreds.refresh = refresh_with_extra
            try:
                creds = C.load_oauth_credentials(tmp, credentials_cls=FakeCreds, refresh_now=False)
                with self.assertRaises(AuthRequired):
                    creds.refresh(None)
            finally:
                FakeCreds.refresh = orig

    def test_api_key(self):
        with TempDir() as tmp:
            with self.assertRaises(ConfigError) as cm:
                C.load_api_key(tmp)
            self.assertNotIn("AIza", str(cm.exception))
            (tmp / C.API_KEY_FILE).write_text(FAKE_API_KEY + "\n", encoding="utf-8")
            self.assertEqual(C.load_api_key(tmp), FAKE_API_KEY)
            self.assertEqual(R.redact(FAKE_API_KEY), "***")


class AuthFlowTests(unittest.TestCase):
    def tearDown(self):
        R.clear_registered()
        FakeFlow.last = None

    CLIENT_ID = "123456789012-fakeclientid.apps.googleusercontent.com"

    def write_secret(self, tmp):
        (tmp / C.CLIENT_SECRET_FILE).write_text(json.dumps(
            {"installed": {"client_id": self.CLIENT_ID, "client_secret": FAKE_SECRET}}), encoding="utf-8")

    def test_client_id_not_redacted_but_secret_is(self):
        """client_id 是公開資訊，會出現在授權網址裡；遮掉會讓網址失效（R1）。"""
        with TempDir() as tmp:
            self.write_secret(tmp)
            FakeFlow.instance = FakeFlow(FlowCreds())
            C.run_auth_flow(tmp, flow_cls=FakeFlow)
            url = f"https://accounts.example.invalid/o/oauth2/auth?client_id={self.CLIENT_ID}&scope=x"
            self.assertIn(self.CLIENT_ID, R.redact(url))
            self.assertEqual(R.redact(FAKE_SECRET), "***")

    def test_scope_unchecked_gives_clear_message(self):
        """使用者取消勾選某個權限時，oauthlib 會丟 Warning("Scope has changed ...")。"""
        class ScopeFlow(FakeFlow):
            def run_local_server(self, **kwargs):
                raise Warning('Scope has changed from "a b c" to "a b".')

        with TempDir() as tmp:
            self.write_secret(tmp)
            ScopeFlow.instance = ScopeFlow(FlowCreds())
            with self.assertRaises(AuthRequired) as cm:
                C.run_auth_flow(tmp, flow_cls=ScopeFlow)
            self.assertIn("勾選全部三個權限", str(cm.exception))
            self.assertFalse((tmp / C.TOKEN_FILE).exists())

    def test_other_flow_errors_propagate(self):
        class BrokenFlow(FakeFlow):
            def run_local_server(self, **kwargs):
                raise RuntimeError("browser failed")

        with TempDir() as tmp:
            self.write_secret(tmp)
            BrokenFlow.instance = BrokenFlow(FlowCreds())
            with self.assertRaises(RuntimeError):
                C.run_auth_flow(tmp, flow_cls=BrokenFlow)

    def test_flow_params(self):
        with TempDir() as tmp:
            self.write_secret(tmp)
            FakeFlow.instance = FakeFlow(FlowCreds())
            C.run_auth_flow(tmp, flow_cls=FakeFlow)
            self.assertEqual(sorted(FakeFlow.last_scopes), sorted(C.SCOPES))
            kw = FakeFlow.last.kwargs
            self.assertEqual(kw.get("access_type"), "offline")
            self.assertEqual(kw.get("prompt"), "consent")
            self.assertNotIn("include_granted_scopes", kw)
            self.assertTrue((tmp / C.TOKEN_FILE).exists())

    def test_no_refresh_token_not_saved(self):
        with TempDir() as tmp:
            self.write_secret(tmp)
            FakeFlow.instance = FakeFlow(FlowCreds(refresh_token=None))
            with self.assertRaises(AuthRequired):
                C.run_auth_flow(tmp, flow_cls=FakeFlow)
            self.assertFalse((tmp / C.TOKEN_FILE).exists())

    def test_wrong_scopes_not_saved(self):
        with TempDir() as tmp:
            self.write_secret(tmp)
            FakeFlow.instance = FakeFlow(FlowCreds(scopes=list(C.SCOPES) + ["https://www.googleapis.com/auth/drive"]))
            with self.assertRaises(AuthRequired):
                C.run_auth_flow(tmp, flow_cls=FakeFlow)
            self.assertFalse((tmp / C.TOKEN_FILE).exists())

    def test_missing_client_secret(self):
        with TempDir() as tmp:
            with self.assertRaises(ConfigError):
                C.run_auth_flow(tmp, flow_cls=FakeFlow)


if __name__ == "__main__":
    unittest.main()
