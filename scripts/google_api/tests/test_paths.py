import os
import shutil
import subprocess
import unittest
from pathlib import Path

from collector import paths as P
from collector.errors import ConfigError

from .fakes import FakeGit, TempDir


def is_cmd(name):
    return lambda args: name in args


class ResolveTests(unittest.TestCase):
    def test_order_cli_env_git(self):
        with TempDir() as tmp:
            git = FakeGit([(is_cmd("--git-common-dir"), (0, str(tmp / "repo" / ".git") + "\n", ""))])
            self.assertEqual(P.resolve_data_dir(str(tmp / "cli"), {"POGOKIT_DATA_DIR": str(tmp / "env")}, tmp, git),
                             (tmp / "cli").resolve())
            self.assertEqual(P.resolve_data_dir(None, {"POGOKIT_DATA_DIR": str(tmp / "env")}, tmp, git),
                             (tmp / "env").resolve())
            self.assertEqual(P.resolve_data_dir(None, {}, tmp, git),
                             (tmp / "repo" / ".private" / "google_data").resolve())

    def test_git_failure(self):
        git = FakeGit(default=(128, "", "not a repo"))
        with self.assertRaises(ConfigError):
            P.resolve_data_dir(None, {}, Path("."), git)

    def test_safe_join(self):
        with TempDir() as tmp:
            self.assertEqual(P.safe_join(tmp, "a", "b.csv"), (tmp / "a" / "b.csv").resolve())
            with self.assertRaises(ValueError):
                P.safe_join(tmp, "..", "x")
            with self.assertRaises(ValueError):
                P.safe_join(tmp, "/etc/passwd")

    def test_default_cred_dir_uses_localappdata(self):
        old = os.environ.get("LOCALAPPDATA")
        try:
            os.environ["LOCALAPPDATA"] = str(Path("C:/fake/local"))
            self.assertEqual(P.default_cred_dir(), Path("C:/fake/local") / "PogoKit" / "google")
        finally:
            if old is None:
                os.environ.pop("LOCALAPPDATA", None)
            else:
                os.environ["LOCALAPPDATA"] = old


class CheckDataDirMockTests(unittest.TestCase):
    def git_for(self, top, ignore_code=0, ls_out=""):
        return FakeGit([
            (is_cmd("--show-toplevel"), (0, str(top) + "\n", "")),
            (is_cmd("check-ignore"), (ignore_code, "", "")),
            (is_cmd("ls-files"), (0, ls_out, "")),
        ])

    def test_pass_creates_dir_and_inner_gitignore_after_check(self):
        with TempDir() as tmp:
            data = tmp / ".private" / "google_data"
            seen = {}

            def on_check_ignore(args):
                if "check-ignore" in args:
                    seen.setdefault("exists_at_check", data.exists())
                    seen["path"] = args[-1]
                    return True
                return False

            git = FakeGit([
                (is_cmd("--show-toplevel"), (0, str(tmp) + "\n", "")),
                (on_check_ignore, (0, "", "")),
                (is_cmd("ls-files"), (0, "", "")),
            ])
            info = P.check_data_dir(data, git)
            self.assertTrue(info["created"])
            self.assertFalse(seen["exists_at_check"])           # 先檢查，通過後才建立
            self.assertTrue(seen["path"].endswith("google_data/manifest.json"))   # 用資料夾內的檔案路徑
            self.assertEqual((data / ".gitignore").read_text(encoding="utf-8"), P.INNER_GITIGNORE)

    def test_not_ignored_refused_and_nothing_created(self):
        with TempDir() as tmp:
            data = tmp / ".private" / "google_data"
            with self.assertRaises(ConfigError):
                P.check_data_dir(data, self.git_for(tmp, ignore_code=1))
            self.assertFalse(data.exists())

    def test_check_ignore_error_refused(self):
        with TempDir() as tmp:
            with self.assertRaises(ConfigError):
                P.check_data_dir(tmp / "d", self.git_for(tmp, ignore_code=128))

    def test_tracked_files_refused(self):
        with TempDir() as tmp:
            with self.assertRaises(ConfigError):
                P.check_data_dir(tmp / ".private" / "google_data", self.git_for(tmp, ls_out=".private/google_data/x\n"))

    def test_outside_repo_allowed(self):
        with TempDir() as tmp:
            git = FakeGit([(is_cmd("--show-toplevel"), (128, "", "not a git repository"))])
            info = P.check_data_dir(tmp / "data", git)
            self.assertTrue(info["outside_repo"])

    def test_git_missing_refused(self):
        with TempDir() as tmp:
            with self.assertRaises(ConfigError):
                P.check_data_dir(tmp / "data", FakeGit(default=(127, "", "")))

    def test_worktrees_dir_refused(self):
        with TempDir() as tmp:
            with self.assertRaises(ConfigError):
                P.check_data_dir(tmp / ".private" / "worktrees" / "x" / "data", self.git_for(tmp))

    def test_inner_gitignore_repaired(self):
        with TempDir() as tmp:
            data = tmp / ".private" / "google_data"
            data.mkdir(parents=True)
            (data / ".gitignore").write_text("wrong\n", encoding="utf-8")
            info = P.check_data_dir(data, self.git_for(tmp))
            self.assertTrue(info["inner_gitignore_fixed"])
            self.assertEqual((data / ".gitignore").read_text(encoding="utf-8"), P.INNER_GITIGNORE)

    def test_cred_dir_rules(self):
        with TempDir() as tmp:
            data = tmp / "data"
            with self.assertRaises(ConfigError):
                P.check_cred_dir(data, data, FakeGit())
            with self.assertRaises(ConfigError):
                P.check_cred_dir(data / "creds", data, FakeGit())
            git_not_ignored = self.git_for(tmp, ignore_code=1)
            with self.assertRaises(ConfigError):
                P.check_cred_dir(tmp / "creds", data, git_not_ignored)
            git_outside = FakeGit([(is_cmd("--show-toplevel"), (128, "", ""))])
            self.assertFalse(P.check_cred_dir(tmp / "creds", data, git_outside)["in_repo"])


@unittest.skipUnless(shutil.which("git"), "找不到 git")
class GitIntegrationTests(unittest.TestCase):
    """用真的臨時 git repo 驗證 check-ignore 行為（審查第 4 點）。"""

    def git(self, *args, cwd):
        return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=True)

    def make_repo(self, tmp, ignore_line=".private/\n", commit=False):
        repo = tmp / "repo"
        repo.mkdir()
        self.git("init", "-q", cwd=repo)
        (repo / ".gitignore").write_text(ignore_line, encoding="utf-8")
        (repo / "README.md").write_text("x", encoding="utf-8")
        if commit:
            # 臨時測試 repo 自己的設定（不影響使用者的 repo）
            self.git("config", "user.email", "test@example.invalid", cwd=repo)
            self.git("config", "user.name", "test", cwd=repo)
            self.git("config", "commit.gpgsign", "false", cwd=repo)
            self.git("add", ".", cwd=repo)
            self.git("commit", "-q", "-m", "init", cwd=repo)
        return repo

    def test_ignored_before_and_after_creation(self):
        with TempDir() as tmp:
            repo = self.make_repo(tmp)
            data = repo / ".private" / "google_data"
            info = P.check_data_dir(data)          # 資料夾不存在
            self.assertTrue(info["created"])
            info2 = P.check_data_dir(data)         # 資料夾已存在
            self.assertFalse(info2["created"])
            rules = P.describe_ignore_rules(data)
            self.assertTrue(rules["root_rule_hit"])
            self.assertTrue(rules["inner_rule_hit"])

    def test_not_ignored_refused(self):
        with TempDir() as tmp:
            repo = self.make_repo(tmp, ignore_line="node_modules/\n")
            with self.assertRaises(ConfigError):
                P.check_data_dir(repo / ".private" / "google_data")
            self.assertFalse((repo / ".private" / "google_data").exists())

    def test_tracked_file_refused(self):
        with TempDir() as tmp:
            repo = self.make_repo(tmp)
            data = repo / ".private" / "google_data"
            data.mkdir(parents=True)
            (data / "tracked.csv").write_text("x", encoding="utf-8")
            self.git("add", "-f", ".private/google_data/tracked.csv", cwd=repo)
            with self.assertRaises(ConfigError):
                P.check_data_dir(data)

    def test_inner_gitignore_alone_still_protects(self):
        with TempDir() as tmp:
            repo = self.make_repo(tmp)
            data = repo / ".private" / "google_data"
            P.check_data_dir(data)
            # 模擬使用者把根目錄的忽略規則拿掉
            (repo / ".gitignore").write_text("node_modules/\n", encoding="utf-8")
            info = P.check_data_dir(data)
            self.assertFalse(info["outside_repo"])
            rules = P.describe_ignore_rules(data)
            self.assertFalse(rules["root_rule_hit"])
            self.assertTrue(rules["inner_rule_hit"])
            (data / "x.csv").write_text("a", encoding="utf-8")
            status = self.git("status", "--porcelain", "--untracked-files=all", cwd=repo).stdout
            self.assertNotIn("google_data", status)

    def test_worktree_resolves_to_main_repo(self):
        with TempDir() as tmp:
            repo = self.make_repo(tmp, commit=True)
            wt = tmp / "repo" / ".private" / "worktrees" / "w"
            self.git("worktree", "add", "-q", str(wt), cwd=repo)
            script_dir = wt / "scripts"
            script_dir.mkdir(parents=True, exist_ok=True)
            data = P.resolve_data_dir(None, {}, script_dir)
            self.assertEqual(os.path.normcase(str(data)),
                             os.path.normcase(str((repo / ".private" / "google_data").resolve())))


if __name__ == "__main__":
    unittest.main()
