"""Cactus / SimFactory 出力の segment 横断 reader (内部共有モジュール).

Zenodo N=28 reference (10.5281/zenodo.155394) と自前 N=16 run は同じ
Cactus 出力構造 (``<sim_dir>/output-NNNN/<sim_name>/...``) を持つため、
低レベル読み込みロジックをこのモジュールに集約し、上位の
``load_zenodo_n28`` / ``load_simulation`` から共通利用する。

主要 API:
    find_segments(sim_dir) -> list[Path]
    load_bh_diagnostics(sim_dir, ah_index) -> np.ndarray
    load_qlm_scalars(sim_dir) -> np.ndarray
    load_psi4_mode(sim_dir, l, m, r) -> tuple[t, re, im]

各 reader は全 segment を時系列方向に concat し、segment 境界で重複する
iteration を削除する (SimFactory walltime restart は通常重複しないが、
checkpoint からの restart で重複しうるため defensive に対応)。
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Iterable

import h5py
import numpy as np

# QLM 0D ASCII 列インデックス (Python 0-based; inspect_zenodo.py と同期)
QLM_TIME_COL = 8       # 1-based col 9 = time
QLM_IRR_MASS = 27      # 1-based col 28 = qlm_irreducible_mass[0]
QLM_SPIN = 45          # 1-based col 46 = qlm_spin[0]  (J, dimensional)
QLM_MASS = 66          # 1-based col 67 = qlm_mass[0]  (= horizon mass)

# BH_diagnostics.ah[123].gp 列インデックス (Python 0-based)
BH_TIME_COL = 1            # 1-based col 2 = cctk_time
BH_CENTROID_X_COL = 2      # 1-based col 3 = centroid_x
BH_CENTROID_Y_COL = 3      # 1-based col 4 = centroid_y
BH_CENTROID_Z_COL = 4      # 1-based col 5 = centroid_z
BH_M_IRREDUCIBLE_COL = 26  # 1-based col 27 = m_irreducible
BH_AREAL_RADIUS_COL = 27   # 1-based col 28 = areal_radius

# puncturetracker-pt_loc..asc 列インデックス (Python 0-based, GW150914.rpar 仕様)
# CarpetIOASCII 0D format で col 8 = cctk_time、col 9 以降が pt_loc グループ。
# pt_loc は 4 BH × {x, y, z} = 12 components で、x[0..3] → y[0..3] → z[0..3] の順:
#   col 22 = pt_loc_x[0] (BH1.x)、col 23 = pt_loc_x[1] (BH2.x)
#   col 32 = pt_loc_y[0] (BH1.y)、col 33 = pt_loc_y[1] (BH2.y)
#   col 42 = pt_loc_z[0] (BH1.z)、col 43 = pt_loc_z[1] (BH2.z)
# (BH3, BH4 = unused、初期値 0 のまま)
PT_TIME_COL = 8
PT_BH1_X_COL = 22
PT_BH2_X_COL = 23
PT_BH1_Y_COL = 32
PT_BH2_Y_COL = 33
PT_BH1_Z_COL = 42
PT_BH2_Z_COL = 43

PSI4_KEY_PATTERN = re.compile(r"l(-?\d+)_m(-?\d+)_r(\d+(?:\.\d+)?)")


# 単一 segment 判定に使う marker file (これらが直下にあれば flat layout とみなす)
_FLAT_SIMDIR_MARKERS = (
    "mp_psi4.h5",
    "quasilocalmeasures-qlm_scalars..asc",
    "BH_diagnostics.ah1.gp",
)


def find_segments(sim_dir: Path | str) -> list[Path]:
    """``sim_dir`` 配下の segment 内側ディレクトリ一覧を返す.

    2 種類のレイアウトに対応する:

    1. **SimFactory 多 segment レイアウト** (Zenodo N=28 など):
       ``<sim_dir>/output-NNNN/<sim_name>/...`` — walltime restart の
       segment 単位で並ぶ
    2. **単一 Cactus run の flat レイアウト** (Phase 3c-2/3/4 自前 N=16):
       ``<sim_dir>/...`` — 直下に出力ファイルが並ぶ

    後者は ``output-*`` サブディレクトリが存在せず、かつ
    ``mp_psi4.h5`` / ``quasilocalmeasures-qlm_scalars..asc`` /
    ``BH_diagnostics.ah1.gp`` のいずれかが直下に存在する場合に
    「単一 virtual segment」として ``[sim_dir]`` を返す。

    Args:
        sim_dir: simulation ルート (e.g. ``data/.../GW150914_28``,
            ``~/gw150914-output/gw150914-n16-stage-a``)。

    Returns:
        ``output-NNNN`` 順に sort された segment 内側のパスのリスト。
        flat layout の場合は ``[sim_dir]``。空の場合は空リスト。

    Raises:
        FileNotFoundError: ``sim_dir`` が存在しない場合。
    """
    sim_dir = Path(sim_dir)
    if not sim_dir.is_dir():
        raise FileNotFoundError(f"sim_dir not found: {sim_dir}")
    out_dirs = sorted(sim_dir.glob("output-*"))
    segments: list[Path] = []
    for od in out_dirs:
        if not od.is_dir():
            continue
        # 内側に <sim_name> のサブディレクトリが 1 つあるはず。
        # 名前は sim_dir.name と一致するのが慣例だが、Zenodo は
        # 大小区別 / 解像度文字列付きなので、まず名前一致 → fallback で
        # 唯一のサブディレクトリを採用。
        cand = od / sim_dir.name
        if cand.is_dir():
            segments.append(cand)
            continue
        subdirs = [d for d in od.iterdir() if d.is_dir()]
        if len(subdirs) == 1:
            segments.append(subdirs[0])
    if segments:
        return segments
    # flat layout fallback: marker file が直下にあれば sim_dir 自身を 1 segment とみなす
    if any((sim_dir / m).exists() for m in _FLAT_SIMDIR_MARKERS):
        return [sim_dir]
    return []


def _dedup_by_first_col(arr: np.ndarray) -> np.ndarray:
    """1 列目 (cctk_iteration もしくは similar) で重複を除去 (先勝ち).

    SimFactory walltime restart は重複なしが通常だが、checkpoint からの
    restart で iteration が重複しうるため defensive に処理する。
    """
    if arr.size == 0:
        return arr
    _unused, unique_idx = np.unique(arr[:, 0], return_index=True)
    unique_idx.sort()
    return arr[unique_idx]


def _dedup_by_time_array(t: np.ndarray, *cols: np.ndarray) -> tuple[np.ndarray, ...]:
    """時刻配列 ``t`` に基づき重複時刻を除去 (先勝ち).

    psi4 のように iteration カラムを持たない時系列の dedup 用。
    """
    if t.size == 0:
        return (t, *cols)
    _u, unique_idx = np.unique(t, return_index=True)
    unique_idx.sort()
    return tuple(arr[unique_idx] for arr in (t, *cols))


def _concat(arrays: Iterable[np.ndarray]) -> np.ndarray:
    arrays = [a for a in arrays if a.size > 0]
    if not arrays:
        return np.empty((0, 0))
    return np.concatenate(arrays, axis=0)


def load_bh_diagnostics(sim_dir: Path | str, ah_index: int) -> np.ndarray:
    """``BH_diagnostics.ah{1,2,3}.gp`` を全 segment から読み込み concat.

    Args:
        sim_dir: simulation ルート。
        ah_index: 1 / 2 / 3 (BH1 / BH2 / common horizon)。
            ah3 (common) は merger 後にのみ存在し、segment によっては
            ファイルが無い (= empty array)。

    Returns:
        ``(N_t, 40)`` 程度の 2D array。1 列目 = cctk_iteration、
        以降の列インデックスはモジュール定数 ``BH_*_COL`` 参照。

    Raises:
        ValueError: ``ah_index`` が不正、または segment が 1 つも見つからない場合。
        FileNotFoundError: ``sim_dir`` が存在しない場合。
    """
    if ah_index not in (1, 2, 3):
        raise ValueError(f"ah_index must be 1, 2, or 3, got {ah_index}")
    segments = find_segments(sim_dir)
    if not segments:
        raise ValueError(f"no segments found under {sim_dir}")
    arrays: list[np.ndarray] = []
    for seg in segments:
        path = seg / f"BH_diagnostics.ah{ah_index}.gp"
        if not path.exists():
            continue
        a = np.loadtxt(path, comments="#")
        if a.ndim == 1:
            a = a[np.newaxis, :]
        arrays.append(a)
    out = _concat(arrays)
    return _dedup_by_first_col(out) if out.size else out


def load_qlm_scalars(sim_dir: Path | str) -> np.ndarray:
    """``quasilocalmeasures-qlm_scalars..asc`` を全 segment から読み込み concat.

    各行は 1 iteration の 0D 出力。列インデックスはモジュール定数
    ``QLM_*_COL`` 参照。``qlm_spin`` は J (角運動量、次元あり)、
    無次元化は ``χ = J / m_horizon²`` (Kerr 慣習) を呼び出し側で行う。

    Returns:
        ``(N_t, 111)`` の 2D array。空の場合は ``(0, 0)``。
    """
    segments = find_segments(sim_dir)
    if not segments:
        raise ValueError(f"no segments found under {sim_dir}")
    arrays: list[np.ndarray] = []
    for seg in segments:
        path = seg / "quasilocalmeasures-qlm_scalars..asc"
        if not path.exists():
            continue
        a = np.loadtxt(path, comments="#")
        if a.ndim == 1:
            a = a[np.newaxis, :]
        arrays.append(a)
    out = _concat(arrays)
    return _dedup_by_first_col(out) if out.size else out


def load_puncture_tracker(sim_dir: Path | str) -> np.ndarray:
    """``puncturetracker-pt_loc..asc`` を全 segment から読み込み concat.

    軌道角・軌道数の計算に使う (BH centroid と違い puncture は merger 直前まで
    連続 track 可能で、AHFinder の出力頻度に影響されない)。

    Returns:
        ``(N_t, 52)`` の 2D array。列インデックスはモジュール定数
        ``PT_*_COL`` 参照。空の場合は ``(0, 0)``。
    """
    segments = find_segments(sim_dir)
    if not segments:
        raise ValueError(f"no segments found under {sim_dir}")
    arrays: list[np.ndarray] = []
    for seg in segments:
        path = seg / "puncturetracker-pt_loc..asc"
        if not path.exists():
            continue
        a = np.loadtxt(path, comments="#")
        if a.ndim == 1:
            a = a[np.newaxis, :]
        arrays.append(a)
    out = _concat(arrays)
    return _dedup_by_first_col(out) if out.size else out


def chi_dimensionless(j: np.ndarray | float, m_horizon: np.ndarray | float) -> np.ndarray | float:
    """無次元スピン ``χ = J / M_horizon²`` (Kerr 慣習).

    ``m_horizon == 0`` の要素は ``nan`` を返す。スカラー / 配列両対応。
    """
    j_arr = np.asarray(j)
    m_arr = np.asarray(m_horizon)
    with np.errstate(divide="ignore", invalid="ignore"):
        out = np.where(m_arr > 0, j_arr / (m_arr * m_arr), np.nan)
    return out.item() if out.ndim == 0 else out


def load_psi4_mode(
    sim_dir: Path | str,
    l: int,
    m: int,
    r: float,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """``mp_psi4.h5`` の指定 (l, m) モード × 抽出半径 r を全 segment から concat.

    キー命名は ``l<L>_m<M>_r<R>`` で R は実数 (例 ``l2_m2_r100.00``)。
    抽出半径は実測小数点 2 桁丸めで一致させる必要がある。

    Args:
        sim_dir: simulation ルート。
        l, m: 球面調和指数 (l >= 0, |m| <= l)。
        r: 抽出半径 [M] (例 100.0)。Zenodo: ``[100, 115, 136, 167, 214, 300, 500]``。

    Returns:
        ``(t, re, im)`` の 3 配列。空の場合は全て長さ 0。
    """
    segments = find_segments(sim_dir)
    if not segments:
        raise ValueError(f"no segments found under {sim_dir}")
    target_key = f"l{l}_m{m}_r{r:.2f}"
    t_list: list[np.ndarray] = []
    re_list: list[np.ndarray] = []
    im_list: list[np.ndarray] = []
    for seg in segments:
        h5_path = seg / "mp_psi4.h5"
        if not h5_path.exists():
            continue
        with h5py.File(h5_path, "r") as f:
            if target_key not in f:
                # fallback: prefix 一致を試みる (R の小数桁が異なる場合)
                cand = [k for k in f.keys() if _psi4_key_matches(k, l, m, r)]
                if not cand:
                    continue
                target_key_actual = cand[0]
            else:
                target_key_actual = target_key
            ds = f[target_key_actual][:]
            if ds.ndim != 2 or ds.shape[1] < 3:
                continue
            t_list.append(ds[:, 0])
            re_list.append(ds[:, 1])
            im_list.append(ds[:, 2])
    if not t_list:
        return np.empty(0), np.empty(0), np.empty(0)
    t = np.concatenate(t_list)
    re_arr = np.concatenate(re_list)
    im_arr = np.concatenate(im_list)
    return _dedup_by_time_array(t, re_arr, im_arr)


def _psi4_key_matches(key: str, l: int, m: int, r: float, rtol: float = 1e-3) -> bool:
    """psi4 キー名が ``(l, m, r)`` と一致するか (R は相対許容誤差 ``rtol``)."""
    match = PSI4_KEY_PATTERN.search(key)
    if not match:
        return False
    return (
        int(match.group(1)) == l
        and int(match.group(2)) == m
        and abs(float(match.group(3)) - r) <= rtol * max(abs(r), 1.0)
    )


def list_psi4_radii(sim_dir: Path | str, l: int = 2, m: int = 2) -> list[float]:
    """指定 (l, m) で利用可能な抽出半径一覧 (sort 済み)."""
    segments = find_segments(sim_dir)
    if not segments:
        return []
    radii: set[float] = set()
    for seg in segments:
        h5_path = seg / "mp_psi4.h5"
        if not h5_path.exists():
            continue
        with h5py.File(h5_path, "r") as f:
            for k in f.keys():
                match = PSI4_KEY_PATTERN.search(k)
                if match and int(match.group(1)) == l and int(match.group(2)) == m:
                    radii.add(float(match.group(3)))
    return sorted(radii)
