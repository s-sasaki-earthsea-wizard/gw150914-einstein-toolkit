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

# GW150914 feasibility 関連 (Phase 3b, N=28 メモリ計測用)。
GW_RPAR              := par/GW150914/GW150914.rpar
GW_FEASIBILITY_PAR   := par/GW150914/generated/gw150914-feasibility.par
GW_CONTAINER_NAME    := gw150914-et

# feasibility run の cctk_itlast. 0 = TwoPunctures のみ。
SIM_ITLAST ?= 0

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

.PHONY: gw150914-feasibility-parfile
gw150914-feasibility-parfile: ## GW150914 feasibility 用 par を生成 (N=28, SIM_ITLAST で iteration 数指定)
	@test -f $(GW_RPAR) || (echo "GW150914.rpar 未取得: make fetch-parfile を先に実行" && exit 1)
	@$(COMPOSE) exec -T et python3 /home/etuser/work/scripts/generate_gw150914_feasibility_parfile.py \
		--itlast $(SIM_ITLAST)

.PHONY: run-gw150914-feasibility
run-gw150914-feasibility: gw150914-feasibility-parfile ## GW150914 N=28 feasibility を実行 (Phase 3b, メモリ計測付き)
	@echo "実行設定: np=$(SIM_MPI_PROCS) × OMP=$(SIM_OMP_THREADS) cctk_itlast=$(SIM_ITLAST)"
	@mkdir -p _logs
	@TS=$$(date +%Y%m%d-%H%M%S); \
	TAG="np$(SIM_MPI_PROCS)-omp$(SIM_OMP_THREADS)-it$(SIM_ITLAST)-$$TS"; \
	LOG="_logs/gw150914-feasibility-$$TAG.log"; \
	MEMLOG="_logs/gw150914-feasibility-mem-$$TAG.log"; \
	echo "実行ログ: $$LOG"; \
	echo "メモリログ: $$MEMLOG"; \
	bash scripts/sample_container_memory.sh $(GW_CONTAINER_NAME) "$$MEMLOG" 2 & \
	MEMPID=$$!; \
	trap "kill $$MEMPID 2>/dev/null || true" EXIT INT TERM; \
	set +e; \
	$(COMPOSE) exec -T -w /home/etuser/simulations et bash -c '\
		time mpirun \
			-np $(SIM_MPI_PROCS) \
			-genv OMP_NUM_THREADS $(SIM_OMP_THREADS) \
			-genv HDF5_USE_FILE_LOCKING FALSE \
			$(CACTUS_SIM) \
			/home/etuser/work/$(GW_FEASIBILITY_PAR) \
			2>&1' | tee "$$LOG"; \
	RC=$${PIPESTATUS[0]}; \
	kill $$MEMPID 2>/dev/null || true; \
	wait $$MEMPID 2>/dev/null || true; \
	echo ""; \
	echo "=== メモリ使用量サマリ ==="; \
	awk 'NR>1 && $$2 ~ /[GM]iB$$/ { \
		v=$$2; unit=""; \
		if (v ~ /GiB/) { sub(/GiB/,"",v); g=v+0 } \
		else if (v ~ /MiB/) { sub(/MiB/,"",v); g=(v+0)/1024.0 } \
		if (g>max) max=g \
	} END { printf "peak container memory: %.2f GiB\n", max }' "$$MEMLOG"; \
	echo "詳細は $$MEMLOG を参照"; \
	exit $$RC

.PHONY: sweep-gw150914-feasibility
sweep-gw150914-feasibility: ## GW150914 N=28 TwoPunctures メモリスイープ (np=1/2/4 × OMP=16/8/4)
	@echo "============================================================"
	@echo "GW150914 N=28 TwoPunctures メモリスイープ (Phase 3b Step 1)"
	@echo "============================================================"
	@for config in "1:16" "2:8" "4:4"; do \
		np=$${config%%:*}; \
		omp=$${config##*:}; \
		echo ""; \
		echo "------------------------------------------------------------"; \
		echo "[試行] np=$$np × OMP=$$omp (= $$(( np * omp )) cores)"; \
		echo "------------------------------------------------------------"; \
		$(MAKE) --no-print-directory run-gw150914-feasibility \
			SIM_MPI_PROCS=$$np SIM_OMP_THREADS=$$omp SIM_ITLAST=0 \
			|| echo "[警告] np=$$np × OMP=$$omp で失敗 (継続)"; \
	done
	@echo ""
	@echo "スイープ完了。各試行のログは _logs/ を参照。"
