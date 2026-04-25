# シミュレーション実行ターゲット
# =======================================================
# cactus_sim を Docker コンテナ内で MPI 実行する。
# 並列度 (SIM_MPI_PROCS / SIM_OMP_THREADS) は **マシン依存**のため
# ``.env`` で指定する。未設定時は安全寄りのフォールバックを使用。

# 本 Makefile 群は bash 依存 (PIPESTATUS, ${var%%:*} 等) のため bash を明示。
# Make のデフォルト (/bin/sh = dash on Debian/Ubuntu) だと ``Bad substitution``
# エラーで exit code が正しく伝播しない。
SHELL := /bin/bash

# 安全なフォールバック (.env で上書きされる想定)。
# 推奨値はワークロード依存: qc0 smoke は np=8 × OMP=2 (Phase 3a 検証済)、
# GW150914 N=28 は np=1 × OMP=16 (Phase 3b Step 1 実測、np>=2 で OOM)。
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
GW_N16_PAR           := par/GW150914/generated/gw150914-n16-feasibility.par
GW_N16_CKPT_PAR      := par/GW150914/generated/gw150914-n16-checkpoint-test.par
GW_CONTAINER_NAME    := gw150914-et

# feasibility run の cctk_itlast. 0 = TwoPunctures のみ。
SIM_ITLAST ?= 0

# N=16 feasibility 用 grid 調整 (Issue #9)。
# inner-radius は本質的な解決策、maxrls は補助 (省略時 = rpar 原本 9)。
SIM_N16_INNER_RADIUS ?= 77.14
SIM_N16_MAXRLS       ?=

# 単一試行の wall time 上限 (秒)。OOM ハング暴発防止 (Phase 3b-i で 297 分ハング実測)。
SIM_RUN_TIMEOUT ?= 1800

# Phase 3c-1 checkpoint 検証用。
# write モードは 2h walltime + 約 5 分 evolve buffer のため 8000s 余裕を持って指定。
SIM_CKPT_TIMEOUT ?= 8000
SIM_CKPT_MODE    ?= write    # write | restart
SIM_CKPT_ITLAST  ?=          # 空なら mode 既定値 (write=4000, restart=4500)

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

.PHONY: gw150914-n16-parfile
gw150914-n16-parfile: ## GW150914 N=16 用 par を生成 (Issue #9, inner_radius/maxrls 調整)
	@test -f $(GW_RPAR) || (echo "GW150914.rpar 未取得: make fetch-parfile を先に実行" && exit 1)
	@$(COMPOSE) exec -T et python3 /home/etuser/work/scripts/generate_gw150914_n16_parfile.py \
		--n 16 \
		--inner-radius $(SIM_N16_INNER_RADIUS) \
		$(if $(SIM_N16_MAXRLS),--maxrls $(SIM_N16_MAXRLS),) \
		--itlast $(SIM_ITLAST)

.PHONY: run-gw150914-n16-feasibility
run-gw150914-n16-feasibility: gw150914-n16-parfile ## GW150914 N=16 feasibility 実行 (Phase 3b-ii, inner_radius/maxrls/itlast 可変, $(SIM_RUN_TIMEOUT)s で強制終了)
	@echo "実行設定: N=16 inner_radius=$(SIM_N16_INNER_RADIUS) maxrls=$(if $(SIM_N16_MAXRLS),$(SIM_N16_MAXRLS),default9) np=$(SIM_MPI_PROCS) × OMP=$(SIM_OMP_THREADS) cctk_itlast=$(SIM_ITLAST) timeout=$(SIM_RUN_TIMEOUT)s"
	@mkdir -p _logs
	@TS=$$(date +%Y%m%d-%H%M%S); \
	TAG="n16-m$(SIM_N16_MAXRLS)-np$(SIM_MPI_PROCS)-omp$(SIM_OMP_THREADS)-it$(SIM_ITLAST)-$$TS"; \
	LOG="_logs/gw150914-n16-feasibility-$$TAG.log"; \
	MEMLOG="_logs/gw150914-n16-feasibility-mem-$$TAG.log"; \
	echo "実行ログ: $$LOG"; \
	echo "メモリログ: $$MEMLOG"; \
	bash scripts/sample_container_memory.sh $(GW_CONTAINER_NAME) "$$MEMLOG" 2 & \
	MEMPID=$$!; \
	trap "kill $$MEMPID 2>/dev/null || true" EXIT INT TERM; \
	set +e; \
	$(COMPOSE) exec -T -w /home/etuser/simulations et bash -c '\
		time timeout --signal=KILL $(SIM_RUN_TIMEOUT) mpirun \
			-np $(SIM_MPI_PROCS) \
			-genv OMP_NUM_THREADS $(SIM_OMP_THREADS) \
			-genv HDF5_USE_FILE_LOCKING FALSE \
			$(CACTUS_SIM) \
			/home/etuser/work/$(GW_N16_PAR) \
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
	if [ "$$RC" = "137" ] || [ "$$RC" = "124" ]; then \
		echo "[警告] timeout ($(SIM_RUN_TIMEOUT)s) に達して強制終了されました"; \
	fi; \
	exit $$RC

.PHONY: gw150914-n16-checkpoint-test-parfile
gw150914-n16-checkpoint-test-parfile: ## Phase 3c-1 checkpoint 検証 par 生成 (SIM_CKPT_MODE=write|restart)
	@test -f $(GW_RPAR) || (echo "GW150914.rpar 未取得: make fetch-parfile を先に実行" && exit 1)
	@$(COMPOSE) exec -T et python3 /home/etuser/work/scripts/generate_gw150914_n16_checkpoint_test_parfile.py \
		--mode $(SIM_CKPT_MODE) \
		$(if $(SIM_CKPT_ITLAST),--itlast $(SIM_CKPT_ITLAST),)

.PHONY: run-gw150914-n16-checkpoint-test
run-gw150914-n16-checkpoint-test: gw150914-n16-checkpoint-test-parfile ## Phase 3c-1: N=16 checkpoint write/restart 検証 (SIM_CKPT_MODE=write|restart, ~2h)
	@echo "実行設定: N=16 checkpoint mode=$(SIM_CKPT_MODE) np=$(SIM_MPI_PROCS) × OMP=$(SIM_OMP_THREADS) timeout=$(SIM_CKPT_TIMEOUT)s"
	@mkdir -p _logs
	@TS=$$(date +%Y%m%d-%H%M%S); \
	TAG="n16-ckpt-$(SIM_CKPT_MODE)-np$(SIM_MPI_PROCS)-omp$(SIM_OMP_THREADS)-$$TS"; \
	LOG="_logs/gw150914-$$TAG.log"; \
	MEMLOG="_logs/gw150914-mem-$$TAG.log"; \
	echo "実行ログ: $$LOG"; \
	echo "メモリログ: $$MEMLOG"; \
	bash scripts/sample_container_memory.sh $(GW_CONTAINER_NAME) "$$MEMLOG" 5 & \
	MEMPID=$$!; \
	trap "kill $$MEMPID 2>/dev/null || true" EXIT INT TERM; \
	set +e; \
	$(COMPOSE) exec -T -w /home/etuser/simulations et bash -c '\
		time timeout --signal=KILL $(SIM_CKPT_TIMEOUT) mpirun \
			-np $(SIM_MPI_PROCS) \
			-genv OMP_NUM_THREADS $(SIM_OMP_THREADS) \
			-genv HDF5_USE_FILE_LOCKING FALSE \
			$(CACTUS_SIM) \
			/home/etuser/work/$(GW_N16_CKPT_PAR) \
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
	if [ "$$RC" = "137" ] || [ "$$RC" = "124" ]; then \
		echo "[警告] timeout ($(SIM_CKPT_TIMEOUT)s) に達して強制終了されました"; \
	fi; \
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
