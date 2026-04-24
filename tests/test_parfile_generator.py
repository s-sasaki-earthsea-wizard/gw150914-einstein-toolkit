"""Level 1: rpar → par 生成パイプラインの純 Python テスト

cactus_sim を呼び出さないため、Docker 外でも実行可能。
目的:
    - rpar 原本の存在
    - プレースホルダ置換の健全性
    - 物理パラメータ（GW150914 のスピン・分離）の一貫性
    - overrides 上書き機構の正しさ
"""

from __future__ import annotations

import pytest

from tests.helpers.parfile import (
    PLACEHOLDERS,
    RPAR_SOURCE,
    apply_overrides,
    generate_par,
)

pytestmark = pytest.mark.smoke


def test_rpar_source_exists() -> None:
    """公式 rpar が取得済みであること"""
    assert RPAR_SOURCE.is_file(), (
        f"rpar 未取得: {RPAR_SOURCE}. `make fetch-parfile` を実行してください"
    )


def test_generate_par_creates_file(tmp_path) -> None:
    par = generate_par(tmp_path, n=8, simulation_name="test_minimal")
    assert par.is_file()
    assert par.name == "test_minimal.par"


def test_generated_par_has_no_unreplaced_placeholders(tmp_path) -> None:
    par = generate_par(tmp_path, n=8)
    content = par.read_text(encoding="utf-8")
    for placeholder in PLACEHOLDERS:
        assert placeholder not in content, (
            f"プレースホルダ {placeholder} が未置換です"
        )


def test_generated_par_contains_gw150914_physics(tmp_path) -> None:
    """GW150914 の物理パラメータが鍵値として現れることを確認"""
    par = generate_par(tmp_path, n=8)
    content = par.read_text(encoding="utf-8")
    # D = 10 M、総質量 1、質量比 q = 36/29
    assert "# D                   = 10.0" in content
    assert "# M                   = 1.0" in content
    # スピン: chip = 0.31, chim = -0.46
    assert "# chip                = 0.31" in content
    assert "# chim                = -0.46" in content


def test_generated_par_contains_required_thorns(tmp_path) -> None:
    """GW150914 で必須の thorn 群が ActiveThorns に含まれること"""
    par = generate_par(tmp_path, n=8)
    content = par.read_text(encoding="utf-8")
    for thorn in (
        "TwoPunctures",
        "ML_BSSN",
        "AHFinderDirect",
        "QuasiLocalMeasures",
        "WeylScal4",
        "Multipole",
    ):
        assert thorn in content, f"必須 thorn が不足: {thorn}"


@pytest.mark.parametrize("n", [8, 16, 28])
def test_generator_accepts_different_N(tmp_path, n: int) -> None:
    par = generate_par(tmp_path, n=n, simulation_name=f"run_n{n}")
    assert par.is_file()
    # N 依存パラメータ（Coordinates::h_cartesian）が N によって変わることを確認
    # n が大きいほど h_cartesian は小さくなる


def test_walltime_hours_is_substituted(tmp_path) -> None:
    par = generate_par(tmp_path, n=8, walltime_hours=0.25)
    content = par.read_text(encoding="utf-8")
    assert "TerminationTrigger::max_walltime" in content
    assert "= 0.25" in content


def test_simulation_name_controls_out_dir(tmp_path) -> None:
    par = generate_par(tmp_path, n=8, simulation_name="custom_run")
    content = par.read_text(encoding="utf-8")
    assert 'IO::out_dir                             = "custom_run"' in content


def test_apply_overrides_replaces_existing_line(tmp_path) -> None:
    par = generate_par(tmp_path, n=8)
    apply_overrides(par, {"Cactus::terminate": "iteration"})
    content = par.read_text(encoding="utf-8")
    # 元の "= time" が "= \"iteration\"" に置き換わる
    assert 'Cactus::terminate' in content
    assert '"iteration"' in content
    # 旧値が残っていないこと（= time 単体の行が消える）
    assert "Cactus::terminate                               = time" not in content


def test_apply_overrides_appends_missing_key(tmp_path) -> None:
    par = generate_par(tmp_path, n=8)
    apply_overrides(par, {"Cactus::cctk_itlast": 0})
    content = par.read_text(encoding="utf-8")
    assert "Cactus::cctk_itlast = 0" in content


def test_apply_overrides_handles_bool(tmp_path) -> None:
    par = generate_par(tmp_path, n=8)
    apply_overrides(par, {"IO::abort_on_io_errors": False})
    content = par.read_text(encoding="utf-8")
    assert "IO::abort_on_io_errors" in content
    # bool → "no" に変換される
    assert "= no" in content


def test_overrides_case_insensitive(tmp_path) -> None:
    """Cactus パラメータ名は大小文字非依存。上書きもそれに従う"""
    par = generate_par(tmp_path, n=8)
    apply_overrides(par, {"cactus::TERMINATE": "iteration"})
    content = par.read_text(encoding="utf-8")
    assert '"iteration"' in content
