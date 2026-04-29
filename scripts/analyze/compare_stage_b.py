"""Stage B (0 → 1000 M) 比較スクリプト (Phase 4 / Issue #4 タスク E).

自前 N=16 run (Stage B 完走分) と Zenodo N=28 reference を比較し、
merger 関連量 (merger_time, 最終 BH M_final / χ_final, 軌道数, ψ4 pre-merger 振幅)
の pass/fail JSON を出力する。

Stage A との主要な違い:
    * 評価対象は ``t = merger_time + Δ`` の **retarded snapshot** (両 run の
      merger 時刻が異なるため、絶対時刻ではなく相対時刻で揃える)
    * ψ4 peak は r=100 M の light-travel delay の都合で N=16 Stage B では
      捕捉できない (peak 時刻 ≈ merger + 100 M、Stage B 終端 = merger + 74 M)。
      代替として merger 直前の振幅 trend を比較する
    * 軌道数は ``puncturetracker-pt_loc..asc`` から計算 (BH_diagnostics の
      AHFinder は inspiral 早期に出力されないため使えない)

判定ロジックと閾値根拠は ``docs/comparison_method_n16_vs_n28.md`` を参照。

主要関数 (テストから直接呼び出し可能):
    detect_merger_time(sim_dir) -> float
    compute_orbit_count(sim_dir, t_start, t_end) -> float
    collect_metrics(sim_dir, ...) -> dict
    evaluate_checks(n16, n28, thresholds) -> dict
    build_report(...) -> dict
    main(argv) -> int  (CLI エントリポイント)
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from . import _simdir
from .compare_stage_a import (
    TARGET_TIME_SNAP_TOLERANCE_M,
    _check_abs,
    _check_pct,
    _interp_or_nan,
    _sanitize_for_json,
)

TARGET_TIME_M = 1000.0
PSI4_DEFAULT_RADIUS = 100.0

# 公式ギャラリー期待値 (= Zenodo N=28 reference に近い値が出るはず)
OFFICIAL_MERGER_TIME_M = 899.0
OFFICIAL_M_FINAL = 0.95
OFFICIAL_CHI_FINAL = 0.69
OFFICIAL_N_ORBIT = 6.0

# 後合体スナップショット評価のための offset [M]。
# N=16 Stage B (t_max ≈ 999 M, merger ≈ 925 M) では merger + 74 M が上限。
# 50 M なら ringdown 早期で十分振る舞いが安定し、両 run で評価可能。
POST_MERGER_DELTA_M = 50.0

# Pre-merger ψ4 振幅評価の窓幅 [M] (merger 直前 30 M の |ψ4| 平均)
PRE_MERGER_PSI4_WINDOW_M = 30.0


# ----------------------------------------------------------------------------
# 閾値定義
# ----------------------------------------------------------------------------
@dataclass(frozen=True)
class StageBThresholds:
    """Stage B pass 閾値. 単体テストで上書き可能."""

    # merger 時刻 (Zenodo N=28 値を reference に ±5%)
    merger_time_pct: float = 5.0

    # 最終 BH パラメータ (公式ギャラリー閾値ベース)
    m_final_pct: float = 5.0
    chi_final_abs: float = 0.10  # 公式 0.69 ± 10% ≈ ±0.069 を緩めに ±0.10

    # 軌道数 (公式 6 ± 1)
    n_orbit_abs: float = 1.0

    # ψ4 pre-merger 振幅 (provisional、Stage C 完了後に確定)
    psi4_pre_merger_pct: float = 50.0

    # self-consistency (ringdown 帯での質量・スピンドリフト)
    m_drift_pct: float = 1.0
    chi_drift_abs: float = 0.05


DEFAULT_THRESHOLDS = StageBThresholds()

# ψ4 pre-merger 振幅は暫定閾値のため overall_pass に算入しない
PROVISIONAL_CHECKS: frozenset[str] = frozenset({"psi4_pre_merger_amplitude"})


# ----------------------------------------------------------------------------
# Stage B 固有のメトリクス抽出
# ----------------------------------------------------------------------------
def detect_merger_time(sim_dir: Path | str) -> float:
    """common horizon (ah3) が初検出された時刻を merger time とする.

    ``BH_diagnostics.ah3.gp`` の最小時刻を返す。Stage B 完走前など ah3 が
    存在しない場合は NaN。
    """
    try:
        ah3 = _simdir.load_bh_diagnostics(sim_dir, 3)
    except ValueError:
        return float("nan")
    if ah3.size == 0:
        return float("nan")
    return float(ah3[0, _simdir.BH_TIME_COL])


def compute_orbit_count(
    sim_dir: Path | str,
    t_start: float,
    t_end: float,
) -> float:
    """``puncturetracker-pt_loc..asc`` から ``[t_start, t_end]`` の軌道数を計算.

    BH1, BH2 の puncture xy 位置から軌道角 ``φ(t) = atan2(y2-y1, x2-x1)`` を
    導き、unwrap した累積角度 / 2π を返す。

    Args:
        sim_dir: simulation ルート
        t_start, t_end: 評価窓 [M]。両方とも puncturetracker の出力範囲内で
            なければ NaN。

    Returns:
        軌道数 (float)。負値は逆回転 (通常は正)。
    """
    pt = _simdir.load_puncture_tracker(sim_dir)
    if pt.size == 0:
        return float("nan")
    t = pt[:, _simdir.PT_TIME_COL]
    if t_start < t[0] - 1e-9 or t_end > t[-1] + 1e-9:
        return float("nan")
    mask = (t >= t_start - 1e-9) & (t <= t_end + 1e-9)
    if mask.sum() < 2:
        return float("nan")
    x1 = pt[mask, _simdir.PT_BH1_X_COL]
    y1 = pt[mask, _simdir.PT_BH1_Y_COL]
    x2 = pt[mask, _simdir.PT_BH2_X_COL]
    y2 = pt[mask, _simdir.PT_BH2_Y_COL]
    phi = np.arctan2(y2 - y1, x2 - x1)
    phi_unwrapped = np.unwrap(phi)
    total_phase = phi_unwrapped[-1] - phi_unwrapped[0]
    return float(abs(total_phase) / (2.0 * math.pi))


def compute_post_merger_state(
    sim_dir: Path | str,
    merger_time: float,
    delta_M: float = POST_MERGER_DELTA_M,
) -> dict[str, float]:
    """``t = merger_time + delta_M`` での common horizon 量を QLM から取得.

    Returns: ``{m_horizon, J, m_irreducible, chi}`` (NaN 可能)。
    """
    if math.isnan(merger_time):
        return _empty_qlm()
    qlm = _simdir.load_qlm_scalars(sim_dir)
    if qlm.size == 0:
        return _empty_qlm()
    t_eval = merger_time + delta_M
    t = qlm[:, _simdir.QLM_TIME_COL]
    # common (BH3) は offset = 2
    m_h = _interp_or_nan(t, qlm[:, _simdir.QLM_MASS + 2], t_eval, snap_tolerance_M=TARGET_TIME_SNAP_TOLERANCE_M)
    j = _interp_or_nan(t, qlm[:, _simdir.QLM_SPIN + 2], t_eval, snap_tolerance_M=TARGET_TIME_SNAP_TOLERANCE_M)
    m_irr = _interp_or_nan(t, qlm[:, _simdir.QLM_IRR_MASS + 2], t_eval, snap_tolerance_M=TARGET_TIME_SNAP_TOLERANCE_M)
    chi = (
        float(_simdir.chi_dimensionless(j, m_h))
        if not math.isnan(m_h) and m_h > 0
        else float("nan")
    )
    return {"m_horizon": m_h, "J": j, "m_irreducible": m_irr, "chi": chi}


def compute_pre_merger_psi4_amplitude(
    sim_dir: Path | str,
    merger_time: float,
    window_M: float = PRE_MERGER_PSI4_WINDOW_M,
    radius: float = PSI4_DEFAULT_RADIUS,
) -> dict[str, float]:
    """merger 直前 ``[merger - window, merger]`` 内での ψ4 (l=2,m=2) 振幅統計.

    ψ4 peak (≈ merger + r/c = merger + 100 M) は Stage B 終端 (merger + 74 M)
    に届かないため、代替として merger 直前の振幅 trend を比較する。

    Returns: ``{t_peak, amp_peak, amp_mean, n_samples}``。
    """
    if math.isnan(merger_time):
        return {"t_peak": float("nan"), "amp_peak": float("nan"),
                "amp_mean": float("nan"), "n_samples": 0}
    t, re_arr, im_arr = _simdir.load_psi4_mode(sim_dir, 2, 2, radius)
    if t.size == 0:
        return {"t_peak": float("nan"), "amp_peak": float("nan"),
                "amp_mean": float("nan"), "n_samples": 0}
    t_lo = merger_time - window_M
    t_hi = merger_time
    mask = (t >= t_lo) & (t <= t_hi)
    if mask.sum() == 0:
        return {"t_peak": float("nan"), "amp_peak": float("nan"),
                "amp_mean": float("nan"), "n_samples": 0}
    amp = np.hypot(re_arr[mask], im_arr[mask])
    t_w = t[mask]
    i_peak = int(np.argmax(amp))
    return {
        "t_peak": float(t_w[i_peak]),
        "amp_peak": float(amp[i_peak]),
        "amp_mean": float(np.mean(amp)),
        "n_samples": int(mask.sum()),
    }


# ----------------------------------------------------------------------------
# メトリクス収集
# ----------------------------------------------------------------------------
def _empty_qlm() -> dict[str, float]:
    return {"m_horizon": float("nan"), "J": float("nan"),
            "m_irreducible": float("nan"), "chi": float("nan")}


def collect_metrics(
    sim_dir: Path | str,
    psi4_radius: float = PSI4_DEFAULT_RADIUS,
    post_merger_delta_M: float = POST_MERGER_DELTA_M,
    pre_merger_window_M: float = PRE_MERGER_PSI4_WINDOW_M,
    n_orbit_t_start: float | None = None,
) -> dict[str, Any]:
    """1 つの sim_dir から Stage B 比較に必要な全メトリクスを抽出.

    Args:
        n_orbit_t_start: 軌道数計算の開始時刻 [M]。``None`` なら
            puncturetracker の最初のサンプル時刻を使用。``build_report`` から
            両 sim の共通開始時刻 (max of t_min) を渡すことで fair 比較を担保。

    Returns:
        ``{merger_time, post_merger, n_orbit, psi4_pre_merger, time_range,
        puncture_t_range, ah1_t_range, ah3_t_range}`` を含む dict。
    """
    merger_time = detect_merger_time(sim_dir)

    post_merger = compute_post_merger_state(sim_dir, merger_time, post_merger_delta_M)

    pt = _simdir.load_puncture_tracker(sim_dir)
    if pt.size > 0:
        pt_t = pt[:, _simdir.PT_TIME_COL]
        pt_t_min = float(pt_t[0])
        pt_t_max = float(pt_t[-1])
    else:
        pt_t_min = pt_t_max = float("nan")

    # 軌道数の評価窓: t_start = (引数 or pt_t_min)、t_end = merger or pt_t_max
    t_start_eval = n_orbit_t_start if n_orbit_t_start is not None else pt_t_min
    if not math.isnan(merger_time) and pt_t_max >= merger_time:
        n_orbit_t_end = merger_time
    else:
        n_orbit_t_end = pt_t_max
    n_orbit = (
        compute_orbit_count(sim_dir, t_start_eval, n_orbit_t_end)
        if (
            not math.isnan(t_start_eval)
            and not math.isnan(n_orbit_t_end)
            and t_start_eval >= pt_t_min - 1e-9
        )
        else float("nan")
    )

    psi4_pre_merger = compute_pre_merger_psi4_amplitude(
        sim_dir, merger_time, pre_merger_window_M, psi4_radius,
    )

    # 完走判定用 time_range (ah1 を基準に Stage A と整合)
    try:
        ah1 = _simdir.load_bh_diagnostics(sim_dir, 1)
        ah1_t_range = (
            float(ah1[0, _simdir.BH_TIME_COL]) if ah1.size else float("nan"),
            float(ah1[-1, _simdir.BH_TIME_COL]) if ah1.size else float("nan"),
        )
    except ValueError:
        ah1_t_range = (float("nan"), float("nan"))

    try:
        ah3 = _simdir.load_bh_diagnostics(sim_dir, 3)
        ah3_t_range = (
            float(ah3[0, _simdir.BH_TIME_COL]) if ah3.size else float("nan"),
            float(ah3[-1, _simdir.BH_TIME_COL]) if ah3.size else float("nan"),
        )
    except ValueError:
        ah3_t_range = (float("nan"), float("nan"))

    return {
        "merger_time_M": merger_time,
        "post_merger": post_merger,
        "post_merger_delta_M": post_merger_delta_M,
        "n_orbit": {
            "value": n_orbit,
            "t_start": t_start_eval,
            "t_end": n_orbit_t_end,
        },
        "psi4_pre_merger": psi4_pre_merger,
        "psi4_pre_merger_window_M": pre_merger_window_M,
        "psi4_radius_M": psi4_radius,
        "time_range": ah1_t_range,
        "ah3_t_range": ah3_t_range,
        "puncture_t_range": (pt_t_min, pt_t_max),
    }


# ----------------------------------------------------------------------------
# 比較ロジック
# ----------------------------------------------------------------------------
def evaluate_checks(
    n16: dict[str, Any],
    n28: dict[str, Any],
    thresholds: StageBThresholds = DEFAULT_THRESHOLDS,
    target_time_M: float = TARGET_TIME_M,
) -> dict[str, Any]:
    """N=16 / N=28 metrics dict から Stage B スナップショット比較を生成."""
    checks: dict[str, dict[str, Any]] = {}

    # 完走判定: puncturetracker の t_max が target に到達しているか。
    # NOTE: BH_diagnostics.ah1 は merger 後に BH1 が common horizon へ吸収され
    # 出力停止するため (Zenodo N=28 では t≈910 M で止まる)、Stage B 完走判定
    # には不適。puncturetracker は AH 消失後も puncture 位置を track 続ける
    # ため、Stage B target=1000 M / Stage C target=1700 M いずれにも対応可能。
    n16_t_max = n16["puncture_t_range"][1]
    completion_pass = (
        not math.isnan(n16_t_max)
        and n16_t_max >= target_time_M - TARGET_TIME_SNAP_TOLERANCE_M
    )
    checks["completion"] = {
        "pass": completion_pass,
        "n16_t_max_M": n16_t_max,
        "target_M": target_time_M,
        "details": (
            f"n16 reached t={n16_t_max:.3f} M"
            if completion_pass
            else f"n16 only reached t={n16_t_max} (need {target_time_M})"
        ),
    }

    # merger time
    checks["merger_time"] = _check_pct(
        n16["merger_time_M"], n28["merger_time_M"], thresholds.merger_time_pct,
    )

    # 最終 BH 質量・スピン (post-merger snapshot at merger + delta)
    checks["m_final"] = _check_pct(
        n16["post_merger"]["m_horizon"], n28["post_merger"]["m_horizon"],
        thresholds.m_final_pct,
    )
    checks["chi_final"] = _check_abs(
        n16["post_merger"]["chi"], n28["post_merger"]["chi"],
        thresholds.chi_final_abs,
    )

    # 軌道数 (絶対値の差)
    checks["n_orbit"] = _check_abs(
        n16["n_orbit"]["value"], n28["n_orbit"]["value"], thresholds.n_orbit_abs,
    )

    # ψ4 pre-merger 振幅 (provisional)
    psi4_amp = _check_pct(
        n16["psi4_pre_merger"]["amp_peak"],
        n28["psi4_pre_merger"]["amp_peak"],
        thresholds.psi4_pre_merger_pct,
    )
    psi4_amp["pass"] = None  # provisional
    psi4_amp["note"] = "provisional threshold (Stage C 完了後に確定予定), not counted in overall_pass"
    checks["psi4_pre_merger_amplitude"] = psi4_amp

    return checks


def evaluate_self_consistency(
    sim_dir: Path | str,
    merger_time: float,
    thresholds: StageBThresholds = DEFAULT_THRESHOLDS,
    eval_window: tuple[float, float] = (30.0, 70.0),
) -> dict[str, Any]:
    """N=16 単体の ringdown 帯 self-consistency 判定.

    ``[merger + eval_window[0], merger + eval_window[1]]`` の範囲で QLM common
    の m_horizon / chi のドリフトを評価する。

    Args:
        eval_window: merger からの offset 範囲 [M]。デフォルト 30-70 M
            (Stage B 上限 ≈ 74 M 内、ringdown 早期相当)。
    """
    if math.isnan(merger_time):
        return {"available": False, "reason": "merger_time is NaN (no common horizon)"}

    qlm = _simdir.load_qlm_scalars(sim_dir)
    if qlm.size == 0:
        return {"available": False, "reason": "qlm_scalars not found"}

    t = qlm[:, _simdir.QLM_TIME_COL]
    t_lo = merger_time + eval_window[0]
    t_hi = merger_time + eval_window[1]
    mask = (t >= t_lo) & (t <= t_hi)
    if mask.sum() < 2:
        return {
            "available": False,
            "reason": f"insufficient samples in [{t_lo:.1f}, {t_hi:.1f}] (got {mask.sum()})",
        }

    # common (BH3) offset = 2
    m_h = qlm[mask, _simdir.QLM_MASS + 2]
    j = qlm[mask, _simdir.QLM_SPIN + 2]
    chi = j / (m_h * m_h)

    m_drift_pct = float((m_h.max() - m_h.min()) / np.mean(m_h) * 100.0)
    chi_drift = float(chi.max() - chi.min())

    return {
        "available": True,
        "eval_window_M": list(eval_window),
        "n_samples": int(mask.sum()),
        "m_final_drift": {
            "pass": m_drift_pct <= thresholds.m_drift_pct,
            "drift_pct": m_drift_pct,
            "threshold_pct": thresholds.m_drift_pct,
        },
        "chi_final_drift": {
            "pass": chi_drift <= thresholds.chi_drift_abs,
            "drift": chi_drift,
            "threshold": thresholds.chi_drift_abs,
        },
    }


def overall_pass(
    checks: dict[str, Any],
    self_consistency: dict[str, Any],
) -> bool:
    """checks / self_consistency から overall pass を算出.

    PROVISIONAL_CHECKS (= pass が None) は判定対象外。
    self_consistency が利用不可 (available=False) の場合は無視。
    """
    for name, c in checks.items():
        if name in PROVISIONAL_CHECKS:
            continue
        if c.get("pass") is False:
            return False
    if self_consistency.get("available", False):
        for name, c in self_consistency.items():
            if name in ("available", "eval_window_M", "n_samples"):
                continue
            if isinstance(c, dict) and c.get("pass") is False:
                return False
    return True


# ----------------------------------------------------------------------------
# レポート生成
# ----------------------------------------------------------------------------
def build_report(
    n16_dir: Path | str,
    n28_dir: Path | str,
    target_time_M: float = TARGET_TIME_M,
    psi4_radius: float = PSI4_DEFAULT_RADIUS,
    post_merger_delta_M: float = POST_MERGER_DELTA_M,
    pre_merger_window_M: float = PRE_MERGER_PSI4_WINDOW_M,
    thresholds: StageBThresholds = DEFAULT_THRESHOLDS,
) -> dict[str, Any]:
    """両 sim_dir から完全な比較レポート (JSON 化可能) を生成.

    軌道数計算では両 sim の puncturetracker 最初のサンプル時刻のうち
    遅い方 (= 共通開始時刻) を使う。N=16 self-run の puncture 出力は
    Stage B 起動後の trigger に従い t≈261 M から始まるが、Zenodo は
    t=0 から始まる。共通範囲で計算しないと N=16 だけが早期 1 軌道
    分を欠落させて見える。
    """
    pt16 = _simdir.load_puncture_tracker(n16_dir)
    pt28 = _simdir.load_puncture_tracker(n28_dir)
    if pt16.size and pt28.size:
        common_t_start = max(
            float(pt16[0, _simdir.PT_TIME_COL]),
            float(pt28[0, _simdir.PT_TIME_COL]),
        )
    else:
        common_t_start = None

    n16_metrics = collect_metrics(
        n16_dir, psi4_radius, post_merger_delta_M, pre_merger_window_M,
        n_orbit_t_start=common_t_start,
    )
    n28_metrics = collect_metrics(
        n28_dir, psi4_radius, post_merger_delta_M, pre_merger_window_M,
        n_orbit_t_start=common_t_start,
    )

    checks = evaluate_checks(n16_metrics, n28_metrics, thresholds, target_time_M)
    sc = evaluate_self_consistency(n16_dir, n16_metrics["merger_time_M"], thresholds)

    return {
        "stage": "B",
        "target_time_M": target_time_M,
        "post_merger_delta_M": post_merger_delta_M,
        "pre_merger_window_M": pre_merger_window_M,
        "psi4_extraction_radius_M": psi4_radius,
        "official_reference": {
            "merger_time_M": OFFICIAL_MERGER_TIME_M,
            "M_final": OFFICIAL_M_FINAL,
            "chi_final": OFFICIAL_CHI_FINAL,
            "n_orbit": OFFICIAL_N_ORBIT,
        },
        "n16_dir": str(n16_dir),
        "n28_dir": str(n28_dir),
        "overall_pass": overall_pass(checks, sc),
        "checks": checks,
        "self_consistency": sc,
        "n16_raw_metrics": _sanitize_for_json(n16_metrics),
        "n28_raw_metrics": _sanitize_for_json(n28_metrics),
    }


# ----------------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------------
def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--n16-dir", type=Path, required=True,
                   help="自前 N=16 Stage B simulation top-level")
    p.add_argument("--n28-dir", type=Path, required=True,
                   help="Zenodo N=28 reference top-level (extracted/GW150914_28)")
    p.add_argument("--output", "-o", type=Path, required=True,
                   help="JSON 出力パス")
    p.add_argument("--target-time", type=float, default=TARGET_TIME_M,
                   help=f"Stage B target time [M] (デフォルト {TARGET_TIME_M})")
    p.add_argument("--psi4-radius", type=float, default=PSI4_DEFAULT_RADIUS,
                   help=f"ψ4 抽出半径 [M] (デフォルト {PSI4_DEFAULT_RADIUS})")
    p.add_argument("--post-merger-delta", type=float, default=POST_MERGER_DELTA_M,
                   help=f"merger 後評価 offset [M] (デフォルト {POST_MERGER_DELTA_M})")
    p.add_argument("--pre-merger-window", type=float, default=PRE_MERGER_PSI4_WINDOW_M,
                   help=f"ψ4 pre-merger 評価窓 [M] (デフォルト {PRE_MERGER_PSI4_WINDOW_M})")
    p.add_argument("--plot-dir", type=Path, default=None,
                   help="(オプション) plot 出力先")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    report = build_report(
        n16_dir=args.n16_dir,
        n28_dir=args.n28_dir,
        target_time_M=args.target_time,
        psi4_radius=args.psi4_radius,
        post_merger_delta_M=args.post_merger_delta,
        pre_merger_window_M=args.pre_merger_window,
    )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    print(f"[compare_stage_b] wrote JSON: {args.output}")

    if args.plot_dir is not None:
        try:
            from . import plot_stage_b  # 遅延 import
            plot_stage_b.generate_plots(
                n16_dir=args.n16_dir, n28_dir=args.n28_dir,
                output_dir=args.plot_dir,
                target_time_M=args.target_time,
                psi4_radius=args.psi4_radius,
            )
            print(f"[compare_stage_b] wrote plots to: {args.plot_dir}")
        except ImportError as e:
            print(f"[compare_stage_b] plot generation skipped: {e}", file=sys.stderr)

    print(f"[compare_stage_b] overall_pass = {report['overall_pass']}")
    for name, c in report["checks"].items():
        if isinstance(c, dict) and "pass" in c:
            mark = {True: "✓", False: "✗", None: "·"}[c["pass"]]
            delta = c.get("delta_pct", c.get("delta", "-"))
            print(f"  {mark} {name}: {delta}")

    sc = report["self_consistency"]
    if sc.get("available", False):
        for name in ("m_final_drift", "chi_final_drift"):
            c = sc.get(name, {})
            if isinstance(c, dict) and "pass" in c:
                mark = "✓" if c["pass"] else "✗"
                print(f"  {mark} self_consistency.{name}: {c.get('drift_pct', c.get('drift', '-'))}")

    return 0 if report["overall_pass"] else 1


if __name__ == "__main__":
    sys.exit(main())
