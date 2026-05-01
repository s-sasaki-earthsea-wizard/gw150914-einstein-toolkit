"""Stage C (0 → 1700 M) 比較スクリプト (Phase 4 / Issue #4 タスク F).

自前 N=16 run (Stage A + B + C 連結) と Zenodo N=28 reference を比較する。
Stage C 単体には merger event が含まれない (resume 開始のため) ので、
``--n16-dirs`` に Stage A / B / C の sim_dir を順に渡し、``_simdir`` の
sequence サポートで全 segment を時系列方向に concat する。

Stage B との主要な違い:
    * ψ4 peak が r=100 M で完全捕捉される (peak ≈ merger + 100 M ≈ 1025 M)
      → 真の ψ4 peak amplitude / peak time を比較対象に格上げ
    * ringdown self-consistency 評価窓を 30-200 M (= merger 後 ~870 M
      まで) に拡張可能 (Stage B では 30-70 M に制限されていた)
    * 完走 target = 1700 M

判定ロジックと閾値根拠は ``docs/comparison_method_n16_vs_n28.md`` を参照。

主要関数 (テストから直接呼び出し可能):
    detect_psi4_peak(sim_dir, radius) -> dict
    collect_metrics(sim_dirs, ...) -> dict
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
from .compare_stage_b import (
    OFFICIAL_CHI_FINAL,
    OFFICIAL_M_FINAL,
    OFFICIAL_MERGER_TIME_M,
    OFFICIAL_N_ORBIT,
    POST_MERGER_DELTA_M,
    PSI4_DEFAULT_RADIUS,
    compute_orbit_count,
    compute_post_merger_state,
    detect_merger_time,
)

TARGET_TIME_M = 1700.0

# puncturetracker 連結時の「大ギャップ」判定係数。
# Stage A → Stage B 間で N=16 puncturetracker は t=99 → 261 M (~162 M) の
# trigger ギャップを持つ (Stage A は inspiral 起動時の trigger 設定で連続出力、
# Stage B は restart trigger 仕様で 261 M から再出力)。このギャップ越しに
# np.unwrap で位相を取ると数軌道分の偽の jump が発生し n_orbit が壊れる。
# 中央値 dt の MAX_GAP_FACTOR 倍を超えるギャップを検出した場合、最後の
# 大ギャップ以降の連続区間 start を有効 pt_t_min として軌道数計算に使う。
MAX_GAP_FACTOR = 5.0


# ----------------------------------------------------------------------------
# 閾値定義
# ----------------------------------------------------------------------------
@dataclass(frozen=True)
class StageCThresholds:
    """Stage C pass 閾値. 単体テストで上書き可能.

    Stage B より厳しめ (peak amplitude が捕捉できる + ringdown 評価が長い分、
    より厳密な比較が可能)。
    """

    # merger 時刻 (Zenodo N=28 値を reference に ±5%)
    merger_time_pct: float = 5.0

    # 最終 BH パラメータ (Stage B 実測 0.10% / 0.0054 を踏まえ ±2% / ±0.02 に
    # 引き締めるが、N=16 解像度の系統誤差マージンとして余裕は残す)
    m_final_pct: float = 2.0
    chi_final_abs: float = 0.02

    # 軌道数 (Stage B 実測 +0.15 を踏まえ ±0.5)
    n_orbit_abs: float = 0.5

    # ψ4 peak amplitude (Stage B 実測 1.79% を踏まえ ±10%、解像度依存性吸収用)
    psi4_peak_pct: float = 10.0

    # ψ4 peak time (merger 揃え後の差。光路時間 r/c ≈ 100 M に対し ±20 M)
    psi4_peak_time_abs: float = 20.0

    # self-consistency (拡張 ringdown 窓での質量・スピンドリフト)
    m_drift_pct: float = 1.0
    chi_drift_abs: float = 0.05


DEFAULT_THRESHOLDS = StageCThresholds()


# ----------------------------------------------------------------------------
# Stage C 固有のメトリクス抽出
# ----------------------------------------------------------------------------
def effective_pt_t_min(
    pt: np.ndarray,
    max_gap_factor: float = MAX_GAP_FACTOR,
) -> float:
    """puncturetracker の最大時刻ギャップ以降の連続区間 start を返す.

    Stage A+B+C 連結データでは Stage A 終端 (t=99 M) → Stage B 開始 (t=261 M)
    の trigger ギャップで unwrap が壊れる。中央値 dt の ``max_gap_factor``
    倍を超える gap が検出されたら、その直後を「有効 t_min」とする。

    ギャップが無ければ ``t[0]`` をそのまま返す。``pt`` が空 or 1-row なら NaN
    もしくは ``t[0]``。

    Args:
        pt: puncturetracker 全 segment 連結配列 (``_simdir.load_puncture_tracker``)。
        max_gap_factor: gap / median(dt) の閾値。

    Returns:
        有効 ``t_min`` (連続区間の start)。
    """
    if pt.size == 0:
        return float("nan")
    t = pt[:, _simdir.PT_TIME_COL]
    if t.size < 2:
        return float(t[0])
    dt = np.diff(t)
    median_dt = np.median(dt)
    big_gap_idx = np.where(dt > max_gap_factor * median_dt)[0]
    if big_gap_idx.size == 0:
        return float(t[0])
    # 最後の大ギャップの直後を有効 start とする
    return float(t[big_gap_idx[-1] + 1])


def detect_psi4_peak(
    sim_dir: _simdir.SimDir,
    radius: float = PSI4_DEFAULT_RADIUS,
    l: int = 2,
    m: int = 2,
) -> dict[str, float]:
    """``mp_psi4.h5`` の (l, m) モード × 抽出半径 r で peak amplitude を検出.

    Returns:
        ``{t_peak, amp_peak, n_samples, t_min, t_max}``。データ不在は NaN。
    """
    t, re_arr, im_arr = _simdir.load_psi4_mode(sim_dir, l, m, radius)
    if t.size == 0:
        return {"t_peak": float("nan"), "amp_peak": float("nan"),
                "n_samples": 0, "t_min": float("nan"), "t_max": float("nan")}
    amp = np.hypot(re_arr, im_arr)
    i_peak = int(np.argmax(amp))
    return {
        "t_peak": float(t[i_peak]),
        "amp_peak": float(amp[i_peak]),
        "n_samples": int(t.size),
        "t_min": float(t[0]),
        "t_max": float(t[-1]),
    }


# ----------------------------------------------------------------------------
# メトリクス収集
# ----------------------------------------------------------------------------
def collect_metrics(
    sim_dir: _simdir.SimDir,
    psi4_radius: float = PSI4_DEFAULT_RADIUS,
    post_merger_delta_M: float = POST_MERGER_DELTA_M,
    n_orbit_t_start: float | None = None,
) -> dict[str, Any]:
    """1 つの sim_dir (もしくは sim_dir 群) から Stage C 比較に必要な全メトリクスを抽出.

    Args:
        sim_dir: simulation top-level (単一 Path/str もしくは Stage A+B+C
            連結用のシーケンス)。
        n_orbit_t_start: 軌道数計算の開始時刻 [M]。``None`` なら
            puncturetracker の最初のサンプル時刻を使用。

    Returns:
        ``{merger_time, post_merger, n_orbit, psi4_peak, time_range,
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

    psi4_peak = detect_psi4_peak(sim_dir, psi4_radius)

    # 完走判定用 time_range (ah1)
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
        "psi4_peak": psi4_peak,
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
    thresholds: StageCThresholds = DEFAULT_THRESHOLDS,
    target_time_M: float = TARGET_TIME_M,
) -> dict[str, Any]:
    """N=16 / N=28 metrics dict から Stage C 全域比較を生成."""
    checks: dict[str, dict[str, Any]] = {}

    # 完走判定: puncturetracker の t_max が target に到達しているか。
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

    # ψ4 peak amplitude (Stage C で初めて捕捉)
    checks["psi4_peak_amplitude"] = _check_pct(
        n16["psi4_peak"]["amp_peak"], n28["psi4_peak"]["amp_peak"],
        thresholds.psi4_peak_pct,
    )

    # ψ4 peak time: merger からの相対時刻で比較 (両 sim の merger 絶対時刻が
    # 異なるので絶対時刻ではなく retarded time で揃える)
    n16_dt = n16["psi4_peak"]["t_peak"] - n16["merger_time_M"]
    n28_dt = n28["psi4_peak"]["t_peak"] - n28["merger_time_M"]
    checks["psi4_peak_time_after_merger"] = _check_abs(
        n16_dt, n28_dt, thresholds.psi4_peak_time_abs,
    )

    return checks


def evaluate_self_consistency(
    sim_dir: _simdir.SimDir,
    merger_time: float,
    thresholds: StageCThresholds = DEFAULT_THRESHOLDS,
    eval_window: tuple[float, float] = (50.0, 500.0),
) -> dict[str, Any]:
    """N=16 単体の拡張 ringdown 帯 self-consistency 判定.

    Stage B (30-70 M 窓) と異なり、Stage C では merger + 50 M から
    merger + 500 M (= 約 t=1425 M, target 1700 M 内) までの長い窓で
    drift を評価できる。
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

    self_consistency が利用不可 (available=False) の場合は無視。
    """
    for c in checks.values():
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
    n16_dir: _simdir.SimDir,
    n28_dir: _simdir.SimDir,
    target_time_M: float = TARGET_TIME_M,
    psi4_radius: float = PSI4_DEFAULT_RADIUS,
    post_merger_delta_M: float = POST_MERGER_DELTA_M,
    thresholds: StageCThresholds = DEFAULT_THRESHOLDS,
) -> dict[str, Any]:
    """両 sim_dir (もしくは Stage A+B+C 連結シーケンス) から比較レポート生成.

    軌道数計算は Stage B と同じく両 sim の puncturetracker 最初のサンプル
    時刻のうち遅い方を共通開始時刻とする。
    """
    pt16 = _simdir.load_puncture_tracker(n16_dir)
    pt28 = _simdir.load_puncture_tracker(n28_dir)
    if pt16.size and pt28.size:
        # 連結データの場合、Stage A → B 境界の trigger ギャップで np.unwrap が
        # 壊れるので「最大ギャップ後の連続区間 start」を有効 t_min として使う。
        common_t_start = max(effective_pt_t_min(pt16), effective_pt_t_min(pt28))
    else:
        common_t_start = None

    n16_metrics = collect_metrics(
        n16_dir, psi4_radius, post_merger_delta_M,
        n_orbit_t_start=common_t_start,
    )
    n28_metrics = collect_metrics(
        n28_dir, psi4_radius, post_merger_delta_M,
        n_orbit_t_start=common_t_start,
    )

    checks = evaluate_checks(n16_metrics, n28_metrics, thresholds, target_time_M)
    sc = evaluate_self_consistency(n16_dir, n16_metrics["merger_time_M"], thresholds)

    return {
        "stage": "C",
        "target_time_M": target_time_M,
        "post_merger_delta_M": post_merger_delta_M,
        "psi4_extraction_radius_M": psi4_radius,
        "official_reference": {
            "merger_time_M": OFFICIAL_MERGER_TIME_M,
            "M_final": OFFICIAL_M_FINAL,
            "chi_final": OFFICIAL_CHI_FINAL,
            "n_orbit": OFFICIAL_N_ORBIT,
        },
        "n16_dir": _stringify_dirs(n16_dir),
        "n28_dir": _stringify_dirs(n28_dir),
        "overall_pass": overall_pass(checks, sc),
        "checks": checks,
        "self_consistency": sc,
        "n16_raw_metrics": _sanitize_for_json(n16_metrics),
        "n28_raw_metrics": _sanitize_for_json(n28_metrics),
    }


def _stringify_dirs(sim_dir: _simdir.SimDir) -> Any:
    """Path/str/sequence を JSON 出力用に str もしくは list[str] に正規化."""
    if isinstance(sim_dir, (str, Path)):
        return str(sim_dir)
    return [str(d) for d in sim_dir]


# ----------------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------------
def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--n16-dirs", type=Path, nargs="+", required=True,
                   help="自前 N=16 simulation top-level (Stage A B C を順に並べる)")
    p.add_argument("--n28-dir", type=Path, required=True,
                   help="Zenodo N=28 reference top-level (extracted/GW150914_28)")
    p.add_argument("--output", "-o", type=Path, required=True,
                   help="JSON 出力パス")
    p.add_argument("--target-time", type=float, default=TARGET_TIME_M,
                   help=f"Stage C target time [M] (デフォルト {TARGET_TIME_M})")
    p.add_argument("--psi4-radius", type=float, default=PSI4_DEFAULT_RADIUS,
                   help=f"ψ4 抽出半径 [M] (デフォルト {PSI4_DEFAULT_RADIUS})")
    p.add_argument("--post-merger-delta", type=float, default=POST_MERGER_DELTA_M,
                   help=f"merger 後評価 offset [M] (デフォルト {POST_MERGER_DELTA_M})")
    p.add_argument("--plot-dir", type=Path, default=None,
                   help="(オプション) plot 出力先")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    report = build_report(
        n16_dir=args.n16_dirs,
        n28_dir=args.n28_dir,
        target_time_M=args.target_time,
        psi4_radius=args.psi4_radius,
        post_merger_delta_M=args.post_merger_delta,
    )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    print(f"[compare_stage_c] wrote JSON: {args.output}")

    if args.plot_dir is not None:
        try:
            from . import plot_stage_c  # 遅延 import
            plot_stage_c.generate_plots(
                n16_dir=args.n16_dirs, n28_dir=args.n28_dir,
                output_dir=args.plot_dir,
                target_time_M=args.target_time,
                psi4_radius=args.psi4_radius,
            )
            print(f"[compare_stage_c] wrote plots to: {args.plot_dir}")
        except ImportError as e:
            print(f"[compare_stage_c] plot generation skipped: {e}", file=sys.stderr)

    print(f"[compare_stage_c] overall_pass = {report['overall_pass']}")
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
