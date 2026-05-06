# SPDX-License-Identifier: GPL-2.0-or-later
# Copyright (C) 2026 Syota Sasaki
"""Phase 4 Stage B 比較ロジックのユニットテスト (Issue #4 タスク E).

スコープ:
    1. ah_index=3 (common horizon) reader の正常動作
    2. puncturetracker reader と軌道角・軌道数計算
    3. detect_merger_time / compute_post_merger_state / compute_pre_merger_psi4_amplitude
    4. evaluate_checks の境界条件 (pass/fail/provisional)
    5. JSON sanity (Zenodo×Zenodo で全 pass)

Zenodo データ未取得環境では module レベルで skip する。
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pytest

from scripts.analyze import _simdir, compare_stage_b, load_zenodo_n28

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
# 1. ah3 reader (common horizon)
# ============================================================================
class TestAh3Reader:
    def test_ah3_index_accepted(self, zenodo_base: Path) -> None:
        """ah_index=3 が valid (Stage B 用に許可)."""
        ah3 = _simdir.load_bh_diagnostics(zenodo_base, ah_index=3)
        assert ah3.ndim == 2 and ah3.shape[1] >= 28

    def test_ah3_appears_post_merger(self, zenodo_base: Path) -> None:
        """common horizon は merger 近傍 (公式 899 M) で初検出される."""
        ah3 = _simdir.load_bh_diagnostics(zenodo_base, ah_index=3)
        t_first = ah3[0, _simdir.BH_TIME_COL]
        # 公式 899 M ± 30 M 程度 (Zenodo N=28 実測 ≈ 898.7 M)
        assert 850.0 < t_first < 950.0

    def test_invalid_ah_index_4_raises(self, zenodo_base: Path) -> None:
        with pytest.raises(ValueError):
            _simdir.load_bh_diagnostics(zenodo_base, ah_index=4)


# ============================================================================
# 2. puncturetracker reader
# ============================================================================
class TestPunctureTracker:
    def test_puncturetracker_loads(self, zenodo_base: Path) -> None:
        pt = _simdir.load_puncture_tracker(zenodo_base)
        assert pt.ndim == 2 and pt.shape[1] >= 44  # col 43 = BH2.z

    def test_puncturetracker_initial_positions(self, zenodo_base: Path) -> None:
        """t=0 で BH1 ≈ +4.46 M, BH2 ≈ -5.54 M (公式 D=10, q=36/29 から)."""
        pt = _simdir.load_puncture_tracker(zenodo_base)
        assert pt[0, _simdir.PT_TIME_COL] == pytest.approx(0.0, abs=1e-3)
        assert pt[0, _simdir.PT_BH1_X_COL] == pytest.approx(4.4615, abs=1e-3)
        assert pt[0, _simdir.PT_BH2_X_COL] == pytest.approx(-5.5385, abs=1e-3)
        assert pt[0, _simdir.PT_BH1_Y_COL] == pytest.approx(0.0, abs=1e-3)
        assert pt[0, _simdir.PT_BH2_Y_COL] == pytest.approx(0.0, abs=1e-3)


# ============================================================================
# 3. Stage B 固有メトリクス抽出
# ============================================================================
class TestStageBMetrics:
    def test_detect_merger_time_zenodo(self, zenodo_base: Path) -> None:
        t_merger = compare_stage_b.detect_merger_time(zenodo_base)
        # Zenodo N=28 実測 898.712 M (公式 899)
        assert 895.0 < t_merger < 905.0

    def test_detect_merger_time_returns_nan_when_no_ah3(self, tmp_path) -> None:
        """ah3.gp が無い (= 未 merger) sim_dir で NaN を返す."""
        # marker file のみ作成、ah3.gp は不在
        (tmp_path / "BH_diagnostics.ah1.gp").touch()
        result = compare_stage_b.detect_merger_time(tmp_path)
        assert math.isnan(result)

    def test_compute_orbit_count_positive(self, zenodo_base: Path) -> None:
        """Zenodo フル inspiral (0 → 898 M) で約 6 軌道を観測."""
        n_orbit = compare_stage_b.compute_orbit_count(zenodo_base, 0.0, 898.0)
        # 公式 6 軌道 ± 1 軌道 (puncturetracker 開始位置は initial separation D=10)
        assert 5.0 < n_orbit < 7.0

    def test_compute_orbit_count_window_outside_range_returns_nan(
        self, zenodo_base: Path,
    ) -> None:
        result = compare_stage_b.compute_orbit_count(zenodo_base, -10.0, 50.0)
        assert math.isnan(result)

    def test_post_merger_state_zenodo(self, zenodo_base: Path) -> None:
        """Zenodo merger + 50 M の m_h ≈ 0.95, χ ≈ 0.69 (公式 ringdown 初期値)."""
        t_merger = compare_stage_b.detect_merger_time(zenodo_base)
        post = compare_stage_b.compute_post_merger_state(zenodo_base, t_merger, 50.0)
        # ringdown 早期: m_h は遷移中なので幅広く許容
        assert 0.85 < post["m_horizon"] < 1.0
        # chi は ringdown 早期で 0.6 〜 0.75 range
        assert 0.5 < post["chi"] < 0.85

    def test_post_merger_state_nan_input(self, zenodo_base: Path) -> None:
        post = compare_stage_b.compute_post_merger_state(zenodo_base, float("nan"), 50.0)
        assert all(math.isnan(v) for v in post.values())

    def test_pre_merger_psi4_amplitude(self, zenodo_base: Path) -> None:
        """merger 直前 30 M の |ψ4₂₂| amplitude が正の有限値を返す."""
        t_merger = compare_stage_b.detect_merger_time(zenodo_base)
        psi4 = compare_stage_b.compute_pre_merger_psi4_amplitude(
            zenodo_base, t_merger, 30.0, 100.0,
        )
        assert psi4["n_samples"] > 0
        assert 0.0 < psi4["amp_peak"] < 1e-2  # inspiral 末期 amplitude オーダー


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
            "psi4_pre_merger": {"t_peak": 870.0, "amp_peak": 1e-4, "amp_mean": 5e-5, "n_samples": 30},
            "psi4_pre_merger_window_M": 30.0,
            "psi4_radius_M": 100.0,
            "time_range": (0.0, 1700.0),
            "ah3_t_range": (merger_time, 1700.0),
            "puncture_t_range": (0.0, 1700.0),
        }

    def test_identical_metrics_pass(self) -> None:
        m = self._baseline_metrics()
        checks = compare_stage_b.evaluate_checks(m, m)
        for name, c in checks.items():
            if name in compare_stage_b.PROVISIONAL_CHECKS:
                continue
            assert c["pass"] is True, f"{name} should pass: {c}"

    def test_merger_time_off_by_30M_passes(self) -> None:
        """merger_time +30 M (= 3.3% of 900) は ±5% 以内なので pass."""
        n28 = self._baseline_metrics(900.0)
        n16 = self._baseline_metrics(930.0)
        checks = compare_stage_b.evaluate_checks(n16, n28)
        assert checks["merger_time"]["pass"] is True

    def test_merger_time_off_by_60M_fails(self) -> None:
        """merger_time +60 M (= 6.7% of 900) は ±5% 超なので fail."""
        n28 = self._baseline_metrics(900.0)
        n16 = self._baseline_metrics(960.0)
        checks = compare_stage_b.evaluate_checks(n16, n28)
        assert checks["merger_time"]["pass"] is False

    def test_chi_final_off_by_05_fails(self) -> None:
        """chi_final 差 0.5 abs は ±0.10 abs 超なので fail."""
        n28 = self._baseline_metrics()
        n16 = self._baseline_metrics()
        n16["post_merger"]["chi"] = 0.20
        checks = compare_stage_b.evaluate_checks(n16, n28)
        assert checks["chi_final"]["pass"] is False

    def test_psi4_pre_merger_is_provisional(self) -> None:
        """ψ4 pre-merger は閾値を大きく超えても overall_pass を落とさない."""
        n28 = self._baseline_metrics()
        n16 = self._baseline_metrics()
        n16["psi4_pre_merger"]["amp_peak"] = 1e-1  # +1000% 異常値
        checks = compare_stage_b.evaluate_checks(n16, n28)
        assert checks["psi4_pre_merger_amplitude"]["pass"] is None
        # overall_pass は true のまま (provisional は除外)
        sc = {"available": False}
        assert compare_stage_b.overall_pass(checks, sc) is True


# ============================================================================
# 5. Sanity check (Zenodo × Zenodo): 全 pass + JSON schema
# ============================================================================
class TestSanityZenodoVsZenodo:
    def test_build_report_zenodo_self_compare(self, zenodo_base: Path, tmp_path: Path) -> None:
        report = compare_stage_b.build_report(
            n16_dir=zenodo_base, n28_dir=zenodo_base,
        )
        assert report["overall_pass"] is True
        # JSON シリアライズ可能
        json_str = json.dumps(report)
        assert len(json_str) > 100

    def test_report_has_expected_top_level_keys(self, zenodo_base: Path) -> None:
        report = compare_stage_b.build_report(
            n16_dir=zenodo_base, n28_dir=zenodo_base,
        )
        for key in (
            "stage", "target_time_M", "post_merger_delta_M",
            "official_reference", "overall_pass", "checks",
            "self_consistency", "n16_raw_metrics", "n28_raw_metrics",
        ):
            assert key in report, f"missing top-level key: {key}"
        assert report["stage"] == "B"

    def test_report_checks_keys(self, zenodo_base: Path) -> None:
        report = compare_stage_b.build_report(
            n16_dir=zenodo_base, n28_dir=zenodo_base,
        )
        expected_checks = {
            "completion", "merger_time", "m_final", "chi_final",
            "n_orbit", "psi4_pre_merger_amplitude",
        }
        assert set(report["checks"].keys()) == expected_checks
