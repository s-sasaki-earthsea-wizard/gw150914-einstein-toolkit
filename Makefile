# GW150914 Einstein Toolkit Simulation
# ======================================
# 各ターゲットの詳細は `make help` を参照。
# サブMakefile(makefiles/*.mk) に機能別に分割している。

.DEFAULT_GOAL := help

# サブMakefileを自動インクルード。
include makefiles/docker.mk

.PHONY: help
help: ## このヘルプを表示
	@echo "GW150914 Einstein Toolkit Simulation — 利用可能なターゲット:"
	@echo ""
	@awk 'BEGIN{FS=":.*?## "} \
		/^##@/ { printf "\n\033[1m%s\033[0m\n", substr($$0, 5); next } \
		/^[a-zA-Z0-9_.-]+:.*?## / { printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2 }' \
		$(MAKEFILE_LIST)
	@echo ""
