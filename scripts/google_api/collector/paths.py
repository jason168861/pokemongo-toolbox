"""資料目錄與憑證目錄的解析與安全檢查（設計 §7.1、§7.3）。

git 指令一律用參數列表呼叫（不經過 shell），runner 可以注入，方便測試。
"""
import os
import subprocess
from pathlib import Path

from .errors import ConfigError

INNER_GITIGNORE = "# 由 PogoKit Google Data Collector 自動產生：本資料夾的內容一律不進 git。\n*\n"
PROBE_FILE = "manifest.json"
TOKEN_FILE = "token.json"


def default_git_runner(args, cwd=None):
    """回傳 (exit_code, stdout, stderr)。找不到 git 時回傳 127。"""
    try:
        p = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=30)
        return p.returncode, p.stdout, p.stderr
    except FileNotFoundError:
        return 127, "", "git not found"
    except subprocess.TimeoutExpired:
        return 124, "", "git timeout"


def default_cred_dir():
    base = os.environ.get("LOCALAPPDATA")
    if base:
        return Path(base) / "PogoKit" / "google"
    return Path.home() / "AppData" / "Local" / "PogoKit" / "google"


def _norm(p):
    return os.path.normcase(os.path.abspath(str(p)))


def is_within(child, parent):
    c, p = _norm(child), _norm(parent)
    try:
        return os.path.commonpath([c, p]) == p
    except ValueError:      # Windows 上不同磁碟
        return False


def safe_join(base, *parts):
    """把 parts 接到 base 底下；結果必須仍在 base 內，否則丟 ValueError。"""
    base_p = Path(base).resolve()
    for part in parts:
        part_s = str(part)
        if os.path.isabs(part_s) or part_s.startswith(("/", "\\")):
            raise ValueError(f"不允許絕對路徑：{part_s}")
    target = base_p.joinpath(*[str(p) for p in parts]).resolve()
    if not is_within(target, base_p):
        raise ValueError(f"路徑跳出資料目錄：{target}")
    return target


def nearest_existing(path):
    p = Path(path).resolve()
    while not p.exists():
        if p.parent == p:
            return p
        p = p.parent
    return p


def main_repo_root(script_dir, git=default_git_runner):
    """由 --git-common-dir 推出主目錄（從 worktree 執行時也會得到主目錄，不是 worktree）。"""
    code, out, err = git(["-C", str(script_dir), "rev-parse", "--path-format=absolute", "--git-common-dir"])
    if code != 0 or not out.strip():
        raise ConfigError("無法用 git 找到主目錄；請用 --data-dir 或環境變數 POGOKIT_DATA_DIR 指定資料目錄。")
    common = Path(out.strip())
    if common.name != ".git":
        raise ConfigError(f"git common dir 不是 .git 資料夾，無法推出主目錄：{common}")
    return common.parent.resolve()


def resolve_data_dir(cli_value=None, env=None, script_dir=None, git=default_git_runner):
    env = os.environ if env is None else env
    if cli_value:
        return Path(cli_value).resolve()
    if env.get("POGOKIT_DATA_DIR"):
        return Path(env["POGOKIT_DATA_DIR"]).resolve()
    if script_dir is None:
        raise ConfigError("無法決定資料目錄。")
    return (main_repo_root(script_dir, git) / ".private" / "google_data").resolve()


def worktree_toplevel(path, git=default_git_runner):
    """path 所在的 git 工作樹根目錄；不在任何工作樹內時回傳 None。git 無法執行時丟 ConfigError。"""
    start = nearest_existing(path)
    if start.is_file():
        start = start.parent
    code, out, err = git(["-C", str(start), "rev-parse", "--show-toplevel"])
    if code == 0 and out.strip():
        return Path(out.strip()).resolve()
    if code in (127, 124):
        raise ConfigError("無法執行 git，不能確認路徑是否被 git 忽略，拒絕寫入。")
    return None


def _rel(path, top):
    rel = os.path.relpath(str(Path(path).resolve()), str(top))
    if rel.startswith(".."):
        raise ConfigError(f"路徑不在工作樹內：{path}")
    return rel.replace("\\", "/")


def _inside_worktrees_dir(path):
    parts = [p.lower() for p in Path(path).resolve().parts]
    for i in range(len(parts) - 1):
        if parts[i] == ".private" and parts[i + 1] == "worktrees":
            return True
    return False


def check_ignored(top, rel_file, git=default_git_runner):
    code, out, err = git(["-C", str(top), "check-ignore", "-q", "--", rel_file])
    if code == 0:
        return True
    if code == 1:
        return False
    raise ConfigError(f"git check-ignore 失敗（exit {code}），拒絕寫入。")


def ignore_sources(top, rel_file, git=default_git_runner):
    """回傳命中的規則來源（.gitignore 路徑），給 check 指令顯示用。"""
    code, out, err = git(["-C", str(top), "check-ignore", "-v", "--", rel_file])
    if code != 0 or not out.strip():
        return None
    first = out.strip().splitlines()[0]
    return first.split(":", 1)[0]


def check_data_dir(data_dir, git=default_git_runner, create=True):
    """寫入前的檢查（設計 §7.3）。通過時回傳資訊 dict；不通過丟 ConfigError。

    順序：worktrees 禁區 → 是否在工作樹內 → check-ignore（資料夾內的檔案路徑）→ ls-files 為空
    → （通過後）建立資料夾、寫入內層 .gitignore。
    """
    data_dir = Path(data_dir).resolve()
    info = {"data_dir": str(data_dir), "outside_repo": False, "toplevel": None,
            "created": False, "inner_gitignore_fixed": False}
    if _inside_worktrees_dir(data_dir):
        raise ConfigError("資料目錄不可以位在 .private/worktrees/ 底下（worktree 的 .private/ 不會被 git 忽略）。")

    top = worktree_toplevel(data_dir, git)
    if top is None:
        info["outside_repo"] = True
    else:
        info["toplevel"] = str(top)
        rel_file = _rel(data_dir / PROBE_FILE, top)
        if not check_ignored(top, rel_file, git):
            raise ConfigError(f"資料目錄沒有被 git 忽略，拒絕寫入：{data_dir}")
        rel_dir = _rel(data_dir, top)
        code, out, err = git(["-C", str(top), "ls-files", "--", rel_dir])
        if code != 0:
            raise ConfigError(f"git ls-files 失敗（exit {code}），拒絕寫入。")
        if out.strip():
            raise ConfigError("資料目錄內有被 git 追蹤的檔案，拒絕寫入。請先處理這些檔案。")

    if create:
        if not data_dir.exists():
            data_dir.mkdir(parents=True)
            info["created"] = True
        gi = data_dir / ".gitignore"
        current = gi.read_text(encoding="utf-8") if gi.exists() else None
        if current != INNER_GITIGNORE:
            tmp = data_dir / ".gitignore.tmp"
            tmp.write_text(INNER_GITIGNORE, encoding="utf-8", newline="\n")
            os.replace(tmp, gi)
            info["inner_gitignore_fixed"] = True
    return info


def describe_ignore_rules(data_dir, git=default_git_runner):
    """check 指令用：顯示根目錄規則與內層規則是否命中。"""
    data_dir = Path(data_dir).resolve()
    top = worktree_toplevel(data_dir, git)
    if top is None:
        return {"outside_repo": True}
    # 內層 .gitignore 管不到「資料夾本身」，所以對資料夾路徑做 check-ignore，
    # 命中的一定是上層（根目錄）的規則。
    rel_dir = _rel(data_dir, top)
    root_hit = check_ignored(top, rel_dir, git)
    root_src = ignore_sources(top, rel_dir, git) if root_hit else None
    gi = data_dir / ".gitignore"
    inner_ok = gi.exists() and gi.read_text(encoding="utf-8") == INNER_GITIGNORE
    return {"outside_repo": False, "root_rule_hit": root_hit, "root_rule_source": root_src,
            "inner_rule_hit": inner_ok}


def resolve_cred_dir(cli_value=None):
    return Path(cli_value).resolve() if cli_value else default_cred_dir().resolve()


def check_cred_dir(cred_dir, data_dir, git=default_git_runner):
    """cred dir 不可等於或位在 data dir 內；位在工作樹內時 token.json 必須被忽略（設計 §7.1）。"""
    cred_dir = Path(cred_dir).resolve()
    if data_dir is not None and is_within(cred_dir, data_dir):
        raise ConfigError("憑證資料夾不可以和資料目錄相同，也不可以位在資料目錄內。")
    top = worktree_toplevel(cred_dir, git)
    if top is not None:
        rel = _rel(cred_dir / TOKEN_FILE, top)
        if not check_ignored(top, rel, git):
            raise ConfigError("憑證資料夾位在 git 工作樹內而且沒有被忽略，拒絕讀寫憑證。")
    return {"cred_dir": str(cred_dir), "in_repo": top is not None}
