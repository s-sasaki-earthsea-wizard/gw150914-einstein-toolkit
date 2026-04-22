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

- OS: Linux (Ubuntu系想定)
- コンテナ: Docker
- Einstein Toolkit: Kruskal release（2025-10-16時点の最新版を想定）

> 詳細な要求リソース・実行時間は Phase 1（環境構築）完了後に追記する。

## インストール方法

Phase 1（Docker 環境構築）で確定後、ここに手順を記載する。
暫定的な想定は以下のとおり:

```bash
# Docker イメージのビルド（予定）
make docker-build

# コンテナ起動（予定）
make docker-run
```

## 使い方

Phase 3（シミュレーション実行）までの整備完了後、ここに手順を記載する。
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
| 0 | プロジェクト初期化・ドキュメント整備 | 進行中 |
| 1 | Docker 環境構築（Einstein Toolkit ビルド） | 未着手 |
| 2 | GW150914 パラメータファイル取得・N=16 へ調整 | 未着手 |
| 3 | シミュレーション実行 | 未着手 |
| 4 | 軌道・波形の抽出とプロット | 未着手 |
| 5 | 3D 可視化（オプション） | 未着手 |

## 参考資料

- Einstein Toolkit BBH Gallery: <https://einsteintoolkit.org/gallery/bbh/index.html>
- `docs/Binary Black Hole.pdf`: 上記ページのPDF版（リポジトリ外、gitignore対象）
- LIGO による発見論文: [Phys. Rev. Lett. 116, 061102](http://dx.doi.org/10.1103/PhysRevLett.116.061102)
- LIGO 解析論文: <http://arxiv.org/abs/1602.03840>
- GW150914 パラメータファイル:
  <https://bitbucket.org/einsteintoolkit/einsteinexamples/raw/master/par/GW150914/GW150914.rpar>

## ライセンス

TBD
