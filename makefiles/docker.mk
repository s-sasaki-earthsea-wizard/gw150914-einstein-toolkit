# Docker 関連ターゲット
# =======================================================
# GW150914 Einstein Toolkit イメージのビルド・起動・管理。
# Kruskal release (ET_2025_05) を Ubuntu 20.04 上にソースビルドする。

# .env があれば読み込む (SIM_OUTPUT_DIR, USER_UID 等)。
ifneq (,$(wildcard .env))
include .env
export
endif

# 出力先のデフォルト (.env 未設定時に使われる)。
SIM_OUTPUT_DIR ?= $(HOME)/gw150914-output

# ホスト UID/GID を自動検出 (.env で上書き可能)。
USER_UID ?= $(shell id -u)
USER_GID ?= $(shell id -g)
MAKE_PARALLEL ?= 8

COMPOSE := docker compose
BUILD_ARGS := \
	--build-arg USER_UID=$(USER_UID) \
	--build-arg USER_GID=$(USER_GID) \
	--build-arg MAKE_PARALLEL=$(MAKE_PARALLEL)

.PHONY: docker-setup
docker-setup: ## 初回セットアップ（.env 生成 + 出力ディレクトリ作成）
	@test -f .env || (cp .env.example .env && echo ".env を .env.example から作成しました")
	@mkdir -p $(SIM_OUTPUT_DIR)
	@echo "出力ディレクトリ: $(SIM_OUTPUT_DIR)"
	@echo "ホスト UID/GID  : $(USER_UID)/$(USER_GID)"

.PHONY: docker-build
docker-build: docker-setup ## Docker イメージをビルド（初回 60〜120 分）
	$(COMPOSE) build $(BUILD_ARGS)

.PHONY: docker-rebuild
docker-rebuild: docker-setup ## キャッシュ無視で Docker イメージを再ビルド
	$(COMPOSE) build --no-cache --pull $(BUILD_ARGS)

.PHONY: docker-up
docker-up: docker-setup ## コンテナをバックグラウンド起動（Jupyter Lab 付き）
	$(COMPOSE) up -d
	@echo ""
	@echo "Jupyter Lab のアクセス URL は以下のコマンドで取得:"
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
docker-check: ## コンテナ内の Einstein Toolkit 関連ツール動作確認
	@echo "== mpirun (システムデフォルト) =="
	@$(COMPOSE) exec et mpirun --version | head -2 || true
	@echo ""
	@echo "== SimFactory (sim) =="
	@$(COMPOSE) exec et bash -lc 'ls -la /home/etuser/Cactus/simfactory/bin/sim' || echo "  sim が見つかりません"
	@echo ""
	@echo "== Cactus 実行ファイル =="
	@$(COMPOSE) exec et bash -lc 'ls -la /home/etuser/Cactus/exe/cactus_sim' \
		|| echo "  cactus_sim が見つかりません（ビルド未完了の可能性）"
	@echo ""
	@echo "== GW150914 で使う主要 thorn / arrangement =="
	@$(COMPOSE) exec et bash -lc '\
		check() { \
			if ls -d /home/etuser/Cactus/arrangements/$$1 >/dev/null 2>&1 \
			   || ls -d /home/etuser/Cactus/arrangements/*/$$1 >/dev/null 2>&1; then \
				echo "  ✅ $$1"; \
			else \
				echo "  ❌ $$1 (見つかりません)"; \
			fi; \
		}; \
		check TwoPunctures; \
		check McLachlan; \
		check ML_BSSN; \
		check AHFinderDirect; \
		check QuasiLocalMeasures; \
		check WeylScal4; \
		check Multipole'
	@echo ""
	@echo "== MPI スモークテスト (mpirun.mpich -np 2) =="
	@$(COMPOSE) exec et bash -lc \
		'cd /home/etuser/Cactus && \
		 mpirun.mpich -np 2 ./exe/cactus_sim --describe-all-parameters > /dev/null 2>&1 \
			&& echo "  ✅ MPI_Init 成功 (mpirun.mpich -np 2)" \
			|| echo "  ❌ MPI_Init 失敗"'
