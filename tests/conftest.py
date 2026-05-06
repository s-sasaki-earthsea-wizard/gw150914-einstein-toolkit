# SPDX-License-Identifier: GPL-2.0-or-later
# Copyright (C) 2026 Syota Sasaki
"""pytest 共通設定とフィクスチャ"""

from __future__ import annotations

import pytest

from tests.helpers import cactus_runner


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers",
        "smoke: 純 Python の高速テスト (< 1 秒目安、Cactus 非依存)",
    )
    config.addinivalue_line(
        "markers",
        "short: cactus_sim を実行する短時間テスト (数分、TwoPunctures まで)",
    )


@pytest.fixture(scope="session")
def cactus_available() -> bool:
    """cactus_sim / mpirun が揃っているかを返す"""
    return cactus_runner.is_cactus_available()


@pytest.fixture()
def skip_if_no_cactus(cactus_available: bool) -> None:
    """Cactus 非搭載環境（ホスト側 pytest など）でテストを skip する"""
    if not cactus_available:
        pytest.skip(
            f"cactus_sim または mpirun が見つかりません "
            f"(CACTUS_SIM={cactus_runner.cactus_sim_path()}, "
            f"MPIRUN={cactus_runner.mpirun_path()})"
        )
