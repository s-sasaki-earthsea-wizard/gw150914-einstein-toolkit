# Phase 4 解析ターゲット (Stage A 比較)
# =======================================================
# 自前 N=16 run と Zenodo N=28 reference を t=100 M で比較し、
# pass/fail JSON + 時系列 overlay plot を出力する。
#
# 判定ロジックの詳細は ``docs/comparison_method_n16_vs_n28.md`` 参照。

SHELL := /bin/bash

# Stage A 比較に使う sim_dir パス (.env で上書き可能)。
# 自前 N=16 run のデフォルト (Phase 3c-2 投入後に作成される)。
SIM_N16_DIR    ?= simulations/GW150914_n16
ZENODO_N28_DIR ?= data/GW150914_N28_zenodo/extracted/GW150914_28

# 出力先 (.gitignore に登録されている reports/ 配下)。
STAGE_A_OUTPUT_DIR ?= reports/stage_a
STAGE_A_JSON       := $(STAGE_A_OUTPUT_DIR)/pass_fail.json
STAGE_A_PLOT_DIR   := $(STAGE_A_OUTPUT_DIR)/plots

.PHONY: compare-stage-a
compare-stage-a: ## Stage A (t=100 M) 比較: 自前 N=16 vs Zenodo N=28、JSON + plot 出力
	@if [ ! -d "$(SIM_N16_DIR)" ]; then \
	  echo "ERROR: N=16 simulation dir not found: $(SIM_N16_DIR)" >&2; \
	  echo "       Phase 3c-2 (Stage A run) を完走させてください" >&2; \
	  exit 1; \
	fi
	@if [ ! -d "$(ZENODO_N28_DIR)" ]; then \
	  echo "ERROR: Zenodo N=28 dir not found: $(ZENODO_N28_DIR)" >&2; \
	  echo "       'make fetch-zenodo' で取得してください" >&2; \
	  exit 1; \
	fi
	$(COMPOSE) exec et python3 -m scripts.analyze.compare_stage_a \
	  --n16-dir "$(SIM_N16_DIR)" \
	  --n28-dir "$(ZENODO_N28_DIR)" \
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
	  --n28-dir "$(ZENODO_N28_DIR)" \
	  --output "$(STAGE_A_JSON)" \
	  --plot-dir "$(STAGE_A_PLOT_DIR)"

.PHONY: compare-stage-a-sanity
compare-stage-a-sanity: ## Sanity check: Zenodo を両側に渡して全 pass を確認 (host)
	python3 -m scripts.analyze.compare_stage_a \
	  --n16-dir "$(ZENODO_N28_DIR)" \
	  --n28-dir "$(ZENODO_N28_DIR)" \
	  --output "$(STAGE_A_OUTPUT_DIR)/sanity_pass_fail.json" \
	  --plot-dir "$(STAGE_A_OUTPUT_DIR)/sanity_plots"
