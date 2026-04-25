"""Zenodo N=28 reference データ構造調査スクリプト (Phase 4 / Issue #4 タスク A1-A3)。

ホスト Python 環境を汚さないため docker 内で実行する想定:
    docker compose exec et python3 /home/etuser/work/scripts/analyze/inspect_zenodo.py

調査項目:
    A1. mp_psi4.h5 の内部構造 (l, m モード, 抽出半径, time range)
    A2. constraint 出力 (H.norm2.asc 等) が Zenodo データに含まれるか
    A3. t=100 M 時点の N=28 reference 値 (D, m_irr, areal radius, ψ4 振幅・位相)
    A5. QLM 出力からスピン (χ = J/M²) と質量を取得、t=100 M 時点 reference 値
"""

from __future__ import annotations

import math
import re
from pathlib import Path

import h5py
import numpy as np

ZENODO_BASE = Path("/home/etuser/work/data/GW150914_N28_zenodo/extracted/GW150914_28")
TARGET_T = 100.0


def banner(title: str) -> None:
    print(f"\n{'=' * 78}\n{title}\n{'=' * 78}")


def list_segments() -> list[Path]:
    return sorted(p for p in ZENODO_BASE.glob("output-*/GW150914_28") if p.is_dir())


# ----------------------------------------------------------------------------
# A1. mp_psi4.h5 内部構造
# ----------------------------------------------------------------------------
def inspect_mp_psi4(seg: Path) -> None:
    banner(f"A1. mp_psi4.h5 内部構造 ({seg.parent.name})")
    mp_path = seg / "mp_psi4.h5"
    if not mp_path.exists():
        print(f"NOT FOUND: {mp_path}")
        return
    print(f"path: {mp_path}")
    print(f"size: {mp_path.stat().st_size / 1e6:.2f} MB")

    with h5py.File(mp_path, "r") as f:
        keys = list(f.keys())
        print(f"total datasets: {len(keys)}")
        print("\n--- 最初 6 個のサンプル (構造確認用) ---")
        for k in keys[:6]:
            ds = f[k]
            print(f"  {k}")
            print(f"    shape={ds.shape} dtype={ds.dtype}")
            if ds.attrs:
                for ak, av in ds.attrs.items():
                    print(f"    attr {ak} = {av}")
            if len(ds.shape) == 2 and ds.shape[1] >= 2:
                print(f"    first row: {ds[0]}")
                print(f"    last  row: {ds[-1]}")

        # キー命名パターン抽出 (一般的に "l<L>_m<M>_r<R>" を含む)
        pat = re.compile(r"l(\d+)_m(-?\d+)_r(\d+\.?\d*)")
        modes: set[tuple[int, int]] = set()
        radii: set[float] = set()
        unmatched_samples: list[str] = []
        for k in keys:
            m = pat.search(k)
            if m:
                modes.add((int(m.group(1)), int(m.group(2))))
                radii.add(float(m.group(3)))
            elif len(unmatched_samples) < 5:
                unmatched_samples.append(k)

        print(f"\nunique (l, m) modes: {len(modes)}")
        if modes:
            print(f"  {sorted(modes)}")
        print(f"unique extraction radii: {sorted(radii)}")
        if unmatched_samples:
            print(f"unmatched key samples (regex 不一致): {unmatched_samples}")


# ----------------------------------------------------------------------------
# A2. constraint output の存在確認
# ----------------------------------------------------------------------------
def inspect_constraints(segments: list[Path]) -> None:
    banner("A2. constraint 出力ファイルの存在確認 (全 segment)")
    # 探索対象: ML_BSSN / ADMConstraints の慣習的命名
    keywords = ["H.", "ham", "M1.", "M2.", "M3.", "mom", "constraint", "norm"]
    for seg in segments:
        ascii_files = sorted(seg.glob("*.asc"))
        cands = [p for p in ascii_files if any(kw in p.name.lower() for kw in keywords)]
        print(f"\n{seg.parent.name}: {len(ascii_files)} .asc 中、constraint 候補 {len(cands)} 件")
        for p in cands[:20]:
            size_kb = p.stat().st_size / 1024
            print(f"  {p.name}  ({size_kb:.1f} KB)")
        if len(cands) > 20:
            print(f"  ... ({len(cands)} total)")
        if not cands:
            print("  (該当なし — 全 .asc 一覧:)")
            for p in ascii_files[:30]:
                print(f"    {p.name}")
            if len(ascii_files) > 30:
                print(f"    ... ({len(ascii_files)} total)")


# ----------------------------------------------------------------------------
# A3. t=100 M reference 値テーブル
# ----------------------------------------------------------------------------
def load_bh_diag(path: Path) -> np.ndarray:
    return np.loadtxt(path, comments="#")


def interp_col(arr: np.ndarray, t: float, col: int) -> float:
    return float(np.interp(t, arr[:, 1], arr[:, col]))


def reference_values_at_t100(seg: Path) -> None:
    banner(f"A3. t={TARGET_T} M 時点の N=28 reference 値 ({seg.parent.name})")
    ah1 = load_bh_diag(seg / "BH_diagnostics.ah1.gp")
    ah2 = load_bh_diag(seg / "BH_diagnostics.ah2.gp")
    print(f"ah1: shape={ah1.shape}, t range = [{ah1[0,1]:.3f}, {ah1[-1,1]:.3f}]")
    print(f"ah2: shape={ah2.shape}, t range = [{ah2[0,1]:.3f}, {ah2[-1,1]:.3f}]")

    # column index (0-based, Cactus 慣習)
    # 1 = cctk_time, 2-4 = centroid_x/y/z, 26 = m_irreducible, 27 = areal_radius
    rec: dict[str, float] = {}
    for tag, arr in [("ah1", ah1), ("ah2", ah2)]:
        rec[f"{tag}_centroid_x"] = interp_col(arr, TARGET_T, 2)
        rec[f"{tag}_centroid_y"] = interp_col(arr, TARGET_T, 3)
        rec[f"{tag}_centroid_z"] = interp_col(arr, TARGET_T, 4)
        rec[f"{tag}_m_irreducible"] = interp_col(arr, TARGET_T, 26)
        rec[f"{tag}_areal_radius"] = interp_col(arr, TARGET_T, 27)

    dx = rec["ah1_centroid_x"] - rec["ah2_centroid_x"]
    dy = rec["ah1_centroid_y"] - rec["ah2_centroid_y"]
    dz = rec["ah1_centroid_z"] - rec["ah2_centroid_z"]
    rec["D_separation"] = math.sqrt(dx * dx + dy * dy + dz * dz)
    rec["orbital_angle_rad"] = math.atan2(dy, dx)

    print(f"\n--- t = {TARGET_T} M reference (N=28, 線形補間) ---")
    for k, v in rec.items():
        print(f"  {k:30s} = {v:+.10g}")

    # ψ4 (l=2, m=2) at t=100 M
    mp_path = seg / "mp_psi4.h5"
    if not mp_path.exists():
        print("\n(mp_psi4.h5 なし、ψ4 抽出スキップ)")
        return
    print("\n--- ψ4 (l=2, m=2) at t=100 M ---")
    pat22 = re.compile(r"l2_m2_r(\d+\.?\d*)")
    with h5py.File(mp_path, "r") as f:
        found = []
        for k in f.keys():
            m = pat22.search(k)
            if m:
                found.append((float(m.group(1)), k))
        found.sort()
        for r, k in found:
            ds = f[k][:]
            if len(ds.shape) != 2 or ds.shape[1] < 3:
                print(f"  {k}: 想定外 shape {ds.shape}, スキップ")
                continue
            t_arr = ds[:, 0]
            if TARGET_T < t_arr[0] or TARGET_T > t_arr[-1]:
                print(f"  r={r:.2f}: t={TARGET_T} 範囲外 [{t_arr[0]:.3f}, {t_arr[-1]:.3f}]")
                continue
            re_val = float(np.interp(TARGET_T, t_arr, ds[:, 1]))
            im_val = float(np.interp(TARGET_T, t_arr, ds[:, 2]))
            amp = math.hypot(re_val, im_val)
            phi = math.atan2(im_val, re_val)
            print(f"  r={r:6.2f}: Re={re_val:+.6e}  Im={im_val:+.6e}  |ψ4|={amp:.6e}  arg={phi:+.4f} rad")
        if not found:
            print("  (l=2, m=2 のキーが見つからず — A1 のキー命名パターン確認が必要)")


# ----------------------------------------------------------------------------
# A5. QLM スピン・質量 reference 値 (t=100 M)
# ----------------------------------------------------------------------------
# QLM 0D ASCII の列 index (Python 0-based)
#   col 1-12: メタ (it, tl, rl, c, ml, ix, iy, iz, time, x, y, z)
#   col 13+: data — 各 variable は [BH1, BH2, common] の 3 要素
QLM_TIME_COL = 8       # 1-based col 9 = time
QLM_IRR_MASS = 27      # 1-based col 28 = qlm_irreducible_mass[0]
QLM_SPIN = 45          # 1-based col 46 = qlm_spin[0]  (J, dimensional)
QLM_MASS = 66          # 1-based col 67 = qlm_mass[0]  (= horizon mass)


def chi_dimensionless(j: float, m_horizon: float) -> float:
    """無次元スピン χ = J / M_horizon² (Kerr 慣習)。"""
    if m_horizon <= 0:
        return float("nan")
    return j / (m_horizon * m_horizon)


def reference_qlm_at_t100(seg: Path) -> None:
    banner(f"A5. t={TARGET_T} M 時点の QLM スピン・質量 reference ({seg.parent.name})")
    qlm_path = seg / "quasilocalmeasures-qlm_scalars..asc"
    if not qlm_path.exists():
        print(f"NOT FOUND: {qlm_path}")
        return
    arr = np.loadtxt(qlm_path, comments="#")
    print(f"shape: {arr.shape}")
    t = arr[:, QLM_TIME_COL]
    print(f"time range: [{t[0]:.3f}, {t[-1]:.3f}]")

    # 初期値 (t=0)
    print("\n--- 初期値 (t=0) ---")
    for label, off in [("BH1", 0), ("BH2", 1)]:
        m_irr = arr[0, QLM_IRR_MASS + off]
        m_h = arr[0, QLM_MASS + off]
        j = arr[0, QLM_SPIN + off]
        chi = chi_dimensionless(j, m_h)
        print(f"  {label}: m_irr={m_irr:.6f}  m_horizon={m_h:.6f}  J={j:+.6f}  χ=J/M²={chi:+.4f}")
    print("  (期待: χ₁=+0.31, χ₂=-0.46 — GW150914.rpar 設定値)")

    # t = TARGET_T 線形補間
    print(f"\n--- t = {TARGET_T} M (線形補間) ---")
    rec: dict[str, float] = {}
    for label, off in [("BH1", 0), ("BH2", 1)]:
        m_irr = float(np.interp(TARGET_T, t, arr[:, QLM_IRR_MASS + off]))
        m_h = float(np.interp(TARGET_T, t, arr[:, QLM_MASS + off]))
        j = float(np.interp(TARGET_T, t, arr[:, QLM_SPIN + off]))
        chi = chi_dimensionless(j, m_h)
        rec[f"{label}_m_irr"] = m_irr
        rec[f"{label}_m_horizon"] = m_h
        rec[f"{label}_J"] = j
        rec[f"{label}_chi"] = chi
        print(
            f"  {label}: m_irr={m_irr:.6f}  m_horizon={m_h:.6f}  "
            f"J={j:+.6f}  χ=J/M²={chi:+.4f}"
        )

    # ドリフト (0 ≤ t ≤ TARGET_T 区間内)
    mask = t <= TARGET_T
    print(f"\n--- 0 ≤ t ≤ {TARGET_T} M でのドリフト (max - min) ---")
    for label, off in [("BH1", 0), ("BH2", 1)]:
        m_h_arr = arr[mask, QLM_MASS + off]
        j_arr = arr[mask, QLM_SPIN + off]
        chi_arr = j_arr / (m_h_arr * m_h_arr)
        m_drift_pct = (m_h_arr.max() - m_h_arr.min()) / np.mean(m_h_arr) * 100
        chi_drift = chi_arr.max() - chi_arr.min()
        print(
            f"  {label}: m_horizon drift = {m_drift_pct:.4f}%, "
            f"χ drift = {chi_drift:+.6f}  ({len(m_h_arr)} samples)"
        )


# ----------------------------------------------------------------------------
def main() -> None:
    segments = list_segments()
    if not segments:
        print(f"NO DATA: {ZENODO_BASE} 配下に segment が見つかりません")
        return
    print(f"検出した segments: {[s.parent.name for s in segments]}")

    # output-0000 が Stage A 100 M を含む
    inspect_mp_psi4(segments[0])
    inspect_constraints(segments)
    reference_values_at_t100(segments[0])
    reference_qlm_at_t100(segments[0])


if __name__ == "__main__":
    main()
