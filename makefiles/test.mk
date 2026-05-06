# SPDX-License-Identifier: GPL-2.0-or-later
# Copyright (C) 2026 Syota Sasaki
# テスト実行ターゲット
# =======================================================
# pytest ベースのユニット/スモークテスト。Level 別に marker で分岐する:
#   smoke : 純 Python テスト (< 1 秒、Cactus 非依存)
#   short : cactus_sim 実行テスト (数分、TwoPunctures 初期データまで)
#
# 既定では Docker コンテナ内で pytest を実行する (cactus_sim / MPI 依存の
# short テストはコンテナでないと skip される)。ホスト側 pytest を直接使う
# 場合は `pytest -m smoke` を手動で叩けば Level 1 のみ走る。

.PHONY: test-smoke
test-smoke: ## Level 1: 純 Python parfile 生成テスト (< 1 秒、コンテナ内)
	$(COMPOSE) exec et python3 -m pytest -m smoke tests/ -v

.PHONY: test-short
test-short: ## Level 1+2: 初期データ smoke まで (数分、要コンテナ起動)
	$(COMPOSE) exec et python3 -m pytest -m "smoke or short" tests/ -v

.PHONY: test-all
test-all: ## 全テスト (Level 1+2 相当、コンテナ内で実行)
	$(COMPOSE) exec et python3 -m pytest tests/ -v

.PHONY: test-host-smoke
test-host-smoke: ## ホスト側 python3 で Level 1 のみ実行 (Docker 不要)
	python3 -m pytest -m smoke tests/ -v
