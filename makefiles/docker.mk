# Docker 関連ターゲット
# =======================================================
# einsteintoolkit/jupyter-et コンテナの起動・管理

# .env があれば読み込む（SIM_OUTPUT_DIR, JUPYTER_PORT 等）。
ifneq (,$(wildcard .env))
include .env
export
endif

# 出力先のデフォルト（.env 未設定時に使われる）。
SIM_OUTPUT_DIR ?= $(HOME)/gw150914-output

COMPOSE := docker compose

.PHONY: docker-setup
docker-setup: ## 初回セットアップ（.env 生成 + 出力ディレクトリ作成）
	@test -f .env || (cp .env.example .env && echo ".env を .env.example から作成しました")
	@mkdir -p $(SIM_OUTPUT_DIR)
	@echo "出力ディレクトリ: $(SIM_OUTPUT_DIR)"

.PHONY: docker-pull
docker-pull: ## Einstein Toolkit Jupyter イメージを取得
	$(COMPOSE) pull

.PHONY: docker-up
docker-up: docker-setup ## コンテナをバックグラウンド起動（Jupyter Lab 付き）
	$(COMPOSE) up -d
	@echo ""
	@echo "Jupyter Lab のアクセスURLは以下のコマンドで取得:"
	@echo "  make docker-token"

.PHONY: docker-down
docker-down: ## コンテナ停止・削除
	$(COMPOSE) down

.PHONY: docker-restart
docker-restart: docker-down docker-up ## コンテナ再起動

.PHONY: docker-shell
docker-shell: ## コンテナ内に bash で入る
	$(COMPOSE) exec et bash

.PHONY: docker-logs
docker-logs: ## コンテナのログをフォロー表示
	$(COMPOSE) logs -f et

.PHONY: docker-token
docker-token: ## Jupyter Lab のアクセストークン(URL)を表示
	@$(COMPOSE) exec et jupyter server list 2>/dev/null \
		|| $(COMPOSE) exec et jupyter notebook list 2>/dev/null \
		|| (echo "Jupyter サーバが確認できません。make docker-logs でログを確認してください。" && exit 1)

.PHONY: docker-ps
docker-ps: ## コンテナ稼働状況を表示
	$(COMPOSE) ps

.PHONY: docker-check
docker-check: ## コンテナ内のEinstein Toolkit関連ツール動作確認
	@echo "== mpirun version =="
	@$(COMPOSE) exec et mpirun --version | head -3 || true
	@echo ""
	@echo "== SimFactory (sim) =="
	@$(COMPOSE) exec et which sim || echo "  sim コマンドが見つかりません"
	@echo ""
	@echo "== Einstein Toolkit ディレクトリ =="
	@$(COMPOSE) exec et bash -lc 'ls -d ~/Cactus 2>/dev/null || ls -d ~/ET* 2>/dev/null || echo "  ETディレクトリ不明、コンテナ内を探索要"'
