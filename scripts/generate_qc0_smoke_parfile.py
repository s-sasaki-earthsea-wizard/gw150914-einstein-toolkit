#!/usr/bin/env python3
"""qc0-mclachlan smoke parfile 生成スクリプト (Phase 3a feasibility 用).

公式 qc0-mclachlan.par に以下の overrides を適用して
``par/qc0-mclachlan/generated/qc0-mclachlan-smoke.par`` を生成する:

- ``Cactus::terminate = "iteration"`` + ``cctk_itlast = 10``:
  初期データ + 数 iteration の evolution まででクリーン終了
- checkpoint 系を全て無効化:
  Phase 3a の段階では MPI + HDF5 1.10.4 の checkpoint 書き込みが
  ``errno=11`` で失敗するため回避 (Phase 3c で本格対応予定)
- ``IO::recover = "no"``:
  古い checkpoint の誤認識を防ぐ
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tests.helpers.parfile import apply_overrides  # noqa: E402

SRC = ROOT / "par/qc0-mclachlan/qc0-mclachlan.par"
DST = ROOT / "par/qc0-mclachlan/generated/qc0-mclachlan-smoke.par"

OVERRIDES: dict[str, object] = {
    "Cactus::terminate": "iteration",
    "Cactus::cctk_itlast": 10,
    "IO::recover": "no",
    "IO::checkpoint_ID": False,
    "IO::checkpoint_every": -1,
    "IO::checkpoint_on_terminate": False,
    "IOHDF5::checkpoint": False,
    "IO::checkpoint_every_walltime_hours": -1,
}


def main() -> None:
    if not SRC.exists():
        sys.exit(
            f"qc0 parfile が見つかりません: {SRC}\n"
            "  `make fetch-qc0` で取得してから再実行してください"
        )
    DST.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SRC, DST)
    apply_overrides(DST, OVERRIDES)
    print(f"生成しました: {DST.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
