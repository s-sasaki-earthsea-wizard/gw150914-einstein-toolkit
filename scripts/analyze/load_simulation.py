# SPDX-License-Identifier: GPL-2.0-or-later
# Copyright (C) 2026 Syota Sasaki
"""自前 N=16 simulation 出力読み込み (Phase 4 / Issue #4 タスク C2).

自前 run の Cactus 出力 (``simulations/<sim_name>/output-NNNN/<sim_name>/``)
を ``load_zenodo_n28`` と同じ API で読む。Cactus / SimFactory の出力構造は
解像度や run 名によらず同形式なので、低レベル実装は ``_simdir`` モジュール
を共通利用する。

Phase 3c-2 (Stage A 100 M run) 投入後にこの reader を介して比較スクリプト
``compare_stage_a.py`` から呼ばれる。本セッションではユニットテスト用に
Zenodo データを「擬似 N=16」として読ませる動作確認のみ。

主要 API:
    find_segments(sim_dir) -> list[Path]
    load_bh_diagnostics(sim_dir, ah_index) -> np.ndarray
    load_qlm_scalars(sim_dir) -> np.ndarray
    load_psi4_mode(sim_dir, l, m, r) -> (t, re, im)
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

from . import _simdir


def find_segments(sim_dir: Path | str) -> list[Path]:
    """``simulations/<sim_name>`` 配下の segment 内側 dir 一覧."""
    return _simdir.find_segments(sim_dir)


def load_bh_diagnostics(sim_dir: Path | str, ah_index: int = 1) -> np.ndarray:
    """``BH_diagnostics.ah{1,2}.gp`` を全 segment 横断で読み込み.

    Args:
        sim_dir: simulation top-level (例: ``simulations/GW150914_n16``)。
        ah_index: 1 または 2 (BH1 / BH2)。
    """
    return _simdir.load_bh_diagnostics(sim_dir, ah_index)


def load_qlm_scalars(sim_dir: Path | str) -> np.ndarray:
    """``quasilocalmeasures-qlm_scalars..asc`` を全 segment 横断で読み込み."""
    return _simdir.load_qlm_scalars(sim_dir)


def load_psi4_mode(
    sim_dir: Path | str,
    l: int = 2,
    m: int = 2,
    r: float = 100.0,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """``mp_psi4.h5`` の指定モード × 抽出半径を全 segment 横断で読み込み."""
    return _simdir.load_psi4_mode(sim_dir, l, m, r)


def list_psi4_radii(
    sim_dir: Path | str,
    l: int = 2,
    m: int = 2,
) -> list[float]:
    """指定 (l, m) で利用可能な抽出半径一覧."""
    return _simdir.list_psi4_radii(sim_dir, l, m)
