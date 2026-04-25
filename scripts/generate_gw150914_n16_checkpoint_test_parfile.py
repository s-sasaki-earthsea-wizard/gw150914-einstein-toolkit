#!/usr/bin/env python3
"""GW150914 N=16 checkpoint 動作確認用 parfile 生成 (Phase 3c-1, Issue #3).

Phase 3a/3b までは HDF5 1.10.4 の POSIX advisory lock 問題を回避するため
checkpoint を全 off にしていた (詳細は Wiki:
HDF5-Checkpoint-POSIX-Lock-Issue を参照)。Phase 3c の本番 run には
checkpoint が必須のため、本スクリプトで N=16 採用構成
(np=1 × OMP=16 + sphere_inner_radius=77.10 M) のもと、
**checkpoint write と restart が成立するか** を実測する。

検証経路:
  1. write モード:
     - 初期データ + ~4000 iter (約 2h05m) evolve
     - walltime トリガ (2h で 1 個書く) + on_terminate (cctk_itlast 到達で 1 個)
     - 計 2 個の checkpoint が writes される想定
  2. restart モード:
     - 同じ simulation_name → 同じ checkpoint_dir
     - IO::recover = "auto" で最新 checkpoint からロード
     - cctk_itlast を 4500 に伸ばして 500 iter 追加 evolve

仮説:
  np=1 構成なら同時 H5Fcreate が起こらず、POSIX lock 衝突は発生しない。
  本スクリプトで仮説を検証する。
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts.generate_gw150914_n16_parfile import snap_inner_radius  # noqa: E402
from tests.helpers.parfile import generate_par  # noqa: E402


# 共通の checkpoint 関連 overrides。
#   - rpar 原本は autoprobe + on_terminate=yes だが、明示制御するため
#     全パラメータを上書き
#   - checkpoint_dir / recover_dir は ../checkpoint-test に分離
#     (将来の本番 checkpoint と混ざらないよう test 用名に)
COMMON_OVERRIDES: dict[str, object] = {
    "Cactus::terminate": "iteration",
    "CarpetIOHDF5::checkpoint": True,
    "IO::checkpoint_ID": False,
    "IO::checkpoint_dir": "../checkpoint-test",
    "IO::recover_dir": "../checkpoint-test",
    "IO::checkpoint_keep": 2,
    "IO::abort_on_io_errors": True,
}

# write モード固有: clean start + 2 個の ckpt (walltime + on_terminate) を生成
WRITE_MODE_OVERRIDES: dict[str, object] = {
    "IO::recover": "no",
    "IO::checkpoint_every": -1,
    "IO::checkpoint_every_walltime_hours": 2.0,
    "IO::checkpoint_on_terminate": True,
}

# restart モード固有: 既存 ckpt を読み、追加 iter 進化
RESTART_MODE_OVERRIDES: dict[str, object] = {
    "IO::recover": "auto",
    "IO::checkpoint_every": -1,
    "IO::checkpoint_every_walltime_hours": -1,
    "IO::checkpoint_on_terminate": True,
}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--mode",
        choices=("write", "restart"),
        default="write",
        help=(
            "write: clean start + walltime/on_terminate で 2 個の ckpt 書く. "
            "restart: 既存 ckpt から recover して追加 evolve."
        ),
    )
    parser.add_argument(
        "--itlast",
        type=int,
        default=None,
        help=(
            "Cactus::cctk_itlast 上書き値. "
            "省略時の既定: write=4000 (約 2h05m), restart=4500 (write より +500)"
        ),
    )
    parser.add_argument(
        "--simulation-name",
        default="gw150914-n16-checkpoint-test",
        help="IO::out_dir + checkpoint 識別子 (write/restart で同じ値を指定すること)",
    )
    parser.add_argument(
        "--n",
        type=int,
        default=16,
        help="rpar の N (Phase 3c では 16 固定)",
    )
    parser.add_argument(
        "--inner-radius",
        type=float,
        default=77.14,
        help=(
            "Coordinates::sphere_inner_radius [M]. "
            "Phase 3b-ii 採用の 77.10 M (snap 後) を維持"
        ),
    )
    parser.add_argument(
        "--walltime-hours",
        type=float,
        default=3.0,
        help="TerminationTrigger::max_walltime (write は 2h ckpt + α 必要)",
    )
    args = parser.parse_args()

    if args.mode == "write":
        mode_overrides = WRITE_MODE_OVERRIDES
        default_itlast = 4000
    else:
        mode_overrides = RESTART_MODE_OVERRIDES
        default_itlast = 4500

    overrides: dict[str, object] = {**COMMON_OVERRIDES, **mode_overrides}
    overrides["Cactus::cctk_itlast"] = (
        args.itlast if args.itlast is not None else default_itlast
    )

    snapped_radius = snap_inner_radius(args.inner_radius, args.n)
    overrides["Coordinates::sphere_inner_radius"] = snapped_radius

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
        f"(mode={args.mode}, N={args.n}, "
        f"inner_radius=snap({args.inner_radius}→{snapped_radius:.4f}), "
        f"cctk_itlast={overrides['Cactus::cctk_itlast']}, "
        f"recover={overrides['IO::recover']!r})"
    )


if __name__ == "__main__":
    main()
