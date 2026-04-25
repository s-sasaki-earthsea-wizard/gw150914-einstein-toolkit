# GW150914 Einstein Toolkit Simulation

## プロジェクト概要

本プロジェクトでは **Einstein Toolkit** を用いて、2015年9月14日にLIGOが直接検出した
最初の重力波イベント **GW150914**（連星ブラックホール合体）を数値相対論シミュレーション
で再現することを目的とする。

参考資料: [`docs/Binary Black Hole.pdf`](docs/Binary%20Black%20Hole.pdf)
（原典: <https://einsteintoolkit.org/gallery/bbh/index.html>）

### 方針・スコープ

- **目的**: 本格的な数値相対論研究ではなく、有名な重力波イベントを「試しに動かしてみる」
  ことを主眼とする。波形や軌道の定性的な再現ができれば成功。
- **解像度**: マシン制約のため公式ギャラリーの `N=28` から大きく解像度を落として
  `N=16` 程度を想定。精度は犠牲にするが、時間・メモリ・ディスクを現実的な範囲に収める。
- **環境分離**: Einstein Toolkit は依存関係が多く構築が難しいため、**Docker** で
  開発環境をホストから分離する（最初の関門は環境構築になると見込む）。

## GW150914 の物理パラメータ

| 項目 | 値 |
| --- | --- |
| 初期分離 D | 10 M |
| 質量比 q = m₁/m₂ | 36/29 ≈ 1.24 |
| スピン χ₁ = a₁/m₁ | 0.31 |
| スピン χ₂ = a₂/m₂ | -0.46 |

### 期待される物理的出力（公式ギャラリー値）

| 項目 | 値 |
| --- | --- |
| 軌道数 | 6 |
| マージャーまでの時間 | 899 M |
| 最終BH質量 | 0.95 M |
| 最終BHスピン（無次元） | 0.69 |

## 計算規模の見積もり

### 公式ギャラリー（参考値、本プロジェクトでは採用しない）

- 解像度: `N=28`
- 並列度: 128 MPI プロセス（Intel Xeon E5-2630 v3 @ 2.40GHz）
- 総メモリ: 98 GB
- 実行時間: 2.8日
- コスト: 8700 コア時間
- 最終テスト: Kruskal release, 2025-10-16

### 本プロジェクトの想定

- 解像度: `N=16`（公式の約 57%）
- 並列度・メモリ・実行時間は環境構築後に実測予定
- メモリ使用量は概ね `N³` に比例するため、公式値の約 1/5 〜 1/6 に抑えられる見込み

## 技術スタック

### Einstein Toolkit の主要コンポーネント

- **Cactus**: 計算フレームワーク本体
- **Carpet**: 適応的メッシュリファインメント (AMR)
- **Llama**: マルチブロックインフラ
- **TwoPunctures**: 初期データ（連星BHの punctures データ）
- **McLachlan**: 時空進化コード（BSSN形式）
- **AHFinderDirect**: アパレントホライズン検出
- **QuasiLocalMeasures**: 準局所質量・スピン計算
- **Kranc**: コード生成パッケージ
- **SimFactory**: ジョブ投入・管理ユーティリティ

### 実行環境

- **Docker**: 環境分離（Ubuntu 20.04 ベースで Kruskal release を自前ビルド）
- **MPI**: MPICH（公式 jupyter-et 構成準拠）
- **可視化（後段）**: VisIt, Mathematica または Wolfram CDF Player

## Phase 計画

進捗管理用の大まかなマイルストーン。各PhaseはGitHub Issue で管理しており、
詳細サブタスクはIssue内チェックリストを参照する。

| Phase | 内容 | Issue | 状態 |
| --- | --- | --- | --- |
| 0 | プロジェクト初期化・ドキュメント整備 | - | ✅ 完了 |
| 1 | Docker 環境構築 | [#1](https://github.com/s-sasaki-earthsea-wizard/gw150914-einstein-toolkit/issues/1) | ✅ 完了 (cactus_sim ビルド済、MPI 動作確認済) |
| 2 | GW150914 パラメータファイル取得・テスト基盤 | [#2](https://github.com/s-sasaki-earthsea-wizard/gw150914-einstein-toolkit/issues/2) | ✅ 完了 (rpar 取得 + Level 1/2 テスト、N=28 で TwoPunctures 6 分 18 秒) |
| 3a | qc0-mclachlan.par による ET feasibility 確認 | [#10](https://github.com/s-sasaki-earthsea-wizard/gw150914-einstein-toolkit/issues/10) | ✅ 完了 (smoke 26 分で完走、make ターゲット化済) |
| 3b-i | N=28 メモリ/時間 feasibility 計測 | - | ✅ 完了 (np=1 OMP=16 で 50 GiB / 16 日見込み → N=16 方針へ転換) |
| 3b-ii | N=16 対応の rpar grid 改変 | [#9](https://github.com/s-sasaki-earthsea-wizard/gw150914-einstein-toolkit/issues/9) | ✅ 完了 (inner_radius 拡大で 1.84 sec/iter, peak 21 GiB, ringdown ~5.7 日見込み) |
| 3c | GW150914 本番実行 (N=16) | [#3](https://github.com/s-sasaki-earthsea-wizard/gw150914-einstein-toolkit/issues/3) | 未着手 |
| 4 | 軌道・波形の抽出とプロット (+ Zenodo N=28 比較) | [#4](https://github.com/s-sasaki-earthsea-wizard/gw150914-einstein-toolkit/issues/4) | 未着手 |
| 5 | 3D 可視化（オプション） | [#5](https://github.com/s-sasaki-earthsea-wizard/gw150914-einstein-toolkit/issues/5) | 未着手 |

**Phase 3 の分割方針**: 公式 GW150914.rpar は N=28 前提の grid 設計で N<28
では crash する（Issue #9）。grid 改変と本番実行を同時に debug すると切り分けが
困難なため、3a で ET 本体の feasibility（infra 問題の有無）を qc0-mclachlan で
先に保証 → 3b-i で N=28 本体の feasibility 計測 → 3b-ii で N=16 grid 改変 →
3c で N=16 本番、という順で進める。

**N=16 解像度選択の根拠 (Phase 3b-i の結論)**:
N=28 は 16 コア環境にも載る（peak 50 GiB, 80 GB 以内）が、ringdown まで
到達させるには 16+ 日 wall time が必要で実用的でない。N=16 に落として
1–3 日で完走させ、**検証基準は Zenodo 10.5281/zenodo.155394 の
公式 N=28 診断データ**（466 MB, 6 checkpoint 分）と比較する方針。

## 環境構築メモ (Phase 1)

### Docker イメージ戦略

- **方針**: Einstein Toolkit を **自前 Dockerfile でソースビルド**
  - 既製イメージ `einsteintoolkit/jupyter-et` は Docker Hub に存在しない（誤った仮定だった）
  - `ndslabs/jupyter-et` は実在するが全タグが 4 年以上前で Kruskal と乖離
- **ベースイメージ**: `ubuntu:20.04`（公式 jupyter-et 準拠、Singularity 互換性のため）
- **ETバージョン**: **Kruskal release = `ET_2025_05`**（リリース 2025-05-29）
- **入手経路**: GetComponents (CRL) + thornlist 経由で公式 Bitbucket からチェックアウト
- **ビルドツール**: SimFactory の `sim setup-silent` + `sim build`

### MPI 実行戦略

- シングルノード 16 コアのため、**Docker コンテナ内で MPI を完結**させる
  （ホスト側 MPI + 複数コンテナ構成は採用しない）
- **MPI 実装は MPICH**（OpenMPI ではない）
  - 公式 jupyter-et の `base.docker` が MPICH (`libmpich-dev`, `libhdf5-mpich-dev`)
    を採用しているため、互換性最優先で踏襲
  - **注意**: Ubuntu の `libscalapack-mpi-dev` パッケージが Open MPI を依存に
    引き込み、`update-alternatives` の auto モードでは Open MPI が選ばれる。
    Dockerfile 末尾で `update-alternatives --set mpirun /usr/bin/mpirun.mpich`
    に明示切替済み。`mpirun` でも `mpirun.mpich` でもどちらも MPICH が呼ばれる。
  - HDF5 (`libhdf5_mpich.so.103`) や ADIOS2 は MPICH ABI でビルドされているため、
    Open MPI で起動するとシンボル衝突や I/O 不整合のリスクあり

### Docker 起動時の重要オプション

- `shm_size: 4gb` — MPICH のプロセス間共有メモリ通信用（デフォルト 64MB では不足）
- `cpuset: 0-15` — 物理コアに固定（NUMA 安定化）
- `mem_limit: 80g` — ホスト 93GiB のうち 80GB をコンテナに割り当て
- 出力先は `${SIM_OUTPUT_DIR}` でローカル SSD に bind mount（NAS への書き込みを避ける）
- `USER_UID` / `USER_GID` は **ビルド時** に `--build-arg` で渡し、
  コンテナ内 `etuser` UID をホストと一致させる（バインドマウント時のパーミッション一致）

### Dockerfile に含む追加ライブラリ（公式 base.docker と同一）

CarpetX 系を含めた完全構成:

| ライブラリ | バージョン | 用途 |
| --- | --- | --- |
| CMake | 3.29.6 | AMReX 等のビルドに必須 |
| ADIOS2 | 2.10.2 | 並列 I/O |
| NSIMD | 3.0.1 | SIMD ベクトル化（SSE2） |
| openPMD-api | 0.15.1 | AMR データレイアウト |
| ssht | 1.5.1 | スピン荷重球面調和 |
| Silo | 4.11 | 可視化用フォーマット |
| yaml-cpp | 0.6.3 | YAML I/O |
| AMReX | 23.05 | AMR バックエンド (CarpetX) |
| Kuibit | 1.5.0 | Python 解析（pip） |

### ファイル構成

- `Dockerfile` — Ubuntu 20.04 ベースの ET ビルドイメージ定義
- `docker/cactus.cfg` — SimFactory 用ビルドオプション（公式 tutorial.cfg 踏襲）
- `.dockerignore` — ビルドコンテキストから除外するパス
- `.env.example` / `.env` — 設定テンプレとユーザー固有設定（`.env` は git 管理外）
- `docker-compose.yml` — サービス定義（`build: .` で Dockerfile を使用）
- `Makefile` + `makefiles/docker.mk` — `make docker-*` ターゲット群
- 全ターゲットは `make help` で一覧取得可能

### ビルド・実行コスト見積もり

- 初回 `make docker-build`: **60〜120 分**（GetComponents + 並列コンパイル）
- 再ビルド（レイヤーキャッシュ利用時）: 10〜20 分
- 最終イメージサイズ: **5〜8 GB** 目安

## Phase 2 メモ (パラメータファイル取得・テスト基盤)

### 外部データ管理

- GW150914.rpar は **git 管理外**（上流 Einstein Toolkit 著作物の尊重）
- `make fetch-parfile` が Bitbucket から取得、`.sha256` sidecar で整合性検証
  - sha256 を Makefile 直書きすると秘密検知ツールの誤検知に当たりやすい → sidecar 方式
- 取得物: `par/GW150914/GW150914.rpar` (gitignore)
- 検証: `par/GW150914/GW150914.rpar.sha256`（git 管理、`sha256sum -c` で照合）

### rpar の構造（重要）

GW150914.rpar は **Python スクリプト** であり以下のパイプラインで `.par` を生成:

1. `@N@` / `@SIMULATION_NAME@` / `@WALLTIME_HOURS@` の 3 プレースホルダを文字列置換
2. `python3 <rpar>` 実行で同ディレクトリに `.par` 出力（出力名は `sys.argv[0]` から導出）
3. 必要に応じて生成後 `.par` にパラメータ上書きを適用
   - 例: Level 2 テストでは `Cactus::terminate = iteration` + `cctk_itlast = 0`

### テスト戦略（Level 分離）

| Level | Marker | 内容 | 時間 | 依存 |
| --- | --- | --- | --- | --- |
| 1 | `smoke` | rpar → par 生成パイプラインの純 Python テスト | < 1 秒 | Python のみ |
| 2 | `short` | cactus_sim で TwoPunctures 初期データまで実行 | 約 7 分 | Docker + Cactus |
| 3 (Phase 3) | - | 短時間時空進化（フィージビリティ本体） | 10〜30 分 | 同上 |

- Level 1 はホストでも `make test-host-smoke` で動作（CI でも回せる設計）
- Level 2 は `cactus_sim` / `mpirun` が無い環境で自動 skip
- テストは常に `pytest tmp_path` で独立、`simulations/` 本番出力を汚染しない
- Level 2 実測 (2026-04-24): N=28 + cctk_itlast=0 + nproc=1 で **6 分 18 秒**

## Phase 3a メモ (qc0-mclachlan ET feasibility)

### smoke 実測値 (2026-04-24, Kruskal release)

`make run-qc0-smoke` (cctk_itlast=10 + checkpoint 無効) を np=8 × OMP=2 で実行:

| 指標 | 値 |
| --- | --- |
| wall time | 26 分 17 秒 |
| CCTK total | 1575 秒 |
| TwoPunctures | 1352 秒 (85.8%) |
| Evolve (16 iter) | 100 秒 (6.4%) |
| 出力サイズ | 314 MB |
| peak メモリ | 約 42 GB (np=8 × ~5.3 GB) |

Evolution 完走、iteration 16 まで進行、全 8 ranks `Done.` でクリーン終了。

### MPI / OMP 構成（超重要、Phase 3c でも共通）

- **必ず `OMP_NUM_THREADS` を明示指定**する（未指定だと Cactus が全コア
  スレッド化し `mpirun -np N` と掛け合わせて N² スレッドで oversubscription）
- 16 コア環境の実測ベース推奨値: **np=8 × OMP=2** (.env の `SIM_MPI_PROCS` /
  `SIM_OMP_THREADS` で指定)
- np=16 は OMP=1 でも container mem_limit (80 GB) を超えるため採用不可
- 設定は `makefile/sim.mk` の `mpirun -np $(SIM_MPI_PROCS) -genv OMP_NUM_THREADS $(SIM_OMP_THREADS)` で自動展開

### HDF5 1.10.4 checkpoint 書き込み問題

- 複数 MPI rank が同一 checkpoint ファイルに同時 open → POSIX lock 衝突
  (`H5FD_sec2_lock: errno=11 'Resource temporarily unavailable'`)
- 出力先が local SSD (ext3) でも発生。NFS 関係ない
- `HDF5_USE_FILE_LOCKING=FALSE` env var は **通常 I/O には効くが
  checkpoint 経路では不十分**。`admbase-curv.h5` などの evolution 出力は
  成功、checkpoint 創設のみ失敗
- Phase 3a smoke では checkpoint 完全無効化で回避
  (`IO::checkpoint_ID=no`, `IOHDF5::checkpoint=no` 等、5 パラメータ)
- **Phase 3c 本番では checkpoint が必須** (長時間 run の中断再開)。
  CarpetIOHDF5 の per-proc モード、あるいは parallel HDF5 (MPI-IO) への
  切り替えを検討する

### rpar のグリッド構造と N の関係 (重要)

公式 rpar の grid structure は **N=28 前提で設計**されている。

- `maxrls = 9` 固定、refinement level 数 `rlsp = rlsm = 7` は N に非依存
- Refinement level 1 の box サイズ (≈21.27 M) は N=28 での Thornburg04
  内部 Cartesian パッチ内に完全に収まるよう調整されている
- **N<28 では Carpet buffer zone が物理単位で拡大**し、level 1 box が
  angular patch に食い込む → Interpolate2 が inter-patch 境界を
  検出して Cactus::Abort（2026-04-24 に N=8/16 で crash 確認）

### Phase 3b-ii への申し送り (N=16 実行に向けて)

Issue #9 の rpar grid 改変で N=16 を走らせる。改変候補:

- 候補 A: `maxrls` を 8 以下に下げる（level 1 の box サイズが縮小）
- 候補 B: `sphere_inner_radius` の N 依存丸めを調整
- 候補 C: `levelsp`/`levelsm` の最外層サイズに上限を設ける

原本 rpar は改変せず、`apply_overrides` 機構か `@MAXRLS@` 追加プレースホルダで対応するのが素直。

## Phase 3b-i メモ (N=28 feasibility 実測)

### Step 1 — TwoPunctures のみ np スイープ (cctk_itlast=0)

| Config | Wall time | Peak mem | 完走 |
| --- | --- | --- | --- |
| **np=1 × OMP=16** | **6m22s** | **43 GiB** | ✅ |
| np=2 × OMP=8 | 26m33s | 80 GiB | ⚠ cleanup 時 OOM |
| np=4 × OMP=4 | 297m (OOM ハング) | 80 GiB | ❌ |

**np を増やすほど悪化**する（qc0 と真逆）。理由: Multipole / WeylScal4 の
球面調和バッファが rank ごとに複製される。GW150914 N=28 は **np=1 × OMP=16
が唯一安定**。

### Step 2 — evolve 16 iter (np=1 × OMP=16, cctk_itlast=16)

- Wall time: 7m7s (TwoPunctures 6m22s + evolve 45s)
- **2.8 秒/iter**
- Peak memory: **50.5 GiB** (evolve 開始時に +7 GiB 増、その後安定)
- 80 GB 上限に対し 30 GiB 余裕

### N=28 full run wall time 見積もり

| 目標 evolve | 物理イベント | wall time |
| --- | --- | --- |
| 200 M | inspiral 初期 | 3.2 日 |
| 900 M | マージャー | 14.6 日 |
| 1000 M | + ringdown 数周期 | **16 日** |
| 1700 M | 公式フル | 27.5 日 |

公式 128 コア × 2.8 日 = 8600 core-hour を 16 コアで割った 22 日と整合。

### 結論: N=16 + Zenodo N=28 比較方式へ

N=28 は物理的に走らせられるがユーザ制約 (2 週間) では ringdown まで届かない。
→ N=16 に解像度を落として 1–3 日で完走 + **Zenodo 10.5281/zenodo.155394**
の公式 N=28 診断データ (466 MB, 6 checkpoint + waveform) で検証。

### 技術的発見

#### Makefile の PIPESTATUS が dash で壊れる

`${PIPESTATUS[0]}` は bash 専用。Make のデフォルト SHELL (= `/bin/sh` →
Debian/Ubuntu で dash) では `Bad substitution` エラーで exit code が
壊れる。`makefiles/sim.mk` 冒頭に `SHELL := /bin/bash` を追加して解消。

#### MPICH mpirun の OOM 対応

1 rank が OOM kill されても残り rank が MPI_Wait で無限停止する（np=4
試行で 297 分ハング）。Phase 3c ではタイムアウト付き実行を推奨。

### Python 依存管理

- `requirements.txt` で一元管理（本 Phase で Dockerfile から分離）
- バージョン変更は `requirements.txt` のみ編集 → `make docker-rebuild`
- pytest は test 依存だが runtime 共存で問題なし（コンテナは dev 兼 run 兼用）

## Phase 3b-ii メモ (N=16 grid 改変, Issue #9)

### 採用構成

- **`Coordinates::sphere_inner_radius = 77.10 M`** (rpar 計算値 51.40 M を 1.5 倍)
  - rpar 自然 step `i × h0 = 8.566 M` の 9 倍。`snap_inner_radius()` 自動 snap
  - 半整数倍制約 (`Coordinates/patchsystem.cc:177`) を満たすため必須
- **`Carpet::max_refinement_levels = 9`** (rpar 原本通り。AMR 階層は犠牲にしない)
- **`np = 1, OMP = 16`** (Phase 3b-i と同じ、GW150914 で OOM 回避)

### 真因の特定 (重要)

事前仮説「`maxrls` 縮小で level-1 box を縮めれば inter-patch 境界に侵入
しない」は**誤り**。実測で否定:

| maxrls | rlsp/rlsm | 最外層 box | 結果 |
| --- | --- | --- | --- |
| 9 | 7 | 21.27 M | ❌ inter-patch crash |
| 8 | 6 | 10.64 M | ❌ 同 crash |
| 7 | 5 | 5.32 M | ❌ 同 crash |

`Interpolate2/test.cc:77` の制約は「refinement level > 0 のグリッドが
inter-patch 境界マーク (Sn>=0) を持つ点を 1 つでも含むと abort」。
crash の真因は box 自体ではなく **Carpet の prolongation buffer +
ghost zones が物理単位で広がり、境界領域に侵入する**こと。

- N=28: h0 = 1.224 M → buffer 厚 ~6 M → sphere_inner=51.40 で OK
- N=16: h0 = 2.143 M → buffer 厚 ~10.7 M (1.75 倍) → 同じ inner では侵入

box を縮小しても buffer 自体は h0 に固定されるため効果なし。
**inner Cartesian patch を物理的に拡大**するのが本質的解決策。

### 実測値 (np=1 × OMP=16, sphere_inner_radius=77.10)

| 試行 | wall time | peak mem | 完走 |
| --- | --- | --- | --- |
| TwoPunctures のみ (cctk_itlast=0) | **3m58s** | **19.4 GiB** | ✅ |
| evolve 16 iter (cctk_itlast=16) | **4m27s** | **21.3 GiB** | ✅ |

**evolve 単独 = 29s / 16 iter = 1.84 sec/iter** (N=28 の 2.8 比 34% 短縮)
dt_it = 0.00375 M (N=28 の 0.00215 M の 1.75 倍 = 28/16)

### N=16 full run wall time 見積もり (1.84 sec/iter ベース)

| 目標 evolve | 物理イベント | 推定 iter 数 | wall time (16 コア) |
| --- | --- | --- | --- |
| 200 M | inspiral 初期 | ~53,000 | 1.1 日 |
| 900 M | **マージャー到達** | ~239,000 | **5.1 日** |
| 1000 M | + ringdown 数周期 | ~265,000 | **5.7 日** |
| 1700 M | 公式フル | ~451,000 | 9.6 日 |

ユーザ目標 (≤ 2 週間で ringdown まで届く) に対し 3 倍弱の余裕。
リスク: マージャー直前に AMR 密集で sec/iter 悪化の可能性 → Phase 3c は
**7 日 wall budget** で計画。

### 重要な制約 (Phase 3c でも踏襲)

1. **`Coordinates/patchsystem.cc:177` の半整数倍制約**:
   `2 * sphere_inner_radius / h_cartesian` が整数 (誤差 1e-8 以内) で
   ある必要があり、任意値を指定すると起動時即 MPI_ABORT。
   `scripts/generate_gw150914_n16_parfile.py::snap_inner_radius()` で
   `i × h0` 単位 (rpar 自然 step) に ceil-snap して回避。
2. **`Interpolate2/test.cc:77` の inter-patch 境界制約**:
   refinement level > 0 のグリッドが inter-patch 境界マーク (Sn>=0) を
   持つ点を 1 つでも含むと abort。N=16 では sphere_inner_radius を
   公式 51.40 M から 77.10 M 以上に拡大しないと必ず crash する。

### Phase 3c への申し送り (本番 run に向けて)

1. **checkpoint 戦略の決定** (Phase 3a でも未解決): HDF5 1.10.4 POSIX
   lock 問題で複数 rank からの同時書き込みが失敗。np=1 構成なら問題
   ないはずだが要確認。落ちた場合は CarpetIOHDF5 per-proc モード or
   parallel HDF5 (MPI-IO) を試す。
2. 最低 ringdown 100 M 込み (= 1000 M) を目標に N=16 本番 run 投入。
3. Zenodo 10.5281/zenodo.155394 の N=28 reference データを Phase 4 で比較。

## 成果物の扱い

- シミュレーション出力（HDF5等）は数GB〜TB規模になりうるため **git管理外** とする
- PDF等の参考資料も `.gitignore` で除外済み（`*.pdf`）
- 出力の保存先は Phase 1 で決定（ローカル / NAS）

## 言語設定

このプロジェクトでは**日本語**での応答を行ってください。コード内のコメント、ログメッセージ、エラーメッセージ、ドキュメンテーション文字列なども日本語で記述してください。

## 開発ルール

### コーディング規約

- Python: PEP 8準拠
- 関数名: snake_case
- クラス名: PascalCase
- 定数: UPPER_SNAKE_CASE
- Docstring: Google Style

## Git運用

- ブランチ戦略: feature/*, fix/*, refactor/*
- コミットメッセージ: 英文を使用、動詞から始める
- PRはmainブランチへ

## 開発ガイドライン

### ドキュメント更新プロセス

機能追加やPhase完了時には、以下のドキュメントを同期更新する：

1. **CLAUDE.md**: プロジェクト全体状況、Phase完了記録、技術仕様
2. **README.md**: ユーザー向け機能概要、実装状況、使用方法
3. **Makefile**: コマンドヘルプテキスト（## コメント）の更新
4. **makefiles/**: コマンドヘルプテキスト（## コメント）の更新

### コミットメッセージ規約

#### コミット粒度

- **1コミット = 1つの主要な変更**: 複数の独立した機能や修正を1つのコミットにまとめない
- **論理的な単位でコミット**: 関連する変更は1つのコミットにまとめる
- **段階的コミット**: 大きな変更は段階的に分割してコミット

#### プレフィックスと絵文字

- ✨ feat: 新機能
- 🐞 fix: バグ修正
- 📚 docs: ドキュメント
- 🎨 style: コードスタイル修正
- 🛠️ refactor: リファクタリング
- ⚡ perf: パフォーマンス改善
- ✅ test: テスト追加・修正
- 🏗️ chore: ビルド・補助ツール
- 🚀 deploy: デプロイ
- 🔒 security: セキュリティ修正
- 📝 update: 更新・改善
- 🗑️ remove: 削除

**重要**: Claude Codeを使用してコミットする場合は、必ず以下の署名を含める：

```text
🤖 Generated with [Claude Code](https://claude.ai/code)

Co-Authored-By: Claude <noreply@anthropic.com>
```
