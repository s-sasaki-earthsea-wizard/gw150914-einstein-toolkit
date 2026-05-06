#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
# Copyright (C) 2026 Syota Sasaki
"""GW150914 feasibility smoke parfile 生成スクリプト (Phase 3b, N=28 メモリ計測用).

GW150914.rpar を N=28 で展開し、以下の overrides を適用して
``par/GW150914/generated/gw150914-feasibility.par`` を生成する:

- ``cctk_itlast``: CLI で指定 (デフォルト 0, TwoPunctures のみ)
- ``Cactus::terminate = "iteration"``: 指定 iteration で確実に停止
- checkpoint 系を全て無効化:
  Phase 3a と同じく HDF5 1.10.4 の POSIX lock 問題を避けるため、
  Phase 3c で本格対応するまでは全ての checkpoint を off にする
- ``IO::recover = "no"``: 古い checkpoint の誤認識を防ぐ

rpar の grid 構造は N=28 向けに tuned 済みなので、ここでは rpar 本体は
改変せず overrides のみで feasibility run を構成する。
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tests.helpers.parfile import generate_par  # noqa: E402


# 注意: GW150914.rpar は CarpetIOHDF5 を使っており IOHDF5 は ActiveThorns に無い。
# 従って qc0 の override key (IOHDF5::checkpoint) ではなく CarpetIOHDF5 を指定する。
OVERRIDES: dict[str, object] = {
    "Cactus::terminate": "iteration",
    "IO::recover": "no",
    "IO::checkpoint_ID": False,
    "IO::checkpoint_on_terminate": False,
    "CarpetIOHDF5::checkpoint": False,
}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--itlast",
        type=int,
        default=0,
        help="cctk_itlast (TwoPunctures のみなら 0, 数 iter evolve なら 16 等)",
    )
    parser.add_argument(
        "--simulation-name",
        default="gw150914-feasibility",
        help="IO::out_dir と par ファイル名に使われる識別子",
    )
    parser.add_argument(
        "--n",
        type=int,
        default=28,
        help="rpar の N (グリッド最細半径方向セル数). Phase 3b では 28 固定が基本",
    )
    parser.add_argument(
        "--walltime-hours",
        type=float,
        default=48.0,
        help="TerminationTrigger::max_walltime",
    )
    args = parser.parse_args()

    overrides = dict(OVERRIDES)
    overrides["Cactus::cctk_itlast"] = args.itlast

    dest = ROOT / "par/GW150914/generated"
    par_path = generate_par(
        dest_dir=dest,
        n=args.n,
        simulation_name=args.simulation_name,
        walltime_hours=args.walltime_hours,
        overrides=overrides,
    )
    print(
        f"生成しました: {par_path.relative_to(ROOT)} "
        f"(N={args.n}, cctk_itlast={args.itlast})"
    )


if __name__ == "__main__":
    main()
