# GW150914 Einstein Toolkit Simulation

Einstein Toolkit を用いた、重力波イベント **GW150914**（連星ブラックホール合体）
の数値相対論シミュレーションプロジェクト。

## 概要

2015年9月14日 09:51 UTC に LIGO が初めて直接検出した重力波イベント GW150914 を、
[Einstein Toolkit](https://einsteintoolkit.org/) で再現することを目的とする。

- **イベント**: 36 + 29 太陽質量の連星ブラックホール合体 → 62 太陽質量の残留BH
  （3 太陽質量分が重力波として放出）
- **論文**: [Phys. Rev. Lett. 116, 061102](http://dx.doi.org/10.1103/PhysRevLett.116.061102)
- **LIGO公式データ**: <https://losc.ligo.org/events/GW150914/>
- **本プロジェクトが参照する公式ギャラリー**:
  <https://einsteintoolkit.org/gallery/bbh/index.html>

### 方針

本プロジェクトは研究目的ではなく、**有名な重力波イベントを試しに計算してみる**
ことを主眼としている。そのため、以下の妥協を行う：

- 公式ギャラリーの解像度 `N=28` を `N=16` 程度に落として実行
  （精度は犠牲、軌道・波形の定性的な再現を狙う）
- 環境構築は Docker で行い、ホスト環境を汚さない

## 物理パラメータ

| 項目 | 値 |
| --- | --- |
| 初期分離 D | 10 M |
| 質量比 q = m₁/m₂ | 36/29 ≈ 1.24 |
| スピン χ₁ | 0.31 |
| スピン χ₂ | -0.46 |

### 公式ギャラリーの期待値

| 項目 | 値 |
| --- | --- |
| 軌道数 | 6 |
| マージャーまでの時間 | 899 M |
| 最終BH質量 | 0.95 M |
| 最終BHスピン（無次元） | 0.69 |

## 開発環境

- OS: Linux (Ubuntu 系想定)
- コンテナ: Docker (ベースイメージは自前ビルド、Ubuntu 20.04)
- Einstein Toolkit: **Kruskal release (`ET_2025_05`)** をソースビルド
- MPI 実装: **MPICH**（公式 jupyter-et 構成準拠）

> 詳細な要求リソース・実行時間は Phase 1 動作確認後に追記する。

## 前提

- Linux ホスト (Ubuntu 24.04 等)
- Docker 29.x 以降 + Docker Compose v2 以降
- 16 CPU コア / 93 GiB RAM / SSD 空き **150 GB 以上推奨**
  （イメージ 5〜8 GB + ビルド中間生成物 + 出力データ）
- ホストユーザが `docker` グループに所属している（`sudo` なしで `docker` 実行可能）

## インストール方法

### 1. 環境設定ファイルの準備

```bash
# .env.example を .env にコピーして調整（出力先・UID 等）
cp .env.example .env
$EDITOR .env
```

主な設定項目:

| 変数 | 意味 | デフォルト |
| --- | --- | --- |
| `SIM_OUTPUT_DIR` | シミュレーション出力先（ローカル SSD 推奨） | `${HOME}/gw150914-output` |
| `JUPYTER_PORT` | Jupyter Lab 公開ポート | `8888` |
| `CONTAINER_CPUSET` | 固定する物理 CPU コア範囲 | `0-15` |
| `CONTAINER_MEM_LIMIT` | コンテナ最大メモリ | `80g` |
| `CONTAINER_SHM_SIZE` | 共有メモリ（MPICH 通信用） | `4gb` |
| `USER_UID` / `USER_GID` | コンテナ内 etuser の UID/GID（ホストと一致させる） | `1000` / `1000` |
| `MAKE_PARALLEL` | Cactus ビルド時の `make -j` 並列度 | `8` |

### 2. Docker イメージのビルド

⚠️ **初回ビルドは 60〜120 分かかります**（Einstein Toolkit Kruskal release を
ソースからビルドし、AMReX / ADIOS2 等の追加ライブラリも含めるため）。

```bash
make docker-build      # ホスト UID/GID は自動検出される
```

`make docker-rebuild` でキャッシュ無視の再ビルドも可能。

### 3. コンテナの起動

```bash
make docker-up      # バックグラウンド起動
make docker-token   # Jupyter Lab のアクセス URL(トークン付) を取得
```

その他の管理コマンド:

```bash
make docker-shell   # コンテナ内 bash
make docker-logs    # ログをフォロー
make docker-check   # mpirun / sim / cactus_sim / 主要 thorn の存在確認
make docker-down    # 停止・削除
make help           # 全ターゲット一覧
```

## 使い方

### パラメータファイル取得

公式の Einstein Toolkit 配布 parfile は **いずれもリポジトリには含めない**
（上流 ET 著作物の尊重）。以下のコマンドで Bitbucket から取得する:

```bash
# GW150914 本体 (Phase 3b/3c 用)
make fetch-parfile    # 公式 rpar を取得 + sha256 sidecar で整合性検証
make verify-parfile   # 既取得ファイルの sha256 のみ確認

# qc0-mclachlan (Phase 3a feasibility 用、等質量・無スピン軽量 BBH)
make fetch-qc0        # qc0-mclachlan.par を取得 + sha256 検証
make verify-qc0       # 既取得ファイルの sha256 のみ確認
```

### qc0-mclachlan smoke 実行 (Phase 3a)

GW150914 grid 改変 (Phase 3b) の前に、ET 本体の動作を qc0-mclachlan.par
(等質量・無スピン軽量 BBH) で検証する:

```bash
make qc0-smoke-parfile  # overrides 適用して smoke 用 par を生成
make run-qc0-smoke      # np=SIM_MPI_PROCS × OMP=SIM_OMP_THREADS で実行
```

- 並列度は `.env` の `SIM_MPI_PROCS` / `SIM_OMP_THREADS` で制御
  (推奨値と背景は `.env.example` 参照)
- smoke は `cctk_itlast=10` で終了、wall time は 16 コア環境で約 30 分
- 出力は `${SIM_OUTPUT_DIR}/qc0-mclachlan-smoke/`、ログは `_logs/`

### GW150914 N=16 feasibility 実行 (Phase 3b-ii)

公式 rpar は N=28 前提で grid 構造が固定されているため、N=16 で動かす
には `Coordinates::sphere_inner_radius` を拡大する必要がある (詳細は
Issue #9 と CLAUDE.md の Phase 3b-ii メモ参照):

```bash
# default: SIM_N16_INNER_RADIUS=77.14 (snap で 77.10 M に補正)
#          SIM_N16_MAXRLS=未設定 (rpar 原本の 9 を使用)
make run-gw150914-n16-feasibility \
    SIM_MPI_PROCS=1 SIM_OMP_THREADS=16 SIM_ITLAST=16
```

実測 (np=1 × OMP=16, evolve 16 iter):
- wall time 4m27s, peak mem 21 GiB, **1.84 sec/iter**
- フル run 見積もり: 900 M (マージャー) で **5.1 日**, 1000 M で 5.7 日
- 30 分 timeout (`SIM_RUN_TIMEOUT`) で OOM ハング (Phase 3b-i で 297 分
  ハングを実測) を防止

### テスト

テストは 2 層構造で、marker で分離している:

| Level | Marker | 内容 | 実行時間 | 依存 |
| --- | --- | --- | --- | --- |
| 1 | `smoke` | rpar → par 生成パイプラインの純 Python テスト | < 1 秒 | Python のみ |
| 2 | `short` | cactus_sim で TwoPunctures 初期データまで実行 | 約 7 分 | Docker + Cactus |

```bash
make test-host-smoke  # ホスト python3 で Level 1 のみ（Docker 不要）
make test-smoke       # コンテナ内で Level 1
make test-short       # コンテナ内で Level 1+2
make test-all         # 全テスト
```

### シミュレーション実行

Phase 3（本番実行）までの整備完了後、ここに手順を追記する。
暫定的な想定は以下のとおり:

```bash
# GW150914 パラメータファイルで低解像度実行（予定）
make simulate N=16

# 軌道・波形のプロット（予定）
make plot
```

## 進捗状況

| Phase | 内容 | 状態 |
| --- | --- | --- |
| 0 | プロジェクト初期化・ドキュメント整備 | ✅ 完了 |
| 1 | Docker 環境構築 ([#1](https://github.com/s-sasaki-earthsea-wizard/gw150914-einstein-toolkit/issues/1)) | ✅ 完了 |
| 2 | GW150914 パラメータファイル取得・テスト基盤 ([#2](https://github.com/s-sasaki-earthsea-wizard/gw150914-einstein-toolkit/issues/2)) | ✅ 完了 |
| 3a | qc0-mclachlan.par による ET feasibility 確認 ([#10](https://github.com/s-sasaki-earthsea-wizard/gw150914-einstein-toolkit/issues/10)) | ✅ 完了 |
| 3b-i | N=28 メモリ/時間 feasibility 計測 | ✅ 完了 (np=1 OMP=16 で 50 GiB / 16 日見込み) |
| 3b-ii | N=16 対応 rpar grid 改変 ([#9](https://github.com/s-sasaki-earthsea-wizard/gw150914-einstein-toolkit/issues/9)) | ✅ 完了 (sphere_inner_radius 拡大で 1.84 sec/iter, 21 GiB, ringdown ~5.7 日見込み) |
| 3c | GW150914 本番実行 (N=16) ([#3](https://github.com/s-sasaki-earthsea-wizard/gw150914-einstein-toolkit/issues/3)) | 未着手 |
| 4 | 軌道・波形の抽出とプロット + Zenodo N=28 比較 ([#4](https://github.com/s-sasaki-earthsea-wizard/gw150914-einstein-toolkit/issues/4)) | 未着手 |
| 5 | 3D 可視化（オプション, [#5](https://github.com/s-sasaki-earthsea-wizard/gw150914-einstein-toolkit/issues/5)) | 未着手 |

## 参考資料

- Einstein Toolkit BBH Gallery: <https://einsteintoolkit.org/gallery/bbh/index.html>
- `docs/Binary Black Hole.pdf`: 上記ページのPDF版（リポジトリ外、gitignore対象）
- LIGO による発見論文: [Phys. Rev. Lett. 116, 061102](http://dx.doi.org/10.1103/PhysRevLett.116.061102)
- LIGO 解析論文: <http://arxiv.org/abs/1602.03840>
- GW150914 パラメータファイル:
  <https://bitbucket.org/einsteintoolkit/einsteinexamples/raw/master/par/GW150914/GW150914.rpar>
- **Zenodo 公式 N=28 診断データ** (Phase 4 比較用): <https://doi.org/10.5281/zenodo.155394>

## ライセンス

TBD
