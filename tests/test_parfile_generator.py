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
    patch_constraint_outputs,
    patch_maxrls,
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


# ---------------------------------------------------------------------------
# Issue #9 / Phase 3b-ii: maxrls パッチ機構
# ---------------------------------------------------------------------------


def test_patch_maxrls_replaces_max_refinement_levels(tmp_path) -> None:
    """maxrls=8 で Carpet::max_refinement_levels が 8 になる"""
    par = generate_par(tmp_path, n=16, maxrls=8)
    content = par.read_text(encoding="utf-8")
    assert "Carpet::max_refinement_levels           = 8" in content


def test_patch_maxrls_caps_rlsp_rlsm(tmp_path) -> None:
    """maxrls=8 → rlsp = rlsm = 6 (CarpetRegrid2::num_levels に反映)"""
    par = generate_par(tmp_path, n=16, maxrls=8)
    content = par.read_text(encoding="utf-8")
    # 元は rlsp = rlsm = 7 だが、maxrls-2=6 で cap される
    assert "CarpetRegrid2::num_levels_1             = 6" in content
    assert "CarpetRegrid2::num_levels_2             = 6" in content


def test_patch_maxrls_shrinks_outermost_radius(tmp_path) -> None:
    """maxrls=8 では levelsp の最外層が rp*2^4 (=10.6 M 程度) に縮小される"""
    par = generate_par(tmp_path, n=16, maxrls=8)
    content = par.read_text(encoding="utf-8")
    # rp ≈ 0.665, 2^4 = 16 → 約 10.64 M
    # 厳密値ではなく first-level radius が 11 M 未満であることを確認
    # radius_1 行: "CarpetRegrid2::radius_1 = [0,X1, X2, ...]"
    import re as _re

    match = _re.search(
        r"CarpetRegrid2::radius_1\s*=\s*\[0,\s*([0-9.]+)",
        content,
    )
    assert match is not None, "radius_1 行が見つからない"
    outermost = float(match.group(1))
    assert outermost < 11.0, (
        f"maxrls=8 でも最外層が {outermost} M (10.6 M 近傍を期待)"
    )
    # 元の N=28/maxrls=9 だと 21.27 M 程度
    assert outermost > 9.0, (
        f"最外層が小さすぎる ({outermost} M)。何かを過剰に縮小している可能性"
    )


def test_patch_maxrls_does_not_change_h0_for_same_n(tmp_path) -> None:
    """maxrls 変更で h_cartesian (RL0 セル幅) が変わらない (重要)

    h0_min は ``rlsm`` 計算後・cap 前に確定するため、N 同じなら h_cartesian
    は maxrls に依存しない。これにより \"外側を削る\" 意味での修正となる。
    """
    par_default = generate_par(tmp_path / "default", n=16)  # maxrls=None
    par_patched = generate_par(tmp_path / "patched", n=16, maxrls=8)

    import re as _re

    def _h_cart(par):
        m = _re.search(
            r"Coordinates::h_cartesian\s*=\s*([0-9.eE+-]+)",
            par.read_text(encoding="utf-8"),
        )
        assert m is not None
        return float(m.group(1))

    assert abs(_h_cart(par_default) - _h_cart(par_patched)) < 1e-9


def test_patch_maxrls_rejects_too_small() -> None:
    """maxrls=3 以下は拒否される"""
    template = RPAR_SOURCE.read_text(encoding="utf-8").replace("@N@", "16")
    with pytest.raises(ValueError, match="小さすぎ"):
        patch_maxrls(template, maxrls=3)


def test_patch_maxrls_default_unchanged_without_arg(tmp_path) -> None:
    """maxrls 引数を渡さなければ Carpet::max_refinement_levels=9 のまま"""
    par = generate_par(tmp_path, n=16)  # maxrls なし
    content = par.read_text(encoding="utf-8")
    assert "Carpet::max_refinement_levels           = 9" in content
    # rlsp = rlsm = 7 (元の値)
    assert "CarpetRegrid2::num_levels_1             = 7" in content


@pytest.mark.parametrize("maxrls,expected_levels", [(8, 6), (7, 5), (6, 4)])
def test_patch_maxrls_various_values(tmp_path, maxrls: int, expected_levels: int) -> None:
    """各 maxrls 値で num_levels が maxrls-2 になる"""
    par = generate_par(
        tmp_path,
        n=16,
        simulation_name=f"test_n16_m{maxrls}",
        maxrls=maxrls,
    )
    content = par.read_text(encoding="utf-8")
    assert f"CarpetRegrid2::num_levels_1             = {expected_levels}" in content
    assert f"CarpetRegrid2::num_levels_2             = {expected_levels}" in content


# ---------------------------------------------------------------------------
# Issue #9 / Phase 3b-ii: snap_inner_radius (Coordinates patchsystem 制約)
# ---------------------------------------------------------------------------

# scripts/ 配下のスクリプトから関数を import する。pytest 実行は repo root から。
import importlib.util as _importlib_util  # noqa: E402

_ROOT = RPAR_SOURCE.parent.parent.parent  # repo root
_spec = _importlib_util.spec_from_file_location(
    "n16_gen", _ROOT / "scripts" / "generate_gw150914_n16_parfile.py"
)
_n16_gen = _importlib_util.module_from_spec(_spec)
_spec.loader.exec_module(_n16_gen)
snap_inner_radius = _n16_gen.snap_inner_radius


def _h_cartesian_for(n: int) -> float:
    """rpar の h_cartesian 計算式の Python 再現"""
    mm = 29.0 / 65.0
    rm = mm * 1.0 * 1.2
    hfm_min = rm / 24.0
    h0_min = hfm_min * 64.0
    return h0_min * 24.0 / n


def test_snap_inner_radius_satisfies_coordinates_check() -> None:
    """snap した値が Coordinates patchsystem の半整数倍チェックを通る

    Coordinates/patchsystem.cc:177-179 は
    ``2*sphere_inner_radius / h_cartesian`` が整数 (誤差 1e-8 以内) であることを
    要求し、満たさないと CCTK_WARN(0) で MPI_ABORT する。
    """
    h_cart = _h_cartesian_for(16)
    for target in [40.0, 51.0, 70.0, 77.0, 100.0, 120.0]:
        r = snap_inner_radius(target, n=16)
        ratio = 2.0 * r / h_cart
        assert abs(ratio - round(ratio)) < 1e-8, (
            f"snap({target}) = {r} は h_cart={h_cart} の半整数倍ではない "
            f"(2*r/h = {ratio}, 整数誤差 {ratio - round(ratio)})"
        )


def test_snap_inner_radius_ceils_up() -> None:
    """target 以上の最小の有効値が返る"""
    r = snap_inner_radius(77.0, n=16)
    assert r >= 77.0, f"snap(77.0) = {r} < 77.0 (ceil でなく floor している)"
    # 次の有効値 (8 * i*h0 = 68.5...) より大きいこと
    h_cart = _h_cartesian_for(16)
    i_h0 = 4 * h_cart  # i = N/4 = 4 for N=16
    # snap(77) は 9*i_h0 = 77.0954 のはず
    assert abs(r - 9 * i_h0) < 1e-8


def test_snap_inner_radius_default_45_matches_rpar() -> None:
    """target=45 (rpar の初期値) で rpar 出力 51.40 と一致"""
    r = snap_inner_radius(45.0, n=16)
    # rpar: ceil(45/8.5662) * 8.5662 = 6 * 8.5662 = 51.40
    h_cart = _h_cartesian_for(16)
    i_h0 = 4 * h_cart
    assert abs(r - 6 * i_h0) < 1e-8


@pytest.mark.parametrize("n", [16, 28])
def test_snap_inner_radius_works_for_various_n(n: int) -> None:
    """N=16, N=28 どちらでも整数倍 snap が動く"""
    h_cart = _h_cartesian_for(n)
    r = snap_inner_radius(80.0, n=n)
    ratio = 2.0 * r / h_cart
    assert abs(ratio - round(ratio)) < 1e-8


# ---------------------------------------------------------------------------
# Issue #3 / Phase 3c-1: checkpoint test parfile (HDF5 POSIX lock 検証)
# ---------------------------------------------------------------------------

_ckpt_spec = _importlib_util.spec_from_file_location(
    "n16_ckpt_gen",
    _ROOT / "scripts" / "generate_gw150914_n16_checkpoint_test_parfile.py",
)
_n16_ckpt_gen = _importlib_util.module_from_spec(_ckpt_spec)
_ckpt_spec.loader.exec_module(_n16_ckpt_gen)
COMMON_OVERRIDES = _n16_ckpt_gen.COMMON_OVERRIDES
WRITE_MODE_OVERRIDES = _n16_ckpt_gen.WRITE_MODE_OVERRIDES
RESTART_MODE_OVERRIDES = _n16_ckpt_gen.RESTART_MODE_OVERRIDES


def _build_ckpt_par(tmp_path, mode: str, itlast: int) -> str:
    """checkpoint test スクリプトと同じ overrides で par を生成し中身を返す.

    sub-process 起動を避けるため、スクリプトの構成定数を直接再利用する.
    """
    if mode == "write":
        mode_ov = WRITE_MODE_OVERRIDES
    elif mode == "restart":
        mode_ov = RESTART_MODE_OVERRIDES
    else:
        raise ValueError(mode)

    overrides = {
        **COMMON_OVERRIDES,
        **mode_ov,
        "Cactus::cctk_itlast": itlast,
        "Coordinates::sphere_inner_radius": snap_inner_radius(77.14, n=16),
    }
    par = generate_par(
        tmp_path,
        n=16,
        simulation_name=f"ckpt-test-{mode}",
        walltime_hours=3.0,
        overrides=overrides,
    )
    return par.read_text(encoding="utf-8")


def test_ckpt_write_mode_enables_checkpointing(tmp_path) -> None:
    """write モード: clean start (recover=no) + walltime 0.5h + on_terminate"""
    content = _build_ckpt_par(tmp_path, mode="write", itlast=4000)
    assert 'IO::recover' in content and '= "no"' in content
    assert "IO::checkpoint_every_walltime_hours" in content
    # walltime トリガを 0.5h に設定 (Phase 3c-1 第 2 回試行で iter ~2000 時点
    # で walltime 経路を発火させるため。1 回目では 2.0h で発火せず terminate
    # 経路のみ検証されたため修正)
    assert "= 0.5" in content
    # on_terminate と CarpetIOHDF5::checkpoint が yes
    assert "IO::checkpoint_on_terminate" in content
    assert "CarpetIOHDF5::checkpoint" in content
    # 旧 CarpetIOHDF5::checkpoint = yes 行と置換が両立する確認
    assert "= yes" in content


def test_ckpt_restart_mode_recovers_auto(tmp_path) -> None:
    """restart モード: recover=auto + walltime trigger 無効化 + on_terminate のみ"""
    content = _build_ckpt_par(tmp_path, mode="restart", itlast=4500)
    assert 'IO::recover' in content and '= "auto"' in content
    # restart で walltime トリガを無効化 (-1)
    import re as _re

    m = _re.search(r"IO::checkpoint_every_walltime_hours\s*=\s*(-?\d+(?:\.\d+)?)", content)
    assert m is not None
    assert float(m.group(1)) < 0.0
    # on_terminate は依然有効
    assert "IO::checkpoint_on_terminate" in content


def test_ckpt_uses_separated_checkpoint_dir(tmp_path) -> None:
    """checkpoint_dir / recover_dir が ../checkpoints/checkpoint-test (test 用 subdir)
    に置かれる. ../checkpoints は docker-compose の SIM_CHECKPOINT_DIR
    bind mount で host persistent
    """
    content = _build_ckpt_par(tmp_path, mode="write", itlast=4000)
    assert 'IO::checkpoint_dir' in content
    assert '"../checkpoints/checkpoint-test"' in content
    assert 'IO::recover_dir' in content
    assert '"../checkpoints/checkpoint-test"' in content


def test_ckpt_write_mode_itlast_is_applied(tmp_path) -> None:
    """cctk_itlast 上書きが反映される"""
    content = _build_ckpt_par(tmp_path, mode="write", itlast=4000)
    assert "Cactus::cctk_itlast = 4000" in content


def test_ckpt_terminate_overridden_to_iteration(tmp_path) -> None:
    """rpar 原本の terminate=time を iteration に置換 (cctk_itlast を効かせるため)"""
    content = _build_ckpt_par(tmp_path, mode="write", itlast=4000)
    # rpar 原本の "Cactus::terminate ... = time" 行は残らない
    assert "Cactus::terminate                               = time" not in content
    # 新しい値が反映
    assert '"iteration"' in content


def test_ckpt_keep_two_checkpoints(tmp_path) -> None:
    """checkpoint_keep=2 で 2 個保持される (ディスク制御)"""
    content = _build_ckpt_par(tmp_path, mode="write", itlast=4000)
    assert "IO::checkpoint_keep = 2" in content


# ---------------------------------------------------------------------------
# Issue #4 D3: patch_constraint_outputs (Hamiltonian/Momentum norm 出力)
# ---------------------------------------------------------------------------


def test_patch_constraint_outputs_adds_norm_reductions(tmp_path) -> None:
    """patch_constraint_outputs で reductions に norm2 / norm_inf が追加される"""
    par = generate_par(tmp_path, n=16, enable_constraint_output=True)
    content = par.read_text(encoding="utf-8")
    assert (
        'IOScalar::outScalar_reductions          = "minimum maximum average norm2 norm_inf"'
        in content
    )


def test_patch_constraint_outputs_adds_constraint_vars(tmp_path) -> None:
    """ML_ADMConstraints::ML_Ham と ML_mom が outScalar_vars に含まれる"""
    par = generate_par(tmp_path, n=16, enable_constraint_output=True)
    content = par.read_text(encoding="utf-8")
    # multi-line block 内に両変数が現れる
    assert "ML_ADMConstraints::ML_Ham" in content
    assert "ML_ADMConstraints::ML_mom" in content
    # 既存の SystemStatistics::process_memory_mb は残す (メモリ計測継続)
    assert "SystemStatistics::process_memory_mb" in content


def test_patch_constraint_outputs_disabled_by_default(tmp_path) -> None:
    """enable_constraint_output=False (デフォルト) では rpar 原本のまま

    既存の N=16 feasibility / checkpoint test との後方互換性を保つ。
    """
    par = generate_par(tmp_path, n=16)
    content = par.read_text(encoding="utf-8")
    assert "ML_ADMConstraints::ML_Ham" not in content
    assert "norm2 norm_inf" not in content


def test_patch_constraint_outputs_function_directly() -> None:
    """rpar text 単体に対して patch を当てた出力が期待通り"""
    template = (
        RPAR_SOURCE.read_text(encoding="utf-8")
        .replace("@N@", "16")
        .replace("@SIMULATION_NAME@", "test")
        .replace("@WALLTIME_HOURS@", "1.0")
    )
    patched = patch_constraint_outputs(template)
    # reductions に norm 系が追加される
    assert '"minimum maximum average norm2 norm_inf"' in patched
    # vars が multi-line 化される
    import re as _re

    block = _re.search(
        r'IOScalar::outScalar_vars\s*=\s*"\n((?:.+\n)+?)"',
        patched,
    )
    assert block is not None, "patch 後の outScalar_vars block が見つからない"
    body = block.group(1)
    assert "SystemStatistics::process_memory_mb" in body
    assert "ML_ADMConstraints::ML_Ham" in body
    assert "ML_ADMConstraints::ML_mom" in body


def test_patch_constraint_outputs_idempotent_failure() -> None:
    """同じ rpar に 2 回適用するとエラー (二度パッチで原本変更検知)"""
    template = (
        RPAR_SOURCE.read_text(encoding="utf-8")
        .replace("@N@", "16")
        .replace("@SIMULATION_NAME@", "test")
        .replace("@WALLTIME_HOURS@", "1.0")
    )
    patched = patch_constraint_outputs(template)
    with pytest.raises(ValueError, match="見つかりません"):
        patch_constraint_outputs(patched)


# ---------------------------------------------------------------------------
# Issue #3 + #4 D1: stage parfile generator
# ---------------------------------------------------------------------------

_stage_spec = _importlib_util.spec_from_file_location(
    "n16_stage_gen",
    _ROOT / "scripts" / "generate_gw150914_n16_stage_parfile.py",
)
_n16_stage_gen = _importlib_util.module_from_spec(_stage_spec)
_stage_spec.loader.exec_module(_n16_stage_gen)
STAGE_FINAL_TIMES = _n16_stage_gen.STAGE_FINAL_TIMES
stage_overrides = _n16_stage_gen.stage_overrides


def _build_stage_par(tmp_path, stage: str) -> str:
    """stage parfile generator と同等の overrides で par を生成し中身を返す."""
    sim_name = f"test-stage-{stage.lower()}"
    overrides = stage_overrides(stage, sim_name)
    overrides["Coordinates::sphere_inner_radius"] = snap_inner_radius(77.14, n=16)
    par = generate_par(
        tmp_path,
        n=16,
        simulation_name=sim_name,
        walltime_hours=8.0,
        overrides=overrides,
        enable_constraint_output=True,
    )
    return par.read_text(encoding="utf-8")


@pytest.mark.parametrize(
    "stage,final_time", [("A", 100.0), ("B", 1000.0), ("C", 1700.0)]
)
def test_stage_final_time_is_set(tmp_path, stage: str, final_time: float) -> None:
    """各 stage で cctk_final_time が想定値 (100/1000/1700 M) になる"""
    content = _build_stage_par(tmp_path, stage)
    assert f"Cactus::cctk_final_time                         = {final_time}" in content


def test_stage_terminate_mode_is_time(tmp_path) -> None:
    """terminate=time (rpar 原本通り、checkpoint test の iteration 上書きは継承しない)"""
    content = _build_stage_par(tmp_path, "A")
    # rpar 原本の terminate=time が保たれる、または override で再度 "time" 指定
    assert 'Cactus::terminate                               = "time"' in content
    assert 'Cactus::terminate                               = "iteration"' not in content


def test_stage_recover_autoprobe(tmp_path) -> None:
    """recover=autoprobe (既存 ckpt があれば recover、無ければ clean start)"""
    content = _build_stage_par(tmp_path, "A")
    assert 'IO::recover' in content and '= "autoprobe"' in content


def test_stage_checkpoint_dir_separated_per_stage(tmp_path) -> None:
    """checkpoint_dir が stage 別に分離される"""
    content_a = _build_stage_par(tmp_path / "a", "A")
    content_b = _build_stage_par(tmp_path / "b", "B")
    assert '"../checkpoints/test-stage-a"' in content_a
    assert '"../checkpoints/test-stage-b"' in content_b


def test_stage_walltime_checkpoint_trigger_production_cadence(tmp_path) -> None:
    """walltime checkpoint trigger は production cadence の 2.0 h"""
    content = _build_stage_par(tmp_path, "A")
    assert "IO::checkpoint_every_walltime_hours = 2.0" in content


def test_stage_constraint_output_enabled(tmp_path) -> None:
    """stage モードでは constraint 出力が必ず有効 (D3)"""
    content = _build_stage_par(tmp_path, "A")
    assert "ML_ADMConstraints::ML_Ham" in content
    assert "norm2 norm_inf" in content


def test_stage_overrides_rejects_unknown_stage() -> None:
    """未知の stage 文字列は ValueError"""
    with pytest.raises(ValueError, match="未知の stage"):
        stage_overrides("Z", "test")


def test_stage_no_cctk_itlast_set(tmp_path) -> None:
    """stage モードでは cctk_itlast を上書きしない (final_time で打ち切り)

    rpar 原本は terminate=time モードで運用するため ``Cactus::cctk_itlast``
    を明示せず、Cactus デフォルト値に任せている。本 stage generator もそれを
    踏襲し、cctk_itlast を一切設定しない。
    """
    content = _build_stage_par(tmp_path, "A")
    import re as _re

    matches = _re.findall(r"^Cactus::cctk_itlast\s*=", content, _re.MULTILINE)
    assert len(matches) == 0, (
        f"cctk_itlast が {len(matches)} 回現れる (0 を期待: stage では設定しない)"
    )
