# 外部データ取得ターゲット
# =======================================================
# Einstein Toolkit 公式の GW150914 パラメータファイル等、
# ライセンス上プロジェクトリポジトリに含めない外部データを
# ユーザ環境でフェッチするためのターゲット群。
#
# 取得物は .gitignore 済み。整合性検証は sidecar の .sha256 ファイルで行う
# (sha256sum -c の標準フォーマット)。

PARFILE_URL      := https://bitbucket.org/einsteintoolkit/einsteinexamples/raw/master/par/GW150914/GW150914.rpar
PARFILE_DIR      := par/GW150914
PARFILE_NAME     := GW150914.rpar
PARFILE_DEST     := $(PARFILE_DIR)/$(PARFILE_NAME)
PARFILE_CHECKSUM := $(PARFILE_DIR)/$(PARFILE_NAME).sha256

QC0_URL          := https://bitbucket.org/einsteintoolkit/einsteinexamples/raw/master/par/qc0-mclachlan.par
QC0_DIR          := par/qc0-mclachlan
QC0_NAME         := qc0-mclachlan.par
QC0_DEST         := $(QC0_DIR)/$(QC0_NAME)
QC0_CHECKSUM     := $(QC0_DIR)/$(QC0_NAME).sha256

.PHONY: fetch-parfile
fetch-parfile: ## 公式 GW150914.rpar を Bitbucket から取得 + sha256 検証
	@mkdir -p $(PARFILE_DIR)
	@if [ -f $(PARFILE_DEST) ]; then \
		echo "既に存在します: $(PARFILE_DEST) (再取得は make refetch-parfile)"; \
	else \
		echo "取得中: $(PARFILE_URL)"; \
		curl -fsSL -o $(PARFILE_DEST) $(PARFILE_URL); \
		echo "取得完了: $(PARFILE_DEST)"; \
	fi
	@$(MAKE) --no-print-directory verify-parfile

.PHONY: refetch-parfile
refetch-parfile: ## rpar を削除して再取得
	@rm -f $(PARFILE_DEST)
	@$(MAKE) --no-print-directory fetch-parfile

.PHONY: verify-parfile
verify-parfile: ## 取得済み rpar の sha256 検証 (sidecar ファイル利用)
	@test -f $(PARFILE_DEST) || (echo "rpar 未取得: make fetch-parfile を先に実行してください" && exit 1)
	@test -f $(PARFILE_CHECKSUM) || (echo "sha256 sidecar が見つかりません: $(PARFILE_CHECKSUM)" && exit 1)
	@cd $(PARFILE_DIR) && sha256sum -c $(PARFILE_NAME).sha256

.PHONY: fetch-qc0
fetch-qc0: ## Phase 3a 用 qc0-mclachlan.par を Bitbucket から取得 + sha256 検証
	@mkdir -p $(QC0_DIR)
	@if [ -f $(QC0_DEST) ]; then \
		echo "既に存在します: $(QC0_DEST) (再取得は make refetch-qc0)"; \
	else \
		echo "取得中: $(QC0_URL)"; \
		curl -fsSL -o $(QC0_DEST) $(QC0_URL); \
		echo "取得完了: $(QC0_DEST)"; \
	fi
	@$(MAKE) --no-print-directory verify-qc0

.PHONY: refetch-qc0
refetch-qc0: ## qc0-mclachlan.par を削除して再取得
	@rm -f $(QC0_DEST)
	@$(MAKE) --no-print-directory fetch-qc0

.PHONY: verify-qc0
verify-qc0: ## 取得済み qc0-mclachlan.par の sha256 検証 (sidecar ファイル利用)
	@test -f $(QC0_DEST) || (echo "par 未取得: make fetch-qc0 を先に実行してください" && exit 1)
	@test -f $(QC0_CHECKSUM) || (echo "sha256 sidecar が見つかりません: $(QC0_CHECKSUM)" && exit 1)
	@cd $(QC0_DIR) && sha256sum -c $(QC0_NAME).sha256
