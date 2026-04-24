# GW150914 パラメータファイル

Einstein Toolkit 公式ギャラリーの GW150914 パラメータファイル (`GW150914.rpar`)
を **本プロジェクトのリポジトリには含めない**。ライセンス上オープンデータではあるが、
上流の Einstein Toolkit プロジェクトの著作物なので、ユーザ側で公式から取得する。

## 取得方法

```bash
make fetch-parfile
```

- 取得先: <https://bitbucket.org/einsteintoolkit/einsteinexamples/raw/master/par/GW150914/GW150914.rpar>
- 保存先: `par/GW150914/GW150914.rpar`
- 整合性検証: `makefiles/data.mk` 内の `PARFILE_SHA256` と照合

## 再取得 / 検証

```bash
make refetch-parfile   # 削除して取り直す
make verify-parfile    # sha256 のみ確認
```

## ディレクトリ構成

| パス | 内容 | git |
| --- | --- | --- |
| `GW150914.rpar` | 公式原本 (make fetch-parfile で取得) | 管理外 |
| `generated/` | テストが都度生成する `.par` | 管理外 |
| `README.md` | 本ファイル | 管理対象 |

## 上流ライセンス

Einstein Toolkit 本体の ET license (LGPL 系) に従う。詳細は
[einsteintoolkit.org](https://einsteintoolkit.org/about.html) を参照。
