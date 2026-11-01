"""PogoKit Google API Data Collector 進入點。

用法：python scripts/google_api/collect.py <指令> [參數]   （說明見同資料夾的 README.md）

第一件事就是安裝 stdout／stderr／warnings 的遮蔽，之後才載入任何 Google 套件。
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from collector import runlog  # noqa: E402

runlog.install_stream_guards()

from collector.cli import main  # noqa: E402

if __name__ == "__main__":
    code = main()
    try:
        sys.stdout.flush()
        sys.stderr.flush()
    except Exception:
        pass
    sys.exit(code)
