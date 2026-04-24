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
| 2 | GW150914 パラメータファイル取得・N=16 調整 | [#2](https://github.com/s-sasaki-earthsea-wizard/gw150914-einstein-toolkit/issues/2) | 未着手 |
| 3 | シミュレーション実行 | [#3](https://github.com/s-sasaki-earthsea-wizard/gw150914-einstein-toolkit/issues/3) | 未着手 |
| 4 | 軌道・波形の抽出とプロット | [#4](https://github.com/s-sasaki-earthsea-wizard/gw150914-einstein-toolkit/issues/4) | 未着手 |
| 5 | 3D 可視化（オプション） | [#5](https://github.com/s-sasaki-earthsea-wizard/gw150914-einstein-toolkit/issues/5) | 未着手 |

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
