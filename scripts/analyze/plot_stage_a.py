"""Stage A 時系列重ね描き plot 生成 (Phase 4 / Issue #4 タスク C3 (a) 層).

``compare_stage_a.py`` から ``--plot-dir`` 指定時に呼ばれる。matplotlib を
import するため、JSON 比較のみ走らせたい場合は呼ばれない (compare_stage_a
側で遅延 import)。

生成図 (各 PNG):
    orbit_separation.png    — D(t)
    horizon_mass.png        — m_horizon(t) for BH1, BH2
    spin.png                — χ(t) for BH1, BH2
    psi4_22_re.png          — Re ψ4_22(t) at r=100 M
    psi4_22_amplitude.png   — |ψ4_22|(t) at r=100 M
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

from . import _simdir


def _plot_overlay(
    ax,  # matplotlib Axes
    n16_data: tuple[np.ndarray, np.ndarray],
    n28_data: tuple[np.ndarray, np.ndarray],
    t_max: float | None,
    label_y: str,
) -> None:
    t16, y16 = n16_data
    t28, y28 = n28_data
    if t_max is not None:
        m16 = t16 <= t_max
        m28 = t28 <= t_max
        t16, y16 = t16[m16], y16[m16]
        t28, y28 = t28[m28], y28[m28]
    if t28.size:
        ax.plot(t28, y28, label="N=28 (Zenodo)", color="C0", lw=1.5)
    if t16.size:
        ax.plot(t16, y16, label="N=16 (self-run)", color="C1", lw=1.2, ls="--")
    ax.set_xlabel("cctk_time [M]")
    ax.set_ylabel(label_y)
    ax.legend()
    ax.grid(alpha=0.3)


def _separation_series(sim_dir: Path | str) -> tuple[np.ndarray, np.ndarray]:
    ah1 = _simdir.load_bh_diagnostics(sim_dir, 1)
    ah2 = _simdir.load_bh_diagnostics(sim_dir, 2)
    if ah1.size == 0 or ah2.size == 0:
        return np.empty(0), np.empty(0)
    # 共通時刻範囲で線形補間
    t1, t2 = ah1[:, _simdir.BH_TIME_COL], ah2[:, _simdir.BH_TIME_COL]
    t = np.union1d(t1, t2)
    t = t[(t >= max(t1[0], t2[0])) & (t <= min(t1[-1], t2[-1]))]
    if t.size == 0:
        return np.empty(0), np.empty(0)
    x1 = np.interp(t, t1, ah1[:, _simdir.BH_CENTROID_X_COL])
    y1 = np.interp(t, t1, ah1[:, _simdir.BH_CENTROID_Y_COL])
    x2 = np.interp(t, t2, ah2[:, _simdir.BH_CENTROID_X_COL])
    y2 = np.interp(t, t2, ah2[:, _simdir.BH_CENTROID_Y_COL])
    d = np.sqrt((x1 - x2) ** 2 + (y1 - y2) ** 2)
    return t, d


def generate_plots(
    n16_dir: Path | str,
    n28_dir: Path | str,
    output_dir: Path | str,
    t_target: float = 100.0,
    psi4_radius: float = 100.0,
) -> None:
    """全 5 種の overlay plot を ``output_dir`` に出力."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Stage A は t_target+50 M 程度まで描いて余裕を持たせる
    t_plot_max = t_target + 50.0

    # 1. 軌道分離 D(t)
    t16, d16 = _separation_series(n16_dir)
    t28, d28 = _separation_series(n28_dir)
    fig, ax = plt.subplots(figsize=(8, 5))
    _plot_overlay(ax, (t16, d16), (t28, d28), t_plot_max, "Orbital separation D [M]")
    ax.axvline(t_target, color="gray", ls=":", alpha=0.7, label=f"t={t_target} M")
    ax.set_title("Stage A: Orbital separation D(t)")
    ax.legend()
    fig.tight_layout()
    fig.savefig(output_dir / "orbit_separation.png", dpi=120)
    plt.close(fig)

    # 2. m_horizon(t)
    qlm16 = _simdir.load_qlm_scalars(n16_dir)
    qlm28 = _simdir.load_qlm_scalars(n28_dir)
    fig, axes = plt.subplots(1, 2, figsize=(12, 5))
    for ax, off, title in zip(axes, (0, 1), ("BH1", "BH2")):
        n16_d = (qlm16[:, _simdir.QLM_TIME_COL], qlm16[:, _simdir.QLM_MASS + off]) if qlm16.size else (np.empty(0), np.empty(0))
        n28_d = (qlm28[:, _simdir.QLM_TIME_COL], qlm28[:, _simdir.QLM_MASS + off]) if qlm28.size else (np.empty(0), np.empty(0))
        _plot_overlay(ax, n16_d, n28_d, t_plot_max, f"{title} horizon mass [M]")
        ax.axvline(t_target, color="gray", ls=":", alpha=0.7)
        ax.set_title(f"Stage A: {title} horizon mass")
    fig.tight_layout()
    fig.savefig(output_dir / "horizon_mass.png", dpi=120)
    plt.close(fig)

    # 3. χ(t)
    fig, axes = plt.subplots(1, 2, figsize=(12, 5))
    for ax, off, title in zip(axes, (0, 1), ("BH1", "BH2")):
        if qlm16.size:
            t16q = qlm16[:, _simdir.QLM_TIME_COL]
            chi16 = qlm16[:, _simdir.QLM_SPIN + off] / (qlm16[:, _simdir.QLM_MASS + off] ** 2)
            n16_d = (t16q, chi16)
        else:
            n16_d = (np.empty(0), np.empty(0))
        if qlm28.size:
            t28q = qlm28[:, _simdir.QLM_TIME_COL]
            chi28 = qlm28[:, _simdir.QLM_SPIN + off] / (qlm28[:, _simdir.QLM_MASS + off] ** 2)
            n28_d = (t28q, chi28)
        else:
            n28_d = (np.empty(0), np.empty(0))
        _plot_overlay(ax, n16_d, n28_d, t_plot_max, f"{title} χ = J/M²")
        ax.axvline(t_target, color="gray", ls=":", alpha=0.7)
        ax.set_title(f"Stage A: {title} dimensionless spin")
    fig.tight_layout()
    fig.savefig(output_dir / "spin.png", dpi=120)
    plt.close(fig)

    # 4-5. ψ4 (l=2, m=2) at r=psi4_radius
    t16p, re16, im16 = _simdir.load_psi4_mode(n16_dir, 2, 2, psi4_radius)
    t28p, re28, im28 = _simdir.load_psi4_mode(n28_dir, 2, 2, psi4_radius)

    fig, ax = plt.subplots(figsize=(8, 5))
    _plot_overlay(ax, (t16p, re16), (t28p, re28), t_plot_max,
                  f"Re ψ4_22 at r={psi4_radius} M")
    ax.axvline(t_target, color="gray", ls=":", alpha=0.7)
    ax.set_title(f"Stage A: Re ψ4_22 (r={psi4_radius} M)")
    fig.tight_layout()
    fig.savefig(output_dir / "psi4_22_re.png", dpi=120)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(8, 5))
    amp16 = np.hypot(re16, im16) if re16.size else np.empty(0)
    amp28 = np.hypot(re28, im28) if re28.size else np.empty(0)
    _plot_overlay(ax, (t16p, amp16), (t28p, amp28), t_plot_max,
                  f"|ψ4_22| at r={psi4_radius} M")
    ax.axvline(t_target, color="gray", ls=":", alpha=0.7)
    ax.set_title(f"Stage A: |ψ4_22| (r={psi4_radius} M)")
    fig.tight_layout()
    fig.savefig(output_dir / "psi4_22_amplitude.png", dpi=120)
    plt.close(fig)
