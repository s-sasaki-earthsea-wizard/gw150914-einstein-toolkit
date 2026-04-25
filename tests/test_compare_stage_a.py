"""Phase 4 Stage A 比較ロジックのユニットテスト (Issue #4 タスク C4).

スコープ:
    1. Zenodo reader が A3/A5 reference 値と一致する値を返す
    2. Stage A 比較ロジック (snapshot pass/fail, self-consistency)
    3. JSON 出力スキーマの不変性
    4. fault injection (閾値外で正しく fail)

Zenodo データ未取得環境では module レベルで skip する。
"""

from __future__ import annotations

import copy
import json
import math
from pathlib import Path

import numpy as np
import pytest

from scripts.analyze import _simdir, compare_stage_a, load_zenodo_n28

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


@pytest.fixture(scope="module")
def zenodo_metrics(zenodo_base: Path) -> dict:
    return compare_stage_a.collect_metrics(zenodo_base, t_target=100.0)


# ============================================================================
# 1. Reader correctness (against A3/A5 reference values)
# ============================================================================
class TestZenodoReader:
    def test_find_segments_returns_six(self, zenodo_base: Path) -> None:
        segs = load_zenodo_n28.find_segments(zenodo_base)
        assert len(segs) == 6
        assert all(s.is_dir() for s in segs)
        assert [s.parent.name for s in segs] == [f"output-000{i}" for i in range(6)]

    def test_bh_diagnostics_shape_and_time(self, zenodo_base: Path) -> None:
        ah1 = load_zenodo_n28.load_bh_diagnostics(zenodo_base, ah_index=1)
        ah2 = load_zenodo_n28.load_bh_diagnostics(zenodo_base, ah_index=2)
        assert ah1.ndim == 2 and ah1.shape[1] >= 28
        assert ah2.ndim == 2 and ah2.shape[1] >= 28
        # t は 0 から 900+ M まで連続して伸びる
        assert ah1[0, _simdir.BH_TIME_COL] == pytest.approx(0.0, abs=1e-3)
        assert ah1[-1, _simdir.BH_TIME_COL] > 900.0

    def test_qlm_scalars_shape(self, zenodo_base: Path) -> None:
        qlm = load_zenodo_n28.load_qlm_scalars(zenodo_base)
        assert qlm.ndim == 2 and qlm.shape[1] >= 67
        assert qlm[0, _simdir.QLM_TIME_COL] == pytest.approx(0.0, abs=1e-3)

    def test_psi4_radii_match_zenodo(self, zenodo_base: Path) -> None:
        radii = load_zenodo_n28.list_psi4_radii(zenodo_base, l=2, m=2)
        assert radii == [100.0, 115.0, 136.0, 167.0, 214.0, 300.0, 500.0]

    def test_psi4_22_r100_initial_zero(self, zenodo_base: Path) -> None:
        """t=0 時点では波が r=100 に届いていない → ψ4 ≈ 0."""
        t, re_arr, im_arr = load_zenodo_n28.load_psi4_mode(zenodo_base, l=2, m=2, r=100.0)
        assert t.size > 0
        assert abs(re_arr[0]) < 1e-3
        assert abs(im_arr[0]) < 1e-3

    def test_invalid_ah_index_raises(self, zenodo_base: Path) -> None:
        with pytest.raises(ValueError):
            load_zenodo_n28.load_bh_diagnostics(zenodo_base, ah_index=0)
        with pytest.raises(ValueError):
            load_zenodo_n28.load_bh_diagnostics(zenodo_base, ah_index=3)

    def test_missing_sim_dir_raises(self) -> None:
        with pytest.raises(FileNotFoundError):
            _simdir.find_segments("/nonexistent/path/zzz")


class TestFlatLayoutFallback:
    """Phase 3c-2 自前 N=16 run は SimFactory を介さない単一 Cactus 起動のため
    ``output-NNNN`` を持たない flat layout になる。``find_segments`` が
    marker file を見て sim_dir 自体を 1 segment として返すか検証.
    """

    def test_flat_dir_with_psi4_marker_returns_self(self, tmp_path) -> None:
        (tmp_path / "mp_psi4.h5").touch()
        segs = _simdir.find_segments(tmp_path)
        assert segs == [tmp_path]

    def test_flat_dir_with_qlm_marker_returns_self(self, tmp_path) -> None:
        (tmp_path / "quasilocalmeasures-qlm_scalars..asc").touch()
        segs = _simdir.find_segments(tmp_path)
        assert segs == [tmp_path]

    def test_flat_dir_with_bh_diag_marker_returns_self(self, tmp_path) -> None:
        (tmp_path / "BH_diagnostics.ah1.gp").touch()
        segs = _simdir.find_segments(tmp_path)
        assert segs == [tmp_path]

    def test_empty_dir_returns_empty(self, tmp_path) -> None:
        """marker file も output-* も無ければ空リスト (NotFoundError ではない)"""
        segs = _simdir.find_segments(tmp_path)
        assert segs == []

    def test_segmented_layout_takes_priority(self, tmp_path) -> None:
        """output-* と marker file の両方があれば segmented を優先"""
        seg_inner = tmp_path / "output-0000" / "sim"
        seg_inner.mkdir(parents=True)
        (tmp_path / "mp_psi4.h5").touch()  # marker は無視される
        segs = _simdir.find_segments(tmp_path)
        assert segs == [seg_inner]


class TestReferenceValues:
    """A3/A5 で確定した t=100 M reference 値と reader 出力が一致するか.

    Issue #4 の表 (タスク A3+A5) からの pinned 値。reader を変更しても
    値が変わらないことを保証する regression test。
    """

    def test_horizon_mass_bh1(self, zenodo_metrics: dict) -> None:
        assert zenodo_metrics["qlm_bh1"]["m_horizon"] == pytest.approx(0.5539, abs=5e-4)

    def test_horizon_mass_bh2(self, zenodo_metrics: dict) -> None:
        assert zenodo_metrics["qlm_bh2"]["m_horizon"] == pytest.approx(0.4462, abs=5e-4)

    def test_chi_bh1(self, zenodo_metrics: dict) -> None:
        assert zenodo_metrics["qlm_bh1"]["chi"] == pytest.approx(+0.3102, abs=1e-4)

    def test_chi_bh2(self, zenodo_metrics: dict) -> None:
        assert zenodo_metrics["qlm_bh2"]["chi"] == pytest.approx(-0.4604, abs=1e-4)

    def test_separation_D(self, zenodo_metrics: dict) -> None:
        assert zenodo_metrics["D"] == pytest.approx(9.773, abs=1e-2)

    def test_orbital_angle(self, zenodo_metrics: dict) -> None:
        assert zenodo_metrics["orbital_angle"] == pytest.approx(2.694, abs=2e-2)

    def test_psi4_22_amplitude_at_r100(self, zenodo_metrics: dict) -> None:
        assert zenodo_metrics["psi4_22"]["amplitude"] == pytest.approx(1.67e-5, rel=2e-2)

    def test_psi4_22_phase_at_r100(self, zenodo_metrics: dict) -> None:
        assert zenodo_metrics["psi4_22"]["phase"] == pytest.approx(-0.674, abs=5e-2)

    def test_m_irreducible_bh1(self, zenodo_metrics: dict) -> None:
        # Issue #4 表: BH1 m_irr = 0.5470 M
        assert zenodo_metrics["ah1"]["m_irreducible"] == pytest.approx(0.5470, abs=2e-3)


# ============================================================================
# 2. chi_dimensionless 単体
# ============================================================================
class TestChiDimensionless:
    def test_kerr_extreme_limit(self) -> None:
        # 物理的に許される極限値 a/M = 1 → χ = 1
        assert _simdir.chi_dimensionless(j=1.0, m_horizon=1.0) == pytest.approx(1.0)

    def test_zero_mass_returns_nan(self) -> None:
        result = _simdir.chi_dimensionless(j=0.5, m_horizon=0.0)
        assert math.isnan(result)

    def test_array_input(self) -> None:
        j = np.array([0.0, 0.31, -0.46])
        m = np.array([1.0, 1.0, 1.0])
        chi = _simdir.chi_dimensionless(j, m)
        assert np.allclose(chi, j)


# ============================================================================
# 3. 比較ロジック: 正常 (sanity) + fault injection
# ============================================================================
class TestEvaluateChecks:
    """``evaluate_checks`` の挙動を、合成 metrics dict で検証."""

    def _ref_metrics(self) -> dict:
        """Zenodo A3/A5 値ベースの synthetic metrics."""
        return {
            "t_target": 100.0,
            "ah1": {"centroid_x": -3.900, "centroid_y": +1.901, "centroid_z": 0.0,
                    "m_irreducible": 0.5470},
            "ah2": {"centroid_x": +4.908, "centroid_y": -2.332, "centroid_z": 0.0,
                    "m_irreducible": 0.4335},
            "D": 9.773,
            "orbital_angle": 2.694,
            "qlm_bh1": {"m_horizon": 0.5539, "J": 0.0951, "m_irreducible": 0.5470, "chi": +0.3102},
            "qlm_bh2": {"m_horizon": 0.4462, "J": -0.0916, "m_irreducible": 0.4335, "chi": -0.4604},
            "psi4_22": {"re": 1.31e-5, "im": -1.04e-5, "amplitude": 1.67e-5, "phase": -0.674},
            "time_range": (0.0, 246.0),
        }

    def test_identical_metrics_all_pass(self) -> None:
        ref = self._ref_metrics()
        checks = compare_stage_a.evaluate_checks(ref, ref)
        for name, c in checks.items():
            if name in compare_stage_a.PROVISIONAL_CHECKS:
                assert c["pass"] is None, f"{name} should be provisional"
            else:
                assert c["pass"] is True, f"{name} failed: {c}"

    def test_psi4_amplitude_is_provisional(self) -> None:
        ref = self._ref_metrics()
        checks = compare_stage_a.evaluate_checks(ref, ref)
        amp = checks["psi4_22_amplitude"]
        assert amp["pass"] is None
        assert "provisional" in amp.get("note", "").lower()

    def test_separation_just_within_threshold(self) -> None:
        ref = self._ref_metrics()
        n16 = copy.deepcopy(ref)
        # 9% 偏差 (閾値 10% 内)
        n16["D"] = ref["D"] * 1.09
        checks = compare_stage_a.evaluate_checks(n16, ref)
        assert checks["separation_D"]["pass"] is True
        assert abs(checks["separation_D"]["delta_pct"]) < 10.0

    def test_separation_just_outside_threshold(self) -> None:
        ref = self._ref_metrics()
        n16 = copy.deepcopy(ref)
        # 11% 偏差 (閾値 10% 外)
        n16["D"] = ref["D"] * 1.11
        checks = compare_stage_a.evaluate_checks(n16, ref)
        assert checks["separation_D"]["pass"] is False

    def test_horizon_mass_tight_threshold(self) -> None:
        """horizon mass は ±0.5% と厳しい. 1% ずれで fail."""
        ref = self._ref_metrics()
        n16 = copy.deepcopy(ref)
        n16["qlm_bh1"]["m_horizon"] = ref["qlm_bh1"]["m_horizon"] * 1.01
        checks = compare_stage_a.evaluate_checks(n16, ref)
        assert checks["m_horizon_bh1"]["pass"] is False

    def test_chi_abs_threshold_boundary(self) -> None:
        """χ は ±0.005 絶対値. 0.004 偏差で pass, 0.006 で fail."""
        ref = self._ref_metrics()
        n16 = copy.deepcopy(ref)
        n16["qlm_bh1"]["chi"] = ref["qlm_bh1"]["chi"] + 0.004
        assert compare_stage_a.evaluate_checks(n16, ref)["chi_bh1"]["pass"] is True
        n16["qlm_bh1"]["chi"] = ref["qlm_bh1"]["chi"] + 0.006
        assert compare_stage_a.evaluate_checks(n16, ref)["chi_bh1"]["pass"] is False

    def test_completion_fails_when_t_max_short(self) -> None:
        ref = self._ref_metrics()
        n16 = copy.deepcopy(ref)
        n16["time_range"] = (0.0, 50.0)  # 100 M に届かない
        checks = compare_stage_a.evaluate_checks(n16, ref, target_time_M=100.0)
        assert checks["completion"]["pass"] is False

    def test_nan_metric_marked_as_fail(self) -> None:
        ref = self._ref_metrics()
        n16 = copy.deepcopy(ref)
        n16["D"] = float("nan")
        checks = compare_stage_a.evaluate_checks(n16, ref)
        assert checks["separation_D"]["pass"] is False

    def test_overall_pass_ignores_provisional(self) -> None:
        """ψ4 振幅が大きくずれても overall_pass は True (provisional のため)."""
        ref = self._ref_metrics()
        n16 = copy.deepcopy(ref)
        n16["psi4_22"]["amplitude"] = ref["psi4_22"]["amplitude"] * 0.3  # 70% 減
        checks = compare_stage_a.evaluate_checks(n16, ref)
        # checks 自体は異常値を記録するが pass=None
        assert checks["psi4_22_amplitude"]["pass"] is None
        # overall_pass は他の check が全部 True なので True
        assert compare_stage_a.overall_pass(checks, {"available": False}) is True


class TestSelfConsistency:
    def test_zenodo_self_consistency_passes(self, zenodo_base: Path) -> None:
        sc = compare_stage_a.evaluate_self_consistency(zenodo_base, t_max=100.0)
        assert sc["available"] is True
        for k, v in sc.items():
            if k == "available":
                continue
            assert isinstance(v, dict)
            assert v["pass"] is True, f"{k} drift exceeded threshold: {v}"

    def test_self_consistency_unavailable_for_empty_dir(self, tmp_path: Path) -> None:
        # 空 dir → segments 検出も失敗
        with pytest.raises(ValueError):
            compare_stage_a.evaluate_self_consistency(tmp_path)


# ============================================================================
# 4. JSON 出力スキーマ + sanity end-to-end
# ============================================================================
class TestBuildReport:
    def test_zenodo_vs_zenodo_all_pass(self, zenodo_base: Path) -> None:
        report = compare_stage_a.build_report(
            n16_dir=zenodo_base, n28_dir=zenodo_base, t_target=100.0,
        )
        assert report["overall_pass"] is True
        assert report["stage"] == "A"
        assert report["target_time_M"] == 100.0
        assert "checks" in report and "self_consistency" in report

    def test_report_is_json_serializable(self, zenodo_base: Path, tmp_path: Path) -> None:
        report = compare_stage_a.build_report(zenodo_base, zenodo_base)
        out = tmp_path / "r.json"
        with out.open("w") as f:
            json.dump(report, f)  # 失敗すると TypeError
        loaded = json.loads(out.read_text())
        assert loaded["overall_pass"] is True

    def test_report_schema_has_required_keys(self, zenodo_base: Path) -> None:
        report = compare_stage_a.build_report(zenodo_base, zenodo_base)
        required_top = {"stage", "target_time_M", "psi4_extraction_radius_M",
                        "n16_dir", "n28_dir", "overall_pass", "checks", "self_consistency"}
        assert required_top.issubset(report.keys())
        required_checks = {"completion", "separation_D", "orbital_angle",
                           "m_irreducible_bh1", "m_irreducible_bh2",
                           "m_horizon_bh1", "m_horizon_bh2",
                           "chi_bh1", "chi_bh2",
                           "psi4_22_phase", "psi4_22_amplitude"}
        assert required_checks.issubset(report["checks"].keys())

    def test_nan_values_serialized_as_null(self, tmp_path: Path) -> None:
        # 故意に欠落した sim_dir で raw_metrics に NaN が混じる場合
        # → JSON では null になることを確認
        nan_obj = {"x": float("nan"), "y": 1.0, "nested": {"z": float("nan")}}
        sanitized = compare_stage_a._sanitize_for_json(nan_obj)
        assert sanitized == {"x": None, "y": 1.0, "nested": {"z": None}}
        json.dumps(sanitized)  # 失敗しないこと
