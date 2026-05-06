#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
# Copyright (C) 2026 Syota Sasaki
"""GW150914 N=16 本番 run 用 parfile 生成 (Phase 3c-2/3/4, Issue #3 + #4 D1+D3).

Phase 3c-1 で確立した checkpoint 動作確認構成 (np=1 × OMP=16,
sphere_inner_radius=77.10 M, ../checkpoints bind mount) を踏襲し、staged
validation 方式で 0 → 100 / 1000 / 1700 M を物理時間ベースで終了させる。

各 stage の終端時刻 (M):
  - Stage A: 100 M  (inspiral 早期, ~6.6 h)
  - Stage B: 1000 M (merger + ringdown 数周期, 累計 ~2.7 d)
  - Stage C: 1700 M (公式フル, 累計 ~4.7 d)

Phase 3c-1 の checkpoint test parfile generator との違い:
  - ``Cactus::terminate`` は rpar 原本通り ``"time"`` (= ``cctk_final_time``
    で打ち切り)。checkpoint test は短時間検証のため ``"iteration"`` だった
  - walltime checkpoint trigger は production cadence の 2.0 h (3c-1 では
    両経路を 1 run でカバーするため 0.5 h だった)
  - checkpoint_dir / recover_dir は stage ごとに分離
    (``../checkpoints/gw150914-n16-stage-<a|b|c>``) — 別 stage の ckpt と
    混ざらず、stage 失敗時の cleanup も容易
  - Hamiltonian / Momentum constraint norm の出力を有効化
    (Issue #4 D3, self-consistency 検証用)

restart capability: ``IO::recover = "autoprobe"`` (rpar 原本通り) で同じ
``simulation_name`` を再投入すれば自動的に最新 checkpoint から復帰する。
walltime / OOM / 手動中断のいずれの場合も同じ make ターゲットを再投入で
継続可能。
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts.generate_gw150914_n16_parfile import snap_inner_radius  # noqa: E402
from tests.helpers.parfile import generate_par  # noqa: E402


# Stage ごとの ``cctk_final_time`` (物理時間 M)
STAGE_FINAL_TIMES: dict[str, float] = {
    "A": 100.0,
    "B": 1000.0,
    "C": 1700.0,
}

# Stage ごとの推定 wall time (実測 0.89 sec/iter, dt_it=0.00375 M ベース)
STAGE_WALL_HOURS: dict[str, float] = {
    "A": 6.6,
    "B": 65.5,  # 累計 2.7 d
    "C": 111.4,  # 累計 4.7 d
}


def stage_overrides(
    stage: str,
    simulation_name: str,
    continue_from: str | None = None,
) -> dict[str, object]:
    """Stage 共通の Cactus parameter overrides を返す.

    Args:
        stage: ``"A"`` / ``"B"`` / ``"C"``
        simulation_name: checkpoint_dir の subdir 名にも使われる
        continue_from: 前 stage の checkpoint から継続する場合に指定
            (例: Stage B 投入時に ``"A"`` を渡すと
            ``IO::recover_dir`` を Stage A の ckpt dir に向ける)。
            ``None`` の場合は自 stage の ckpt dir のみを参照。

    Returns:
        apply_overrides() 互換の辞書
    """
    if stage not in STAGE_FINAL_TIMES:
        raise ValueError(
            f"未知の stage: {stage!r} (許容値: {sorted(STAGE_FINAL_TIMES)})"
        )

    ckpt_subdir = f"../checkpoints/{simulation_name}"

    # cross-stage 継続の場合は recover_dir を前 stage に向ける。
    # checkpoint_dir (= 書込み先) は当 stage 用に分離して持つ
    # (= 前 stage の ckpt が誤って上書きされない、stage 別 cleanup が容易).
    if continue_from is None:
        recover_subdir = ckpt_subdir
    else:
        prev = continue_from.upper()
        if prev not in STAGE_FINAL_TIMES:
            raise ValueError(
                f"未知の continue_from: {continue_from!r} "
                f"(許容値: {sorted(STAGE_FINAL_TIMES)})"
            )
        if prev == stage:
            raise ValueError(
                f"continue_from と stage が同じ: {stage} → 自分自身からの recover は不可"
            )
        recover_subdir = f"../checkpoints/gw150914-n16-stage-{prev.lower()}"

    return {
        # 終了条件: rpar 原本通り time モード、cctk_final_time のみ stage 別
        "Cactus::terminate": "time",
        "Cactus::cctk_final_time": STAGE_FINAL_TIMES[stage],
        # checkpoint 設定 (production cadence)
        "CarpetIOHDF5::checkpoint": True,
        "IO::checkpoint_ID": False,
        "IO::checkpoint_dir": ckpt_subdir,
        "IO::recover_dir": recover_subdir,
        "IO::recover": "autoprobe",  # 既存 ckpt があれば自動 recover
        "IO::checkpoint_keep": 2,
        "IO::checkpoint_every": -1,
        "IO::checkpoint_every_walltime_hours": 2.0,
        "IO::checkpoint_on_terminate": True,
        "IO::abort_on_io_errors": True,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--stage",
        choices=("A", "B", "C"),
        required=True,
        help=(
            "実行 stage. A=100 M (inspiral 早期), B=1000 M (merger+ringdown), "
            "C=1700 M (公式フル)"
        ),
    )
    parser.add_argument(
        "--simulation-name",
        default=None,
        help=(
            "IO::out_dir + checkpoint 識別子. "
            "省略時は ``gw150914-n16-stage-<a|b|c>`` (小文字)"
        ),
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
        default=None,
        help=(
            "TerminationTrigger::max_walltime [h]. 省略時は stage 推定値の 1.2 倍"
            " (A=8.0, B=78.6, C=133.7)"
        ),
    )
    parser.add_argument(
        "--continue-from",
        choices=("A", "B"),
        default=None,
        help=(
            "前 stage の checkpoint から継続する場合に指定 (A or B)。"
            "例: Stage B 投入時 ``--continue-from A`` で Stage A の最終 ckpt から evolve 開始。"
            "省略時は当 stage の ckpt dir のみを参照 (= clean start もしくは自 stage の resume)"
        ),
    )
    args = parser.parse_args()

    stage = args.stage
    simulation_name = args.simulation_name or f"gw150914-n16-stage-{stage.lower()}"
    walltime_hours = args.walltime_hours
    if walltime_hours is None:
        walltime_hours = round(STAGE_WALL_HOURS[stage] * 1.2, 1)

    overrides = stage_overrides(stage, simulation_name, continue_from=args.continue_from)
    snapped_radius = snap_inner_radius(args.inner_radius, args.n)
    overrides["Coordinates::sphere_inner_radius"] = snapped_radius

    dest = ROOT / "par/GW150914/generated"
    par_path = generate_par(
        dest_dir=dest,
        n=args.n,
        simulation_name=simulation_name,
        walltime_hours=walltime_hours,
        overrides=overrides,
        enable_constraint_output=True,
    )
    cont_msg = (
        f", continue_from={args.continue_from} "
        f"(recover_dir={overrides['IO::recover_dir']!r})"
        if args.continue_from
        else ""
    )
    print(
        f"生成しました: {par_path.relative_to(ROOT)} "
        f"(stage={stage}, final_time={STAGE_FINAL_TIMES[stage]} M, "
        f"N={args.n}, "
        f"inner_radius=snap({args.inner_radius}→{snapped_radius:.4f}), "
        f"walltime={walltime_hours} h, "
        f"checkpoint_dir={overrides['IO::checkpoint_dir']!r}{cont_msg})"
    )


if __name__ == "__main__":
    main()
