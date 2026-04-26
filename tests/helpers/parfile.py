"""rpar → par 生成ユーティリティ

GW150914.rpar は Python スクリプトであり、`@N@` / `@SIMULATION_NAME@` /
`@WALLTIME_HOURS@` の 3 プレースホルダを文字列置換した後に
`python3 <rpar>` で実行することで同ディレクトリに `.par` を生成する。

本モジュールはその一連の処理をラップし、さらに生成後の .par に対して
Cactus パラメータを後付けで上書きする `overrides` を提供する。

加えて Phase 3b-ii (Issue #9) 対応として、N<28 で実行する際に必要な
``maxrls`` (refinement level 数) の縮小を rpar ソースレベルでパッチ
当てする ``patch_maxrls`` 機構を提供する。原本 rpar は無改変、コピー
側にだけパッチが当たる。
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
RPAR_SOURCE = REPO_ROOT / "par" / "GW150914" / "GW150914.rpar"

PLACEHOLDERS = ("@N@", "@SIMULATION_NAME@", "@WALLTIME_HOURS@")


def generate_par(
    dest_dir: Path,
    n: int,
    simulation_name: str = "smoke",
    walltime_hours: float = 0.5,
    overrides: dict[str, Any] | None = None,
    maxrls: int | None = None,
    enable_constraint_output: bool = False,
) -> Path:
    """rpar のプレースホルダを置換して実行し、.par を生成する

    Args:
        dest_dir: 生成物を置くディレクトリ（存在しなければ作成）
        n: 最細グリッド半径方向のセル数（rpar の `N`）
        simulation_name: `@SIMULATION_NAME@` の置換値（IO::out_dir に使われる）
        walltime_hours: `@WALLTIME_HOURS@` の置換値（TerminationTrigger 用）
        overrides: 生成後の .par に対する Cactus パラメータ上書き辞書
        maxrls: 指定すると rpar ソースの ``maxrls = 9`` を上書きし、
            ``rlsp / rlsm`` を ``maxrls - 2`` で cap する（Issue #9 対応）。
            ``None`` (デフォルト) なら原本通り。
        enable_constraint_output: True で ``patch_constraint_outputs`` を適用し、
            ``ML_ADMConstraints::ML_Ham`` / ``ML_mom`` を ``IOScalar::outScalar_vars``
            に追加し、reductions に ``norm2`` / ``norm_inf`` を加える
            (Issue #4 D3, self-consistency 検証用)。

    Returns:
        生成された .par ファイルの絶対パス
    """
    if not RPAR_SOURCE.exists():
        raise FileNotFoundError(
            f"rpar 原本が見つかりません: {RPAR_SOURCE}\n"
            f"make fetch-parfile を先に実行してください"
        )

    dest_dir = Path(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)

    template = RPAR_SOURCE.read_text(encoding="utf-8")
    substituted = (
        template.replace("@N@", str(n))
        .replace("@SIMULATION_NAME@", simulation_name)
        .replace("@WALLTIME_HOURS@", str(walltime_hours))
    )

    if maxrls is not None:
        substituted = patch_maxrls(substituted, maxrls)

    if enable_constraint_output:
        substituted = patch_constraint_outputs(substituted)

    # rpar 内の sys.argv[0] から .par の出力名が決まるため
    # ファイル名は {simulation_name}.rpar にする
    rpar_copy = dest_dir / f"{simulation_name}.rpar"
    rpar_copy.write_text(substituted, encoding="utf-8")

    par_path = dest_dir / f"{simulation_name}.par"

    subprocess.run(
        [sys.executable, str(rpar_copy)],
        check=True,
        capture_output=True,
        text=True,
    )

    if not par_path.exists():
        raise RuntimeError(f"生成された .par が見つかりません: {par_path}")

    if overrides:
        apply_overrides(par_path, overrides)

    return par_path


def patch_maxrls(rpar_text: str, maxrls: int) -> str:
    """rpar ソースの ``maxrls`` を縮小し、``rlsp / rlsm`` を ``maxrls - 2`` で cap する

    公式 GW150914.rpar は N=28 前提で grid 構造が固定されており、N<28 では
    refinement level 1 の box が Thornburg04 inter-patch 境界を超えて crash する
    (Issue #9)。本関数は rpar ソースに以下のパッチを当てて、refinement 階層を
    縮小したコピーを返す。原本 rpar は触らない。

    パッチ内容:
      1. ``maxrls = 9`` → ``maxrls = <new>``
      2. ``h0_min = ...`` 行の直後に ``rlsm = min(rlsm, maxrls - 2)`` を挿入
         (h0_min の計算後にキャップすることで RL0 セルサイズを保ち、
          外側の refinement 層を 1 層以上削減する)
      3. ``rlsp = int(round(rlsp))`` 行の直後に
         ``rlsp = min(rlsp, maxrls - 2)`` を挿入

    Args:
        rpar_text: 既にプレースホルダ置換済みの rpar Python ソース全文
        maxrls: 新しい ``Carpet::max_refinement_levels``。原本では 9。
            最低でも 4 (= rlsp/rlsm が 2 以上) を許容。

    Returns:
        パッチを当てた rpar ソース全文

    Raises:
        ValueError: ``maxrls`` が小さすぎる、または rpar 内の想定行が
            見つからずパッチを当てられない場合。
    """
    if maxrls < 4:
        raise ValueError(
            f"maxrls={maxrls} は小さすぎます (最低 4 以上, "
            f"rlsp/rlsm = maxrls - 2 が 2 以上である必要)"
        )

    text, n_sub = re.subn(
        r"^maxrls = 9\b",
        f"maxrls = {maxrls}",
        rpar_text,
        count=1,
        flags=re.MULTILINE,
    )
    if n_sub != 1:
        raise ValueError(
            "rpar 内の `maxrls = 9` 行が見つかりません。原本が変更された可能性があります"
        )

    text, n_sub = re.subn(
        r"(?m)^(h0_min = hfm_min \* 2\*\*\(rlsm-1\).*)$",
        r"\1\nrlsm = min(rlsm, maxrls - 2)  # Issue #9 (Phase 3b-ii) maxrls override",
        text,
        count=1,
    )
    if n_sub != 1:
        raise ValueError("rpar 内の `h0_min = ...` 行が見つかりません")

    text, n_sub = re.subn(
        r"(?m)^(rlsp = int\(round\(rlsp\)\))$",
        r"\1\nrlsp = min(rlsp, maxrls - 2)  # Issue #9 (Phase 3b-ii) maxrls override",
        text,
        count=1,
    )
    if n_sub != 1:
        raise ValueError("rpar 内の `rlsp = int(round(rlsp))` 行が見つかりません")

    return text


def patch_constraint_outputs(rpar_text: str) -> str:
    """rpar の ``IOScalar`` 出力に Hamiltonian / Momentum constraint norm を追加する

    Phase 4 self-consistency 検証 (Issue #4 D3) のため、各 stage run で
    constraint violation の時間履歴を ASCII で取得する必要がある。公式 rpar
    は ``IOScalar::outScalar_vars`` に ``SystemStatistics::process_memory_mb``
    のみを指定し、reductions は ``"minimum maximum average"`` のため、
    constraint の L2 / L∞ ノルム時間進化が取得できない。

    本関数は rpar コピーに対し以下を実施する:
      1. ``IOScalar::outScalar_reductions`` に ``norm2`` / ``norm_inf`` を追加
      2. ``IOScalar::outScalar_vars`` を multi-line にし、
         ``ML_ADMConstraints::ML_Ham`` / ``ML_ADMConstraints::ML_mom`` を追加

    ``ML_ADMConstraints`` thorn は rpar 原本で既に ``ActiveThorns`` に
    含まれている (line 201) ため、追加 thorn の起動は不要。

    Args:
        rpar_text: 既にプレースホルダ置換済みの rpar Python ソース全文

    Returns:
        パッチを当てた rpar ソース全文

    Raises:
        ValueError: 期待する rpar 内の行が見つからない場合
    """
    text, n_sub = re.subn(
        r'^(IOScalar::outScalar_reductions\s*=\s*)"minimum maximum average"',
        r'\1"minimum maximum average norm2 norm_inf"',
        rpar_text,
        count=1,
        flags=re.MULTILINE,
    )
    if n_sub != 1:
        raise ValueError(
            "rpar 内の `IOScalar::outScalar_reductions = \"minimum maximum average\"` 行が"
            "見つかりません。原本が変更された可能性があります"
        )

    text, n_sub = re.subn(
        r'^(IOScalar::outScalar_vars\s*=\s*)"SystemStatistics::process_memory_mb"',
        (
            r'\1"\n'
            r"  SystemStatistics::process_memory_mb\n"
            r"  ML_ADMConstraints::ML_Ham\n"
            r"  ML_ADMConstraints::ML_mom\n"
            r'"'
        ),
        text,
        count=1,
        flags=re.MULTILINE,
    )
    if n_sub != 1:
        raise ValueError(
            "rpar 内の `IOScalar::outScalar_vars = \"SystemStatistics::process_memory_mb\"`"
            " 行が見つかりません"
        )

    return text


def apply_overrides(par_path: Path, overrides: dict[str, Any]) -> None:
    """Cactus .par ファイルの指定パラメータを上書きする

    既存の `Thorn::param = ...` 行がある場合は値のみ書き換え、
    存在しない場合はファイル末尾に追記する。マッチはパラメータ名の
    大小文字を無視して行う（Cactus の仕様に合わせる）。

    Args:
        par_path: 書き換え対象の .par ファイル
        overrides: パラメータ名 → 値 の辞書
            値が str なら自動でダブルクォート付き、数値ならそのまま。
    """
    text = par_path.read_text(encoding="utf-8")
    remaining = {key: value for key, value in overrides.items()}

    def _replace(match: re.Match[str]) -> str:
        indent, name, sep = match.group(1), match.group(2), match.group(3)
        for key in list(remaining):
            if key.lower() == name.lower():
                value = remaining.pop(key)
                return f"{indent}{name}{sep}{_format_value(value)}"
        return match.group(0)

    pattern = re.compile(
        r"^(\s*)([A-Za-z0-9_:\[\]]+)(\s*=\s*)[^\r\n]*$",
        re.MULTILINE,
    )
    text = pattern.sub(_replace, text)

    if remaining:
        appended = ["", "# テストハーネスにより追加された上書き"]
        for key, value in remaining.items():
            appended.append(f"{key} = {_format_value(value)}")
        text = text.rstrip() + "\n" + "\n".join(appended) + "\n"

    par_path.write_text(text, encoding="utf-8")


def _format_value(value: Any) -> str:
    """Python 値を Cactus パラメータ値へフォーマットする"""
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, str):
        return f'"{value}"'
    return str(value)
