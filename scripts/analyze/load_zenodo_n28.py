"""Zenodo N=28 reference データ読み込み (Phase 4 / Issue #4 タスク C1).

GW150914 公式 N=28 シミュレーション結果 (Zenodo 10.5281/zenodo.155394) を
6 SimFactory walltime restart segment 横断で読み込む reader。

データ構造:
    data/GW150914_N28_zenodo/extracted/GW150914_28/
        output-0000/GW150914_28/  (sim time 0 → 246 M)
        output-0001/GW150914_28/  (246 → 517 M)
        ...
        output-0005/GW150914_28/  (post-merger ringdown 後期)

Stage A 比較は output-0000 単独で完結するが、本 reader は 6 segment
全てを concat して返す (時間方向に切れ目なし、SimFactory restart 慣習)。

主要 API (詳細は ``_simdir`` モジュール):
    find_segments(base) -> list[Path]
    load_bh_diagnostics(base, ah_index) -> np.ndarray
    load_qlm_scalars(base) -> np.ndarray
    load_psi4_mode(base, l, m, r) -> (t, re, im)

ψ4 抽出半径 (Zenodo 実測): [100, 115, 136, 167, 214, 300, 500] M
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

from . import _simdir

# Zenodo データのデフォルト top-level path (sim_dir.name = "GW150914_28")
DEFAULT_ZENODO_BASE = Path("data/GW150914_N28_zenodo/extracted/GW150914_28")
EXTRACTION_RADII = [100.0, 115.0, 136.0, 167.0, 214.0, 300.0, 500.0]


def find_segments(zenodo_base: Path | str = DEFAULT_ZENODO_BASE) -> list[Path]:
    """Zenodo データの segment 内側 dir 一覧を返す (output-0000 から順)."""
    return _simdir.find_segments(zenodo_base)


def load_bh_diagnostics(
    zenodo_base: Path | str = DEFAULT_ZENODO_BASE,
    ah_index: int = 1,
) -> np.ndarray:
    """``BH_diagnostics.ah{1,2}.gp`` を全 segment 横断で読み込み.

    Args:
        zenodo_base: Zenodo top-level dir (デフォルト: ``data/.../GW150914_28``)。
        ah_index: 1 または 2 (BH1 / BH2)。

    Returns:
        ``(N_t, 40)`` 程度の 2D array。
    """
    return _simdir.load_bh_diagnostics(zenodo_base, ah_index)


def load_qlm_scalars(zenodo_base: Path | str = DEFAULT_ZENODO_BASE) -> np.ndarray:
    """``quasilocalmeasures-qlm_scalars..asc`` を全 segment 横断で読み込み."""
    return _simdir.load_qlm_scalars(zenodo_base)


def load_psi4_mode(
    zenodo_base: Path | str = DEFAULT_ZENODO_BASE,
    l: int = 2,
    m: int = 2,
    r: float = 100.0,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """``mp_psi4.h5`` の指定モード × 抽出半径を全 segment 横断で読み込み.

    Returns:
        ``(t, re, im)`` の 3 配列。
    """
    return _simdir.load_psi4_mode(zenodo_base, l, m, r)


def list_psi4_radii(
    zenodo_base: Path | str = DEFAULT_ZENODO_BASE,
    l: int = 2,
    m: int = 2,
) -> list[float]:
    """指定 (l, m) で利用可能な抽出半径一覧."""
    return _simdir.list_psi4_radii(zenodo_base, l, m)
