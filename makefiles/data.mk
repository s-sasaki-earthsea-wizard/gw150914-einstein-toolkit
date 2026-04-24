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
