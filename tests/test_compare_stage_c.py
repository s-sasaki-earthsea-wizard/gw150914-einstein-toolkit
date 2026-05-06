# SPDX-License-Identifier: GPL-2.0-or-later
# Copyright (C) 2026 Syota Sasaki
"""Phase 4 Stage C 比較ロジックのユニットテスト (Issue #4 タスク F).

スコープ:
    1. _simdir.find_segments のシーケンス入力 (Stage A+B+C 連結)
    2. effective_pt_t_min の gap 検出 (連続 / 大ギャップ両ケース)
    3. detect_psi4_peak の正常動作と空入力時の NaN
    4. evaluate_checks の境界条件 (Stage C 固有: ψ4 peak / peak time)
    5. Sanity (Zenodo×Zenodo) で全 check pass + JSON schema

Zenodo データ未取得環境では module レベルで skip する。
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pytest

from scripts.analyze import _simdir, compare_stage_c, load_zenodo_n28

pytestmark = pytest.mark.smoke


REPO_ROOT = Path(__file__).resolve().parent.parent
ZENODO_DEFAULT = REPO_ROOT / load_zenodo_n28.DEFAULT_ZENODO_BASE


# ----------------------------------------------------------------------------
# fixtures
# ----------------------------------------------------------------------------
@pytest.fixture(scope="module")
def zenodo_base() -> Path:
    if not ZENODO_DEFAULT.is_dir():
        pytest.skip(f"Zenodo data not available: {ZENODO_DEFAULT}")
    return ZENODO_DEFAULT


# ============================================================================
# 1. find_segments の sequence 入力
# ============================================================================
class TestFindSegmentsSequence:
    def test_single_dir_unchanged(self, zenodo_base: Path) -> None:
        """単一 Path 入力時の振る舞いは従来と同じ (後方互換)."""
        segs = _simdir.find_segments(zenodo_base)
        assert len(segs) > 0
        assert all(s.is_dir() for s in segs)

    def test_sequence_input_concatenates(self, zenodo_base: Path) -> None:
        """同じ dir を 2 回渡すと segment 数が 2 倍になる."""
        single = _simdir.find_segments(zenodo_base)
        doubled = _simdir.find_segments([zenodo_base, zenodo_base])
        assert len(doubled) == 2 * len(single)

    def test_sequence_preserves_order(self, zenodo_base: Path, tmp_path: Path) -> None:
        """シーケンス入力は要素順を保つ (Stage A → B → C 連結用)."""
        # marker file を持つ flat dir を作成
        flat = tmp_path / "flat"
        flat.mkdir()
        (flat / "BH_diagnostics.ah1.gp").touch()
        segs = _simdir.find_segments([flat, zenodo_base])
        assert segs[0] == flat  # 最初の要素は flat dir
        # 続く segment は zenodo_base 由来
        assert all(zenodo_base in s.parents or s == zenodo_base for s in segs[1:])

    def test_loaders_accept_sequence(self, zenodo_base: Path) -> None:
        """load_* 系が sequence 入力を受け付ける (シグネチャ確認)."""
        ah1 = _simdir.load_bh_diagnostics([zenodo_base], 1)
        qlm = _simdir.load_qlm_scalars([zenodo_base])
        pt = _simdir.load_puncture_tracker([zenodo_base])
        t, re_arr, im_arr = _simdir.load_psi4_mode([zenodo_base], 2, 2, 100.0)
        assert ah1.size > 0 and qlm.size > 0 and pt.size > 0 and t.size > 0


# ============================================================================
# 2. effective_pt_t_min
# ============================================================================
class TestEffectivePtTMin:
    @staticmethod
    def _make_pt(t: np.ndarray) -> np.ndarray:
        """テスト用の最小 puncturetracker 配列を作成 (PT_TIME_COL のみ意味あり)."""
        n_cols = max(_simdir.PT_BH2_Z_COL, _simdir.PT_TIME_COL) + 1
        pt = np.zeros((t.size, n_cols))
        pt[:, _simdir.PT_TIME_COL] = t
        return pt

    def test_continuous_returns_t0(self) -> None:
        """ギャップ無しなら t[0] をそのまま返す."""
        t = np.linspace(0, 1000, 1000)
        pt = self._make_pt(t)
        assert compare_stage_c.effective_pt_t_min(pt) == pytest.approx(0.0)

    def test_large_gap_returns_post_gap_start(self) -> None:
        """中央値 dt の 5 倍を超えるギャップを検出して直後の時刻を返す."""
        # 0..99 (dt=1) → 261..1000 (dt=1)、99 → 261 のギャップ = 162 (>> 5)
        t = np.concatenate([np.arange(0, 100), np.arange(261, 1001)])
        pt = self._make_pt(t)
        result = compare_stage_c.effective_pt_t_min(pt)
        assert result == pytest.approx(261.0, abs=1e-6)

    def test_small_gap_kept(self) -> None:
        """中央値 dt の 5 倍に達しないギャップは無視される."""
        # dt=1 が大半、ところどころ dt=3 (= 3×median) があるが閾値 5×median 未満
        t = np.concatenate([np.arange(0, 50), np.arange(53, 100)])
        pt = self._make_pt(t)
        assert compare_stage_c.effective_pt_t_min(pt) == pytest.approx(0.0)

    def test_empty_returns_nan(self) -> None:
        empty = np.empty((0, 0))
        assert math.isnan(compare_stage_c.effective_pt_t_min(empty))

    def test_single_row_returns_t0(self) -> None:
        pt = self._make_pt(np.array([5.0]))
        assert compare_stage_c.effective_pt_t_min(pt) == pytest.approx(5.0)

    def test_multiple_gaps_returns_last(self) -> None:
        """複数大ギャップがある場合、最後のギャップ後を返す."""
        # 0..49 → 200..249 → 500..549
        t = np.concatenate([np.arange(0, 50), np.arange(200, 250), np.arange(500, 550)])
        pt = self._make_pt(t)
        assert compare_stage_c.effective_pt_t_min(pt) == pytest.approx(500.0)


# ============================================================================
# 3. detect_psi4_peak
# ============================================================================
class TestDetectPsi4Peak:
    def test_peak_zenodo_r100(self, zenodo_base: Path) -> None:
        """Zenodo N=28 の ψ4(2,2, r=100) peak は merger + ~115 M ≈ 1013 M."""
        peak = compare_stage_c.detect_psi4_peak(zenodo_base, radius=100.0)
        # peak 時刻 ≈ 1013 M ± 30
        assert 980.0 < peak["t_peak"] < 1050.0
        # peak amplitude ≈ 7e-4 オーダー
        assert 1e-4 < peak["amp_peak"] < 1e-3
        assert peak["n_samples"] > 1000

    def test_peak_missing_dir(self, tmp_path: Path) -> None:
        """データ無し sim_dir で NaN を返す (find_segments で例外を投げない)."""
        (tmp_path / "BH_diagnostics.ah1.gp").touch()  # marker のみ
        peak = compare_stage_c.detect_psi4_peak(tmp_path, radius=100.0)
        assert math.isnan(peak["t_peak"])
        assert peak["n_samples"] == 0


# ============================================================================
# 4. evaluate_checks の境界条件
# ============================================================================
class TestEvaluateChecks:
    @staticmethod
    def _baseline_metrics(merger_time: float = 900.0) -> dict:
        """テスト用の架空メトリクス dict (両 run 同一値)."""
        return {
            "merger_time_M": merger_time,
            "post_merger": {"m_horizon": 0.95, "J": 0.622, "m_irreducible": 0.85, "chi": 0.69},
            "post_merger_delta_M": 50.0,
            "n_orbit": {"value": 6.0, "t_start": 0.0, "t_end": merger_time},
            "psi4_peak": {
                "t_peak": merger_time + 115.0,
                "amp_peak": 7.3e-4,
                "n_samples": 3000,
                "t_min": 0.0,
                "t_max": 1700.0,
            },
            "psi4_radius_M": 100.0,
            "time_range": (0.0, 1700.0),
            "ah3_t_range": (merger_time, 1700.0),
            "puncture_t_range": (0.0, 1700.0),
        }

    def test_identical_metrics_pass(self) -> None:
        m = self._baseline_metrics()
        checks = compare_stage_c.evaluate_checks(m, m)
        for name, c in checks.items():
            assert c["pass"] is True, f"{name} should pass: {c}"

    def test_psi4_peak_amplitude_threshold(self) -> None:
        """ψ4 peak amplitude +5% は pass、+15% は fail (閾値 ±10%)."""
        n28 = self._baseline_metrics()
        n16_5pct = self._baseline_metrics()
        n16_5pct["psi4_peak"]["amp_peak"] = 7.3e-4 * 1.05
        assert compare_stage_c.evaluate_checks(n16_5pct, n28)["psi4_peak_amplitude"]["pass"] is True

        n16_15pct = self._baseline_metrics()
        n16_15pct["psi4_peak"]["amp_peak"] = 7.3e-4 * 1.15
        assert compare_stage_c.evaluate_checks(n16_15pct, n28)["psi4_peak_amplitude"]["pass"] is False

    def test_psi4_peak_time_after_merger_threshold(self) -> None:
        """ψ4 peak time (merger 揃え) ±15 M は pass、±25 M は fail (閾値 ±20)."""
        n28 = self._baseline_metrics()
        n16_15M = self._baseline_metrics()
        n16_15M["psi4_peak"]["t_peak"] = n16_15M["merger_time_M"] + 115.0 + 15.0
        assert compare_stage_c.evaluate_checks(n16_15M, n28)["psi4_peak_time_after_merger"]["pass"] is True

        n16_25M = self._baseline_metrics()
        n16_25M["psi4_peak"]["t_peak"] = n16_25M["merger_time_M"] + 115.0 + 25.0
        assert compare_stage_c.evaluate_checks(n16_25M, n28)["psi4_peak_time_after_merger"]["pass"] is False

    def test_chi_final_tighter_than_stage_b(self) -> None:
        """chi_final 差 0.05 abs は ±0.02 閾値超なので fail (Stage B では ±0.10 で pass)."""
        n28 = self._baseline_metrics()
        n16 = self._baseline_metrics()
        n16["post_merger"]["chi"] = 0.69 + 0.05
        checks = compare_stage_c.evaluate_checks(n16, n28)
        assert checks["chi_final"]["pass"] is False

    def test_completion_fails_below_target(self) -> None:
        n28 = self._baseline_metrics()
        n16 = self._baseline_metrics()
        n16["puncture_t_range"] = (0.0, 1500.0)  # 1700 に届かない
        checks = compare_stage_c.evaluate_checks(n16, n28, target_time_M=1700.0)
        assert checks["completion"]["pass"] is False


# ============================================================================
# 5. Sanity check (Zenodo × Zenodo): 全 pass + JSON schema
# ============================================================================
class TestSanityZenodoVsZenodo:
    def test_build_report_zenodo_self_compare(self, zenodo_base: Path) -> None:
        report = compare_stage_c.build_report(
            n16_dir=zenodo_base, n28_dir=zenodo_base,
        )
        assert report["overall_pass"] is True
        json_str = json.dumps(report)
        assert len(json_str) > 100

    def test_report_has_expected_top_level_keys(self, zenodo_base: Path) -> None:
        report = compare_stage_c.build_report(
            n16_dir=zenodo_base, n28_dir=zenodo_base,
        )
        for key in (
            "stage", "target_time_M", "post_merger_delta_M",
            "psi4_extraction_radius_M", "official_reference", "overall_pass",
            "checks", "self_consistency", "n16_raw_metrics", "n28_raw_metrics",
        ):
            assert key in report, f"missing top-level key: {key}"
        assert report["stage"] == "C"

    def test_report_checks_keys(self, zenodo_base: Path) -> None:
        report = compare_stage_c.build_report(
            n16_dir=zenodo_base, n28_dir=zenodo_base,
        )
        expected_checks = {
            "completion", "merger_time", "m_final", "chi_final",
            "n_orbit", "psi4_peak_amplitude", "psi4_peak_time_after_merger",
        }
        assert set(report["checks"].keys()) == expected_checks

    def test_report_self_consistency_extended_window(self, zenodo_base: Path) -> None:
        """Stage C self_consistency 評価窓は 50-500 M (Stage B の 30-70 M より広い)."""
        report = compare_stage_c.build_report(
            n16_dir=zenodo_base, n28_dir=zenodo_base,
        )
        sc = report["self_consistency"]
        assert sc["available"] is True
        assert sc["eval_window_M"] == [50.0, 500.0]
