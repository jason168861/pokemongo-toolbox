"""測試用的假物件。全部使用假值，不需要任何憑證或網路。"""
import datetime as _dt
import shutil
import tempfile
from pathlib import Path

from collector import errors as E
from collector.breaker import CircuitBreaker
from collector.engine import Context
from collector.runlog import RunLog
from collector.settings import load_settings
from collector.transport import Budget, Transport

FAKE_API_KEY = "AIza" + "F" * 35
FAKE_ACCESS = "ya29.FAKEaccessTOKENvalue1234567890"
FAKE_REFRESH = "1//FAKErefreshTOKENvalue1234567890abcd"
FAKE_SECRET = "GOCSPX-FAKEclientSECRETvalue"
FAKE_ACCOUNT = "accounts/pub-0000000000000000"
FAKE_PROPERTY = "properties/000000000"
FAKE_SITE = "sc-domain:example.com"


class FakeClock:
    def __init__(self, t=1000.0):
        self.t = t
        self.slept = []

    def __call__(self):
        return self.t

    def sleep(self, s):
        self.slept.append(s)
        self.t += s


class NoLimit:
    def __init__(self):
        self.acquired = 0

    def acquire(self):
        self.acquired += 1


class FakeRequest:
    def __init__(self, handler, path, kwargs):
        self.handler = handler
        self.path = path
        self.kwargs = kwargs

    def execute(self, num_retries=0):
        return self.handler(".".join(self.path), self.kwargs)


class _Called:
    def __init__(self, svc, path, kwargs):
        self._svc = svc
        self._path = path
        self._kwargs = kwargs

    def execute(self, num_retries=0):
        self._svc.calls.append((".".join(self._path), self._kwargs))
        return self._svc.handler(".".join(self._path), self._kwargs)

    def __getattr__(self, name):
        if name.startswith("_"):
            raise AttributeError(name)
        return _Node(self._svc, self._path + (name,))


class _Node:
    def __init__(self, svc, path):
        self._svc = svc
        self._path = path

    def __call__(self, **kwargs):
        return _Called(self._svc, self._path, kwargs)


class FakeService:
    """svc.a().b().list(x=1).execute() → handler("a.b.list", {"x": 1})"""

    def __init__(self, handler):
        self.handler = handler
        self.calls = []

    def __getattr__(self, name):
        if name.startswith("_") or name in ("handler", "calls"):
            raise AttributeError(name)
        return _Node(self, (name,))


class FakeGit:
    """依指令決定回傳值。rules: list of (predicate(args) -> bool, (code, out, err))。"""

    def __init__(self, rules=None, default=(0, "", "")):
        self.rules = rules or []
        self.default = default
        self.calls = []

    def __call__(self, args, cwd=None):
        self.calls.append(list(args))
        for pred, result in self.rules:
            if pred(args):
                return result
        return self.default


class TempDir:
    def __enter__(self):
        self.path = Path(tempfile.mkdtemp(prefix="collector-test-"))
        return self.path

    def __exit__(self, *exc):
        shutil.rmtree(self.path, ignore_errors=True)


def make_transport(source="x", clock=None, max_retries=5, max_total=300, budget=None):
    clock = clock or FakeClock()
    return Transport(source, NoLimit(), budget or Budget(), max_retries=max_retries, max_total_seconds=max_total,
                     sleep=clock.sleep, rand=lambda a, b: 1.0, clock=clock)


def make_ctx(data_dir, services=None, end="2026-10-30", dry_run=False, accept_empty=False, settings_override=None):
    settings = load_settings(settings_override or {})
    runlog = RunLog(str(Path(data_dir) / "collection_log.jsonl"), "test")
    transports = {s: make_transport(s) for s in ("adsense", "gsc", "ga4", "psi", "crux")}
    services = services or {}

    def factory(api, version):
        return services[api]

    return Context(data_dir=data_dir, settings=settings, runlog=runlog, end=end, budget=Budget(),
                   transports=transports, service_factory=factory, dry_run=dry_run, accept_empty=accept_empty)


def api_error(category, status=None, message=""):
    return E.ApiError(category, status, [], message)


def make_http_error(status, content=b"", uri="https://example.invalid/"):
    """建立 googleapiclient 的 HttpError；沒裝套件時回傳 None。"""
    try:
        import httplib2  # type: ignore
        from googleapiclient.errors import HttpError  # type: ignore
    except ImportError:
        return None
    resp = httplib2.Response({"status": status})
    resp.reason = "test"
    return HttpError(resp, content, uri=uri)


def d(s):
    return _dt.date.fromisoformat(s)


def breaker(threshold=3):
    return CircuitBreaker(threshold)
