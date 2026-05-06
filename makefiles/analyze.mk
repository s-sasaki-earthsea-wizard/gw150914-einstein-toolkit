# SPDX-License-Identifier: GPL-2.0-or-later
# Copyright (C) 2026 Syota Sasaki
# Phase 4 解析ターゲット (Stage A 比較)
# =======================================================
# 自前 N=16 run と Zenodo N=28 reference を t=100 M で比較し、
# pass/fail JSON + 時系列 overlay plot を出力する。
#
# 判定ロジックの詳細は ``docs/comparison_method_n16_vs_n28.md`` 参照。

SHELL := /bin/bash

# Stage A 比較に使う sim_dir パス (.env で上書き可能)。
# 自前 N=16 run のデフォルト (Phase 3c-2 投入後に作成される)。
#
# NOTE: data.mk の ZENODO_N28_DIR は tarball 配置先 (= data/GW150914_N28_zenodo) で、
# 比較スクリプトが必要とする展開後ディレクトリとは別。命名衝突を避けるため
# 専用変数 ZENODO_N28_SIMDIR を導入し、data.mk の値を起点に派生させる。
SIM_N16_DIR        ?= simulations/GW150914_n16
ZENODO_N28_SIMDIR  ?= $(ZENODO_N28_DIR)/extracted/GW150914_28

# 出力先 (.gitignore に登録されている reports/ 配下)。
STAGE_A_OUTPUT_DIR ?= reports/stage_a
STAGE_A_JSON       := $(STAGE_A_OUTPUT_DIR)/pass_fail.json
STAGE_A_PLOT_DIR   := $(STAGE_A_OUTPUT_DIR)/plots

STAGE_B_OUTPUT_DIR ?= reports/stage_b
STAGE_B_JSON       := $(STAGE_B_OUTPUT_DIR)/pass_fail.json
STAGE_B_PLOT_DIR   := $(STAGE_B_OUTPUT_DIR)/plots
SIM_N16_STAGE_B_DIR ?= simulations/gw150914-n16-stage-b

STAGE_C_OUTPUT_DIR ?= reports/stage_c
STAGE_C_JSON       := $(STAGE_C_OUTPUT_DIR)/pass_fail.json
STAGE_C_PLOT_DIR   := $(STAGE_C_OUTPUT_DIR)/plots
SIM_N16_STAGE_A_DIR ?= simulations/gw150914-n16-stage-a
SIM_N16_STAGE_C_DIR ?= simulations/gw150914-n16-stage-c

# Stage C 比較は merger event を含む完全な時系列が必要なため、
# Stage A + B + C を順に並べて連結 reader に渡す。
SIM_N16_FULL_DIRS  ?= $(SIM_N16_STAGE_A_DIR) $(SIM_N16_STAGE_B_DIR) $(SIM_N16_STAGE_C_DIR)

.PHONY: compare-stage-a
compare-stage-a: ## Stage A (t=100 M) 比較: 自前 N=16 vs Zenodo N=28、JSON + plot 出力
	@if [ ! -d "$(SIM_N16_DIR)" ]; then \
	  echo "ERROR: N=16 simulation dir not found: $(SIM_N16_DIR)" >&2; \
	  echo "       Phase 3c-2 (Stage A run) を完走させてください" >&2; \
	  exit 1; \
	fi
	@if [ ! -d "$(ZENODO_N28_SIMDIR)" ]; then \
	  echo "ERROR: Zenodo N=28 simdir not found: $(ZENODO_N28_SIMDIR)" >&2; \
	  echo "       'make fetch-zenodo-n28 && make extract-zenodo-n28' で取得・展開してください" >&2; \
	  exit 1; \
	fi
	$(COMPOSE) exec et python3 -m scripts.analyze.compare_stage_a \
	  --n16-dir "$(SIM_N16_DIR)" \
	  --n28-dir "$(ZENODO_N28_SIMDIR)" \
	  --output "$(STAGE_A_JSON)" \
	  --plot-dir "$(STAGE_A_PLOT_DIR)"

.PHONY: compare-stage-a-host
compare-stage-a-host: ## Stage A 比較をホスト側 python で実行 (Docker 不要、要 numpy/h5py/matplotlib)
	@if [ ! -d "$(SIM_N16_DIR)" ]; then \
	  echo "ERROR: N=16 simulation dir not found: $(SIM_N16_DIR)" >&2; \
	  exit 1; \
	fi
	python3 -m scripts.analyze.compare_stage_a \
	  --n16-dir "$(SIM_N16_DIR)" \
	  --n28-dir "$(ZENODO_N28_SIMDIR)" \
	  --output "$(STAGE_A_JSON)" \
	  --plot-dir "$(STAGE_A_PLOT_DIR)"

.PHONY: compare-stage-a-sanity
compare-stage-a-sanity: ## Sanity check: Zenodo を両側に渡して全 pass を確認 (host)
	python3 -m scripts.analyze.compare_stage_a \
	  --n16-dir "$(ZENODO_N28_SIMDIR)" \
	  --n28-dir "$(ZENODO_N28_SIMDIR)" \
	  --output "$(STAGE_A_OUTPUT_DIR)/sanity_pass_fail.json" \
	  --plot-dir "$(STAGE_A_OUTPUT_DIR)/sanity_plots"

# ---------------------------------------------------------------------------
# Stage B 比較 (Phase 4 / Issue #4 タスク E)
# ---------------------------------------------------------------------------
.PHONY: compare-stage-b
compare-stage-b: ## Stage B (1000 M) 比較: merger time / 最終 BH / 軌道数 / ψ4 pre-merger
	@if [ ! -d "$(SIM_N16_STAGE_B_DIR)" ]; then \
	  echo "ERROR: N=16 Stage B simulation dir not found: $(SIM_N16_STAGE_B_DIR)" >&2; \
	  echo "       Phase 3c-3 (Stage B run) を完走させてください" >&2; \
	  exit 1; \
	fi
	@if [ ! -d "$(ZENODO_N28_SIMDIR)" ]; then \
	  echo "ERROR: Zenodo N=28 simdir not found: $(ZENODO_N28_SIMDIR)" >&2; \
	  exit 1; \
	fi
	$(COMPOSE) exec et python3 -m scripts.analyze.compare_stage_b \
	  --n16-dir "$(SIM_N16_STAGE_B_DIR)" \
	  --n28-dir "$(ZENODO_N28_SIMDIR)" \
	  --output "$(STAGE_B_JSON)" \
	  --plot-dir "$(STAGE_B_PLOT_DIR)"

.PHONY: compare-stage-b-host
compare-stage-b-host: ## Stage B 比較をホスト側 python で実行 (Docker 不要)
	@if [ ! -d "$(SIM_N16_STAGE_B_DIR)" ]; then \
	  echo "ERROR: N=16 Stage B simulation dir not found: $(SIM_N16_STAGE_B_DIR)" >&2; \
	  exit 1; \
	fi
	python3 -m scripts.analyze.compare_stage_b \
	  --n16-dir "$(SIM_N16_STAGE_B_DIR)" \
	  --n28-dir "$(ZENODO_N28_SIMDIR)" \
	  --output "$(STAGE_B_JSON)" \
	  --plot-dir "$(STAGE_B_PLOT_DIR)"

.PHONY: compare-stage-b-sanity
compare-stage-b-sanity: ## Sanity check: Zenodo を両側に渡して全 pass を確認 (host)
	python3 -m scripts.analyze.compare_stage_b \
	  --n16-dir "$(ZENODO_N28_SIMDIR)" \
	  --n28-dir "$(ZENODO_N28_SIMDIR)" \
	  --output "$(STAGE_B_OUTPUT_DIR)/sanity_pass_fail.json" \
	  --plot-dir "$(STAGE_B_OUTPUT_DIR)/sanity_plots"

# ---------------------------------------------------------------------------
# Stage C 比較 (Phase 4 / Issue #4 タスク F): full simulation A+B+C 連結
# ---------------------------------------------------------------------------
.PHONY: compare-stage-c
compare-stage-c: ## Stage C (1700 M) 比較: A+B+C 連結 vs Zenodo / ψ4 peak / ringdown 拡張
	@for d in $(SIM_N16_FULL_DIRS); do \
	  if [ ! -d "$$d" ]; then \
	    echo "ERROR: N=16 simulation dir not found: $$d" >&2; \
	    echo "       Stage A/B/C 全てを完走させてください" >&2; \
	    exit 1; \
	  fi; \
	done
	@if [ ! -d "$(ZENODO_N28_SIMDIR)" ]; then \
	  echo "ERROR: Zenodo N=28 simdir not found: $(ZENODO_N28_SIMDIR)" >&2; \
	  exit 1; \
	fi
	$(COMPOSE) exec et python3 -m scripts.analyze.compare_stage_c \
	  --n16-dirs $(SIM_N16_FULL_DIRS) \
	  --n28-dir "$(ZENODO_N28_SIMDIR)" \
	  --output "$(STAGE_C_JSON)" \
	  --plot-dir "$(STAGE_C_PLOT_DIR)"

.PHONY: compare-stage-c-host
compare-stage-c-host: ## Stage C 比較をホスト側 python で実行 (Docker 不要)
	@for d in $(SIM_N16_FULL_DIRS); do \
	  if [ ! -d "$$d" ]; then \
	    echo "ERROR: N=16 simulation dir not found: $$d" >&2; \
	    exit 1; \
	  fi; \
	done
	python3 -m scripts.analyze.compare_stage_c \
	  --n16-dirs $(SIM_N16_FULL_DIRS) \
	  --n28-dir "$(ZENODO_N28_SIMDIR)" \
	  --output "$(STAGE_C_JSON)" \
	  --plot-dir "$(STAGE_C_PLOT_DIR)"

.PHONY: compare-stage-c-sanity
compare-stage-c-sanity: ## Sanity check: Zenodo を両側に渡して全 pass を確認 (host)
	python3 -m scripts.analyze.compare_stage_c \
	  --n16-dirs "$(ZENODO_N28_SIMDIR)" \
	  --n28-dir "$(ZENODO_N28_SIMDIR)" \
	  --output "$(STAGE_C_OUTPUT_DIR)/sanity_pass_fail.json" \
	  --plot-dir "$(STAGE_C_OUTPUT_DIR)/sanity_plots"
