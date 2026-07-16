#!/usr/bin/env python3
"""交易清單一鍵更新:pull PokeMiners → build_data → fetch_assets → 提示 commit。

遊戲更新後(新寶可夢/造型/異色/背卡/可極巨化名單…)跑這支就好,不用記順序。

用法:
    python update.py              # 完整流程,結尾印出 git 指令讓你自己 commit
    python update.py --commit     # 跑完自動 git add/commit/push(trade-list/data 與 assets)
    python update.py --skip-pull  # 跳過更新本機 PokeMiners(離線或剛 pull 過時用)

環境:
    POGO_ASSETS  本機 PokeMiners pogo_assets 路徑(預設 ..\\..\\pogo_assets)
需求:build_data.py 需 cloudscraper、fetch_assets.py 需 Pillow
    pip install cloudscraper Pillow
"""
import argparse, os, subprocess, sys, time

# Windows 主控台:確保能輸出中文與符號、並啟用 ANSI 顏色
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass
if os.name == "nt":
    os.system("")   # 啟用 VT 處理,讓 \033[..m 顏色生效

HERE = os.path.dirname(os.path.abspath(__file__))                 # trade-list/
REPO = os.path.dirname(HERE)                                       # pokemongo-toolbox/
POGO_ASSETS = os.environ.get(
    "POGO_ASSETS",
    os.path.abspath(os.path.join(REPO, "..", "pogo_assets")),      # 預設與 repo 同層
)


def run(title, cmd, cwd=HERE, fatal=True):
    """跑一個步驟,回傳是否成功。fatal=True 時失敗就中止整個流程。"""
    print(f"\n\033[1;36m▶ {title}\033[0m\n  $ {' '.join(cmd)}  (cwd={cwd})", flush=True)
    t = time.time()
    rc = subprocess.run(cmd, cwd=cwd).returncode
    dt = time.time() - t
    if rc == 0:
        print(f"\033[1;32m✔ {title} 完成({dt:.0f}s)\033[0m", flush=True)
        return True
    msg = f"\033[1;31m[X] {title} 失敗(exit {rc})\033[0m"
    if fatal:
        print(msg + " —— 中止。", flush=True)
        sys.exit(rc)
    print(msg + " —— 略過,繼續。", flush=True)
    return False


def check_deps():
    missing = []
    for mod, pip_name in (("cloudscraper", "cloudscraper"), ("PIL", "Pillow")):
        try:
            __import__(mod)
        except ImportError:
            missing.append(pip_name)
    if missing:
        print(f"\033[1;33m⚠ 缺少套件:{', '.join(missing)}\033[0m")
        print(f"  請先執行:  pip install {' '.join(missing)}")
        sys.exit(1)


def git(args):
    return subprocess.run(["git", "-C", REPO, *args], capture_output=True, text=True)


def main():
    ap = argparse.ArgumentParser(description="交易清單資料/圖片一鍵更新")
    ap.add_argument("--commit", action="store_true", help="跑完自動 commit + push")
    ap.add_argument("--skip-pull", action="store_true", help="跳過更新本機 PokeMiners")
    args = ap.parse_args()

    print("=" * 56)
    print(" 交易清單更新流程")
    print(f"  trade-list : {HERE}")
    print(f"  PokeMiners : {POGO_ASSETS}")
    print("=" * 56)

    check_deps()

    # 1) 更新本機 PokeMiners(sprite + 多國語言名稱來源)
    if args.skip_pull:
        print("\n(略過 PokeMiners pull)")
    elif not os.path.isdir(os.path.join(POGO_ASSETS, ".git")):
        print(f"\n\033[1;33m⚠ 找不到 git 倉庫:{POGO_ASSETS}\033[0m")
        print("  無法自動更新 sprite/名稱,將以現有本機資料繼續。")
        print("  (可設定 POGO_ASSETS 環境變數指向你的 pogo_assets clone)")
    else:
        run("更新 PokeMiners(git pull)", ["git", "-C", POGO_ASSETS, "pull", "--ff-only"],
            cwd=POGO_ASSETS, fatal=False)

    # 2) 重建來源資料
    env_note = "" if os.environ.get("POGO_ASSETS") else f"(POGO_ASSETS={POGO_ASSETS})"
    os.environ["POGO_ASSETS"] = POGO_ASSETS
    run(f"重建資料 build_data.py {env_note}", [sys.executable, "build_data.py"])

    # 3) 下載圖片 + 產生縮圖
    run("下載圖片/縮圖 fetch_assets.py", [sys.executable, "fetch_assets.py"])

    # 4) 收尾:commit 或提示
    paths = ["trade-list/data", "trade-list/assets"]
    status = git(["status", "--short", *paths]).stdout.strip()
    if not status:
        print("\n\033[1;32m✔ 全部完成:trade-list/data 與 assets 沒有變更,無需 commit。\033[0m")
        return

    changed = len(status.splitlines())
    print(f"\n\033[1;36m有 {changed} 項變更:\033[0m")
    print(status[:2000])

    if args.commit:
        run("git add", ["git", "-C", REPO, "add", *paths])
        run("git commit", ["git", "-C", REPO, "commit", "-m", "chore(trade-list): 更新資料與圖片"], fatal=False)
        run("git push", ["git", "-C", REPO, "push"], fatal=False)
        print("\n\033[1;32m✔ 已 commit 並 push,線上稍後即會更新。\033[0m")
    else:
        print("\n\033[1;33m下一步:確認無誤後執行\033[0m")
        print("  git add trade-list/data trade-list/assets")
        print('  git commit -m "更新交易清單資料與圖片"')
        print("  git push")
        print("\n(或下次直接:  python update.py --commit )")


if __name__ == "__main__":
    main()
