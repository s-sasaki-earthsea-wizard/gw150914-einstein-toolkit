# SPDX-License-Identifier: GPL-2.0-or-later
# Copyright (C) 2026 Syota Sasaki
"""Level 2: cactus_sim で初期データ生成までを短時間実行するテスト

目的:
    - 生成した .par を Cactus が構文エラーなく読み込める
    - TwoPunctures が initial data 生成フェーズを完走する
    - cctk_itlast=0 で initial data 直後に正常終了する

Cactus 非搭載の環境では自動 skip する。

設計: cactus_sim の 1 回の実行には数分かかるため、module scope の fixture
で一度だけ実行し、複数のアサーションで共有する。

解像度 N について:
    Issue #2 の本来の目標は「N=16 で短時間テスト」だが、公式 rpar の
    grid structure (maxrls=9、Thornburg04 マルチパッチ) は N=28 前提で
    設計されており、N<28 では refinement level 1 が内部 Cartesian パッチ境界を
    越えて Interpolate2 が abort する（2026-04-24 検証）。
    本 Level 2 では rpar 原本を尊重し N=28 を使用する。低 N での実行は
    Phase 3 で grid 調整 (maxrls 低減等) と合わせて取り組む。
    N=28 + cctk_itlast=0 でも初期データのみなら約 6〜7 分で完走する。
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.helpers import cactus_runner
from tests.helpers.parfile import generate_par

pytestmark = [pytest.mark.short]

SIMULATION_NAME = "twopunctures_smoke"


@pytest.fixture(scope="module")
def cactus_initial_data_result(tmp_path_factory, request):
    """cactus_sim を一度だけ実行し、結果を複数テストで共有する

    - N=28: 公式解像度（低 N は rpar の grid 構造と非互換、Phase 3 で対応）
    - overrides:
        * Cactus::terminate = "iteration"  — iteration 基準で停止
        * Cactus::cctk_itlast = 0          — 初期データ直後に停止
        * IO::recover = "no"               — 古い checkpoint 誤認識を防ぐ
    """
    if not cactus_runner.is_cactus_available():
        pytest.skip(
            f"cactus_sim または mpirun が見つかりません "
            f"(CACTUS_SIM={cactus_runner.cactus_sim_path()}, "
            f"MPIRUN={cactus_runner.mpirun_path()})"
        )

    work_dir: Path = tmp_path_factory.mktemp("initial_data")
    parfile = generate_par(
        dest_dir=work_dir,
        n=28,
        simulation_name=SIMULATION_NAME,
        walltime_hours=0.25,
        overrides={
            "Cactus::terminate": "iteration",
            "Cactus::cctk_itlast": 0,
            "IO::recover": "no",
        },
    )
    return cactus_runner.run_cactus(
        parfile=parfile,
        run_dir=work_dir,
        nproc=1,
        timeout=900.0,  # 15 分（N=28 での初期データ所要 6〜7 分 + 余裕）
    )


def test_cactus_sim_exits_cleanly(cactus_initial_data_result) -> None:
    """cactus_sim が正常終了 (rc=0) する"""
    result = cactus_initial_data_result
    assert result.ok, (
        f"cactus_sim が異常終了 (rc={result.returncode})\n"
        f"--- stdout (tail) ---\n{result.stdout[-2000:]}\n"
        f"--- stderr (tail) ---\n{result.stderr[-2000:]}"
    )


def test_twopunctures_was_invoked(cactus_initial_data_result) -> None:
    """ログに TwoPunctures 実行の形跡がある"""
    result = cactus_initial_data_result
    assert "TwoPunctures" in result.stdout, (
        "TwoPunctures の実行ログが見つかりません"
    )


def test_output_directory_created(cactus_initial_data_result) -> None:
    """IO::out_dir で指定したディレクトリに何らかの出力が残る"""
    result = cactus_initial_data_result
    out_dir = result.run_dir / SIMULATION_NAME
    assert out_dir.is_dir(), f"出力ディレクトリ未生成: {out_dir}"

    produced = list(out_dir.iterdir())
    assert len(produced) > 0, "出力ファイル無し"


def test_no_nan_reported(cactus_initial_data_result) -> None:
    """初期データ時点で NaN が発生していない (NaNChecker のエラー無し)"""
    result = cactus_initial_data_result
    # NaNChecker は NaN 発見時に "NaN" を含むエラーメッセージを stderr/stdout に出す
    combined = result.stdout + result.stderr
    assert "found NaNs" not in combined, "初期データに NaN が検出された"
