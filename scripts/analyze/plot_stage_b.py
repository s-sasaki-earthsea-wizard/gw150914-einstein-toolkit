# SPDX-License-Identifier: GPL-2.0-or-later
# Copyright (C) 2026 Syota Sasaki
"""Stage B 時系列重ね描き plot 生成 (Phase 4 / Issue #4 タスク E).

``compare_stage_b.py`` から ``--plot-dir`` 指定時に呼ばれる。

生成図 (各 PNG):
    orbit_trajectory.png             — xy 平面 BH1, BH2 軌跡 (puncturetracker)
    orbit_separation.png             — D(t) 絶対時刻軸 (inspiral 全体)
    orbit_separation_aligned.png     — D(t - t_merger) merger 時刻揃え (定性比較に最適)
    horizon_mass_common.png          — common horizon m_h(t) 絶対時刻軸
    chi_common.png                   — common horizon χ(t) 絶対時刻軸
    ringdown_aligned.png             — m_h, χ を merger-aligned (ringdown 詳細比較)
    psi4_22_re.png                   — Re ψ4_22(t) 絶対時刻軸
    psi4_22_amplitude.png            — \|ψ4_22\|(t) **log y-axis** (inspiral から peak まで)
    psi4_22_amplitude_aligned.png    — \|ψ4_22\|(t - t_merger) merger 揃え + log scale

linear vs log の使い分け: ψ4 振幅は inspiral (~5e-5) と peak (~7e-4) で
1 桁以上差があり、linear scale だと peak が支配的になり inspiral 同士の
一致が見えにくい。merger-aligned + log で「物理的に同じ phase の波形が
完璧に重なる」ことを定性的に示す。
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

from . import _simdir


def _puncture_xy(sim_dir: Path | str) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """``(t, x1, y1, x2, y2)`` を puncturetracker から取得."""
    pt = _simdir.load_puncture_tracker(sim_dir)
    if pt.size == 0:
        empty = np.empty(0)
        return empty, empty, empty, empty, empty
    return (
        pt[:, _simdir.PT_TIME_COL],
        pt[:, _simdir.PT_BH1_X_COL],
        pt[:, _simdir.PT_BH1_Y_COL],
        pt[:, _simdir.PT_BH2_X_COL],
        pt[:, _simdir.PT_BH2_Y_COL],
    )


def _separation_from_puncture(sim_dir: Path | str) -> tuple[np.ndarray, np.ndarray]:
    """puncturetracker から D(t) を計算 (BH_diagnostics より連続した track)."""
    t, x1, y1, x2, y2 = _puncture_xy(sim_dir)
    if t.size == 0:
        return np.empty(0), np.empty(0)
    d = np.sqrt((x1 - x2) ** 2 + (y1 - y2) ** 2)
    return t, d


def generate_plots(
    n16_dir: Path | str,
    n28_dir: Path | str,
    output_dir: Path | str,
    target_time_M: float = 1000.0,
    psi4_radius: float = 100.0,
) -> None:
    """Stage B 用 6 種の overlay plot を ``output_dir`` に出力."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # 表示する時間範囲: Stage B 終端 + 余裕。N=28 は 1700 M まであるが、
    # Stage B 比較のため target_time + 50 M でクリップ。
    t_plot_max = target_time_M + 50.0

    # ------------------------------------------------------------------------
    # 1. 軌道 trajectory (xy 平面)
    # ------------------------------------------------------------------------
    fig, axes = plt.subplots(1, 2, figsize=(14, 6))
    for ax, sd, label in zip(axes, (n28_dir, n16_dir), ("N=28 (Zenodo)", "N=16 (self-run)")):
        t, x1, y1, x2, y2 = _puncture_xy(sd)
        if t.size:
            mask = t <= t_plot_max
            ax.plot(x1[mask], y1[mask], color="C0", lw=0.8, label="BH1")
            ax.plot(x2[mask], y2[mask], color="C3", lw=0.8, label="BH2")
            ax.scatter([x1[mask][0], x2[mask][0]], [y1[mask][0], y2[mask][0]],
                       color="black", s=20, zorder=3, label="start")
            ax.scatter([x1[mask][-1], x2[mask][-1]], [y1[mask][-1], y2[mask][-1]],
                       color="red", s=30, marker="x", zorder=3, label="end")
        ax.set_xlabel("x [M]")
        ax.set_ylabel("y [M]")
        ax.set_title(f"Orbit trajectory ({label})")
        ax.set_aspect("equal", adjustable="datalim")
        ax.grid(alpha=0.3)
        ax.legend(loc="upper right")
    fig.tight_layout()
    fig.savefig(output_dir / "orbit_trajectory.png", dpi=120)
    plt.close(fig)

    # ------------------------------------------------------------------------
    # 2. 軌道分離 D(t)
    # ------------------------------------------------------------------------
    t16, d16 = _separation_from_puncture(n16_dir)
    t28, d28 = _separation_from_puncture(n28_dir)
    fig, ax = plt.subplots(figsize=(10, 5))
    if t28.size:
        m28 = t28 <= t_plot_max
        ax.plot(t28[m28], d28[m28], label="N=28 (Zenodo)", color="C0", lw=1.5)
    if t16.size:
        m16 = t16 <= t_plot_max
        ax.plot(t16[m16], d16[m16], label="N=16 (self-run)", color="C1", lw=1.2, ls="--")
    ax.axvline(target_time_M, color="gray", ls=":", alpha=0.7, label=f"Stage B end = {target_time_M} M")
    ax.set_xlabel("cctk_time [M]")
    ax.set_ylabel("Orbital separation D [M]")
    ax.set_title("Stage B: Orbital separation D(t)")
    ax.legend()
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(output_dir / "orbit_separation.png", dpi=120)
    plt.close(fig)

    # ------------------------------------------------------------------------
    # 3. common horizon m_h(t) (post-merger)
    # ------------------------------------------------------------------------
    qlm16 = _simdir.load_qlm_scalars(n16_dir)
    qlm28 = _simdir.load_qlm_scalars(n28_dir)
    fig, ax = plt.subplots(figsize=(10, 5))
    for label, qlm, color, ls in (
        ("N=28 (Zenodo)", qlm28, "C0", "-"),
        ("N=16 (self-run)", qlm16, "C1", "--"),
    ):
        if qlm.size:
            t = qlm[:, _simdir.QLM_TIME_COL]
            mh = qlm[:, _simdir.QLM_MASS + 2]  # common = offset 2
            mask = (mh > 1e-6) & (t <= t_plot_max)
            if mask.sum():
                ax.plot(t[mask], mh[mask], label=label, color=color, lw=1.4, ls=ls)
    ax.axvline(target_time_M, color="gray", ls=":", alpha=0.7,
               label=f"Stage B end = {target_time_M} M")
    ax.set_xlabel("cctk_time [M]")
    ax.set_ylabel("Common horizon mass M_h [M]")
    ax.set_title("Stage B: Common horizon mass (post-merger)")
    ax.legend()
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(output_dir / "horizon_mass_common.png", dpi=120)
    plt.close(fig)

    # ------------------------------------------------------------------------
    # 4. common horizon χ(t)
    # ------------------------------------------------------------------------
    fig, ax = plt.subplots(figsize=(10, 5))
    for label, qlm, color, ls in (
        ("N=28 (Zenodo)", qlm28, "C0", "-"),
        ("N=16 (self-run)", qlm16, "C1", "--"),
    ):
        if qlm.size:
            t = qlm[:, _simdir.QLM_TIME_COL]
            mh = qlm[:, _simdir.QLM_MASS + 2]
            j = qlm[:, _simdir.QLM_SPIN + 2]
            mask = (mh > 1e-6) & (t <= t_plot_max)
            if mask.sum():
                chi = j[mask] / (mh[mask] ** 2)
                ax.plot(t[mask], chi, label=label, color=color, lw=1.4, ls=ls)
    ax.axvline(target_time_M, color="gray", ls=":", alpha=0.7,
               label=f"Stage B end = {target_time_M} M")
    ax.axhline(0.69, color="green", ls=":", alpha=0.5, label="official χ_f=0.69")
    ax.set_xlabel("cctk_time [M]")
    ax.set_ylabel("Common horizon χ = J/M²")
    ax.set_title("Stage B: Common horizon dimensionless spin")
    ax.legend()
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(output_dir / "chi_common.png", dpi=120)
    plt.close(fig)

    # ------------------------------------------------------------------------
    # 5-6. ψ4 (l=2, m=2) at r=psi4_radius
    # ------------------------------------------------------------------------
    t16p, re16, im16 = _simdir.load_psi4_mode(n16_dir, 2, 2, psi4_radius)
    t28p, re28, im28 = _simdir.load_psi4_mode(n28_dir, 2, 2, psi4_radius)

    fig, ax = plt.subplots(figsize=(10, 5))
    if t28p.size:
        m28p = t28p <= t_plot_max
        ax.plot(t28p[m28p], re28[m28p], label="N=28 (Zenodo)", color="C0", lw=1.0)
    if t16p.size:
        m16p = t16p <= t_plot_max
        ax.plot(t16p[m16p], re16[m16p], label="N=16 (self-run)", color="C1", lw=0.8, ls="--")
    ax.axvline(target_time_M, color="gray", ls=":", alpha=0.7,
               label=f"Stage B end = {target_time_M} M")
    ax.set_xlabel("cctk_time [M]")
    ax.set_ylabel(f"Re ψ4_22 at r={psi4_radius} M")
    ax.set_title(f"Stage B: Re ψ4_22 (r={psi4_radius} M, full inspiral + early ringdown)")
    ax.legend()
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(output_dir / "psi4_22_re.png", dpi=120)
    plt.close(fig)

    # log y-axis 版: inspiral (~5e-5) と peak (~7e-4) を 1 つの図で比較。
    # 0 を含むと log で消えるため、十分小さい floor で clip。
    fig, ax = plt.subplots(figsize=(10, 5))
    amp_floor = 1e-9
    if t28p.size:
        m28p = t28p <= t_plot_max
        amp28 = np.maximum(np.hypot(re28[m28p], im28[m28p]), amp_floor)
        ax.plot(t28p[m28p], amp28, label="N=28 (Zenodo)", color="C0", lw=1.0)
    if t16p.size:
        m16p = t16p <= t_plot_max
        amp16 = np.maximum(np.hypot(re16[m16p], im16[m16p]), amp_floor)
        ax.plot(t16p[m16p], amp16, label="N=16 (self-run)", color="C1", lw=0.8, ls="--")
    ax.axvline(target_time_M, color="gray", ls=":", alpha=0.7,
               label=f"Stage B end = {target_time_M} M")
    ax.set_yscale("log")
    ax.set_ylim(bottom=1e-7)
    ax.set_xlabel("cctk_time [M]")
    ax.set_ylabel(f"|ψ4_22| at r={psi4_radius} M (log)")
    ax.set_title(f"Stage B: |ψ4_22| (r={psi4_radius} M, log scale)")
    ax.legend()
    ax.grid(alpha=0.3, which="both")
    fig.tight_layout()
    fig.savefig(output_dir / "psi4_22_amplitude.png", dpi=120)
    plt.close(fig)

    # ------------------------------------------------------------------------
    # 7. merger-aligned overlays (定性的一致を示す)
    # ------------------------------------------------------------------------
    # 両 sim の merger time を ah3 出現時刻として取得 (NaN なら skip)
    def _merger_time(sim_dir: Path | str) -> float:
        try:
            ah3 = _simdir.load_bh_diagnostics(sim_dir, 3)
        except ValueError:
            return float("nan")
        return float(ah3[0, _simdir.BH_TIME_COL]) if ah3.size else float("nan")

    t_merger_n16 = _merger_time(n16_dir)
    t_merger_n28 = _merger_time(n28_dir)

    if not (np.isnan(t_merger_n16) or np.isnan(t_merger_n28)):
        # 7a. ψ4 amplitude merger-aligned (log scale)
        # x 軸は t - t_merger。両 sim を同じ「merger からの経過時刻」で重ねる。
        fig, ax = plt.subplots(figsize=(10, 5))
        if t28p.size:
            x28 = t28p - t_merger_n28
            mask = (x28 >= -300) & (x28 <= 100)  # inspiral 末期 → ringdown 早期
            amp28 = np.maximum(np.hypot(re28[mask], im28[mask]), amp_floor)
            ax.plot(x28[mask], amp28, label="N=28 (Zenodo)", color="C0", lw=1.2)
        if t16p.size:
            x16 = t16p - t_merger_n16
            mask = (x16 >= -300) & (x16 <= 100)
            amp16 = np.maximum(np.hypot(re16[mask], im16[mask]), amp_floor)
            ax.plot(x16[mask], amp16, label="N=16 (self-run)", color="C1", lw=1.0, ls="--")
        ax.axvline(0.0, color="green", ls=":", alpha=0.7, label="merger (ah3 first detect)")
        ax.set_yscale("log")
        ax.set_xlabel("t − t_merger [M]")
        ax.set_ylabel(f"|ψ4_22| at r={psi4_radius} M (log)")
        ax.set_title("Stage B: |ψ4_22| merger-aligned overlay (log scale)")
        ax.legend()
        ax.grid(alpha=0.3, which="both")
        fig.tight_layout()
        fig.savefig(output_dir / "psi4_22_amplitude_aligned.png", dpi=120)
        plt.close(fig)

        # 7b. orbital separation merger-aligned
        fig, ax = plt.subplots(figsize=(10, 5))
        if t28.size:
            x28 = t28 - t_merger_n28
            mask = (x28 >= -800) & (x28 <= 50)
            ax.plot(x28[mask], d28[mask], label="N=28 (Zenodo)", color="C0", lw=1.5)
        if t16.size:
            x16 = t16 - t_merger_n16
            mask = (x16 >= -800) & (x16 <= 50)
            ax.plot(x16[mask], d16[mask], label="N=16 (self-run)", color="C1", lw=1.2, ls="--")
        ax.axvline(0.0, color="green", ls=":", alpha=0.7, label="merger")
        ax.set_xlabel("t − t_merger [M]")
        ax.set_ylabel("Orbital separation D [M]")
        ax.set_title("Stage B: Orbital separation merger-aligned overlay")
        ax.legend()
        ax.grid(alpha=0.3)
        fig.tight_layout()
        fig.savefig(output_dir / "orbit_separation_aligned.png", dpi=120)
        plt.close(fig)

        # 7c. ringdown m_h, χ merger-aligned (2 panels)
        # NOTE: AHFinder が common horizon を初期検出した直後 (~5 M) は sphere
        # fit が真の (highly distorted) horizon を捕捉できず、QLM J / M² が
        # transient で振動する (χ が一時的に負値や 0.5 以下を取る)。
        # plot では quasi-stationary 領域 (t - t_merger ≥ 10 M) のみ表示し、
        # 物理的に意味のある ringdown 安定相での一致を可視化する。
        ringdown_t_min = 10.0  # transient cut-off [M]

        fig, axes = plt.subplots(2, 1, figsize=(10, 8), sharex=True)

        # m_h panel
        ax = axes[0]
        for label, qlm, t_merger, color, ls in (
            ("N=28 (Zenodo)", qlm28, t_merger_n28, "C0", "-"),
            ("N=16 (self-run)", qlm16, t_merger_n16, "C1", "--"),
        ):
            if qlm.size:
                t = qlm[:, _simdir.QLM_TIME_COL]
                mh = qlm[:, _simdir.QLM_MASS + 2]
                mask = (mh > 1e-6)
                if mask.sum():
                    x = t[mask] - t_merger
                    sub = (x >= ringdown_t_min) & (x <= 200)
                    ax.plot(x[sub], mh[mask][sub], label=label, color=color, lw=1.4, ls=ls)
        ax.axhline(0.95, color="green", ls=":", alpha=0.5, label="official M_f=0.95")
        ax.set_ylabel("Common horizon mass M_h [M]")
        ax.set_ylim(0.945, 0.96)
        ax.set_title(f"Stage B: Ringdown comparison (merger-aligned, t≥{ringdown_t_min:.0f} M)")
        ax.legend(loc="center right")
        ax.grid(alpha=0.3)

        # χ panel
        ax = axes[1]
        for label, qlm, t_merger, color, ls in (
            ("N=28 (Zenodo)", qlm28, t_merger_n28, "C0", "-"),
            ("N=16 (self-run)", qlm16, t_merger_n16, "C1", "--"),
        ):
            if qlm.size:
                t = qlm[:, _simdir.QLM_TIME_COL]
                mh = qlm[:, _simdir.QLM_MASS + 2]
                j = qlm[:, _simdir.QLM_SPIN + 2]
                mask = (mh > 1e-6)
                if mask.sum():
                    x = t[mask] - t_merger
                    chi = j[mask] / (mh[mask] ** 2)
                    sub = (x >= ringdown_t_min) & (x <= 200)
                    ax.plot(x[sub], chi[sub], label=label, color=color, lw=1.4, ls=ls)
        ax.axhline(0.69, color="green", ls=":", alpha=0.5, label="official χ_f=0.69")
        ax.set_xlabel("t − t_merger [M]")
        ax.set_ylabel("χ = J/M²")
        ax.set_ylim(0.65, 0.72)
        ax.legend(loc="center right")
        ax.grid(alpha=0.3)

        fig.tight_layout()
        fig.savefig(output_dir / "ringdown_aligned.png", dpi=120)
        plt.close(fig)
