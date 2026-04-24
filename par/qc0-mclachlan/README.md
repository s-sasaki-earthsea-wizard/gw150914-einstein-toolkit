# qc0-mclachlan パラメータファイル

Einstein Toolkit の標準テスト用 BBH parfile である `qc0-mclachlan.par` を
**本プロジェクトのリポジトリには含めない**。ライセンス上オープンデータではあるが、
上流 Einstein Toolkit プロジェクトの著作物なので、ユーザ側で公式から取得する。

## 位置付け

Phase 3a (ET feasibility 確認) で使用する。GW150914 ではなく等質量・無スピンの
短インスパイラル BBH だが、**grid 構造が小規模マシンでも走るよう tuning 済み**で、
「Einstein Toolkit / Cactus / MPI / 出力パイプラインが正しく動くか」を GW150914
本体の grid 問題から切り離して検証できる。

GW150914 本番 (Phase 3b/3c) とは別スコープ。

## 取得方法

```bash
make fetch-qc0
```

- 取得先: <https://bitbucket.org/einsteintoolkit/einsteinexamples/raw/master/par/qc0-mclachlan.par>
- 保存先: `par/qc0-mclachlan/qc0-mclachlan.par`
- 整合性検証: sidecar の `qc0-mclachlan.par.sha256` と照合

## 再取得 / 検証

```bash
make refetch-qc0   # 削除して取り直す
make verify-qc0    # sha256 のみ確認
```

## ディレクトリ構成

| パス | 内容 | git |
| --- | --- | --- |
| `qc0-mclachlan.par` | 公式原本 (make fetch-qc0 で取得) | 管理外 |
| `qc0-mclachlan.par.sha256` | sha256 sidecar | 管理対象 |
| `README.md` | 本ファイル | 管理対象 |

## 上流ライセンス

Einstein Toolkit 本体の ET license (LGPL 系) に従う。詳細は
[einsteintoolkit.org](https://einsteintoolkit.org/about.html) を参照。
