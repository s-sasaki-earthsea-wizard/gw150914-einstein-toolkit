# シミュレーション実行ターゲット
# =======================================================
# cactus_sim を Docker コンテナ内で MPI 実行する。
# 並列度 (SIM_MPI_PROCS / SIM_OMP_THREADS) は **マシン依存**のため
# ``.env`` で指定する。未設定時は安全寄りのフォールバックを使用。

# 安全なフォールバック (.env で上書きされる想定)。
# 本プロジェクトの 16 コア環境では .env.example の推奨値 (8×2) を参照。
SIM_MPI_PROCS   ?= 4
SIM_OMP_THREADS ?= 1

# コンテナ内 Cactus 実行パス（通常は変更不要）。
CACTUS_SIM ?= /home/etuser/Cactus/exe/cactus_sim

# qc0-mclachlan 関連パス（リポジトリ内、コンテナ内両方で同一のため定数）。
QC0_PARFILE       := par/qc0-mclachlan/qc0-mclachlan.par
QC0_SMOKE_PARFILE := par/qc0-mclachlan/generated/qc0-mclachlan-smoke.par

.PHONY: qc0-smoke-parfile
qc0-smoke-parfile: ## qc0 smoke 用 par を生成 (cctk_itlast=10, checkpoint 無効)
	@test -f $(QC0_PARFILE) || (echo "qc0 parfile 未取得: make fetch-qc0 を先に実行" && exit 1)
	@$(COMPOSE) exec -T et python3 /home/etuser/work/scripts/generate_qc0_smoke_parfile.py

.PHONY: run-qc0-smoke
run-qc0-smoke: qc0-smoke-parfile ## qc0 smoke を実行 (Phase 3a ET feasibility, ~30 分)
	@echo "実行設定: np=$(SIM_MPI_PROCS) × OMP=$(SIM_OMP_THREADS) = $$(( $(SIM_MPI_PROCS) * $(SIM_OMP_THREADS) )) cores"
	@$(COMPOSE) exec -T -w /home/etuser/simulations et bash -c '\
		mkdir -p _logs && \
		LOG=_logs/qc0-smoke-$$(date +%Y%m%d-%H%M%S).log && \
		echo "ログ: $$LOG" && \
		time mpirun \
			-np $(SIM_MPI_PROCS) \
			-genv OMP_NUM_THREADS $(SIM_OMP_THREADS) \
			-genv HDF5_USE_FILE_LOCKING FALSE \
			$(CACTUS_SIM) \
			/home/etuser/work/$(QC0_SMOKE_PARFILE) \
			2>&1 | tee "$$LOG"'
