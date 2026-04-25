#!/usr/bin/env python3
"""GW150914 N=16 feasibility parfile 生成スクリプト (Phase 3b-ii, Issue #9).

公式 GW150914.rpar は N=28 前提で grid 構造が固定されており、N<28 で
そのまま実行すると ``Refinement level 1 contains inter-patch boundaries``
で Carpet::Abort する。

実測 (2026-04-25) でわかった真の原因:
  level-1 box 自体ではなく、Carpet の **prolongation buffer + ghost
  zones** が物理単位で N=28 比 1.75 倍 (h0=2.14 vs 1.22) に膨らみ、
  Llama 多重パッチの inter-patch 境界マーク領域 (Sn>=0) に侵入する
  ことが原因。box を縮小しただけでは不十分 (maxrls=7 でも crash)。

本スクリプトは 2 つの調整パラメータを提供する:
  ``--inner-radius``: Coordinates::sphere_inner_radius を上書きし、
    Cartesian patch を物理的に大きくして buffer を吸収する余裕を作る。
    本質的な解決策。デフォルトは 77.14 M (= 9 × i × h0, 公式 51.4 の 1.5 倍)
  ``--maxrls``: refinement 階層を縮小する補助手段。デフォルトは
    ``None`` (= rpar 原本通り 9)。inner_radius 拡大だけで通れば不要。

その他:
- ``--n 16``: 公式の 57% 解像度
- ``--itlast 0``: TwoPunctures のみ (smoke)
- checkpoint 系全 off (HDF5 1.10.4 の POSIX lock 問題回避、Phase 3a 同様)
"""

from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tests.helpers.parfile import generate_par  # noqa: E402


def snap_inner_radius(target_radius: float, n: int) -> float:
    """``target_radius`` [M] を rpar と同じ ``i × h0`` grid 単位に ceil で snap

    Coordinates/patchsystem.cc は ``2*sphere_inner_radius / h_cartesian`` が
    整数 (= half-integer-multiple of h) であることを要求し、満たさないと
    ``CCTK_WARN(0)`` で MPI_ABORT する。rpar の自然 step は ``i × h0``
    (= 4×h_cart for N=16) で、これに ceil-snap すれば確実に通る。

    rpar 内部の計算式を Python で再現:
      mm = 29/65, rm = mm*1.2, hfm_min = rm/24, h0_min = hfm_min*64
      h0 = h0_min * 24/N, i = N//4
    """
    mm = 29.0 / 65.0  # GW150914: q=36/29 → 1/(1+q)
    rm = mm * 1.0 * 1.2  # ahrm * 1.2
    hfm_min = rm / 24.0
    h0_min = hfm_min * 64.0  # 2^(rlsm-1), rlsm=7
    h0 = h0_min * 24.0 / n
    i_h0 = (n // 4) * h0
    return math.ceil(target_radius / i_h0) * i_h0


# 注意: GW150914.rpar は CarpetIOHDF5 を使う。IOHDF5 は ActiveThorns に無い。
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
        default="gw150914-n16-feasibility",
        help="IO::out_dir と par ファイル名に使われる識別子",
    )
    parser.add_argument(
        "--n",
        type=int,
        default=16,
        help="rpar の N (グリッド最細半径方向セル数). Phase 3b-ii では 16 が基本",
    )
    parser.add_argument(
        "--maxrls",
        type=int,
        default=None,
        help=(
            "Carpet::max_refinement_levels 上書き値 (Issue #9). "
            "省略時は rpar 原本通り 9 (rlsp/rlsm=7)。"
            "8 → rlsp/rlsm=6, 7 → rlsp/rlsm=5。"
            "inner-radius 拡大だけで通る場合は不要"
        ),
    )
    parser.add_argument(
        "--inner-radius",
        type=float,
        default=77.14,
        help=(
            "Coordinates::sphere_inner_radius 上書き値 [M] (Issue #9 本命)。"
            "rpar 原本の N=16 計算値は 51.43 M で buffer が patch 境界に侵入。"
            "デフォルト 77.14 M (= 9 × i × h0 for N=16) で 1.5 倍に拡大。"
            "0 を指定すると上書きなし (rpar 原本値)"
        ),
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
    snapped_radius: float | None = None
    if args.inner_radius > 0:
        snapped_radius = snap_inner_radius(args.inner_radius, args.n)
        overrides["Coordinates::sphere_inner_radius"] = snapped_radius

    dest = ROOT / "par/GW150914/generated"
    par_path = generate_par(
        dest_dir=dest,
        n=args.n,
        simulation_name=args.simulation_name,
        walltime_hours=args.walltime_hours,
        overrides=overrides,
        maxrls=args.maxrls,
    )
    maxrls_str = "default(9)" if args.maxrls is None else str(args.maxrls)
    radius_str = (
        f"snap({args.inner_radius}→{snapped_radius:.4f})"
        if snapped_radius is not None
        else "rpar default"
    )
    print(
        f"生成しました: {par_path.relative_to(ROOT)} "
        f"(N={args.n}, maxrls={maxrls_str}, "
        f"inner_radius={radius_str}, cctk_itlast={args.itlast})"
    )


if __name__ == "__main__":
    main()
