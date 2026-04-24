"""rpar → par 生成ユーティリティ

GW150914.rpar は Python スクリプトであり、`@N@` / `@SIMULATION_NAME@` /
`@WALLTIME_HOURS@` の 3 プレースホルダを文字列置換した後に
`python3 <rpar>` で実行することで同ディレクトリに `.par` を生成する。

本モジュールはその一連の処理をラップし、さらに生成後の .par に対して
Cactus パラメータを後付けで上書きする `overrides` を提供する。
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
) -> Path:
    """rpar のプレースホルダを置換して実行し、.par を生成する

    Args:
        dest_dir: 生成物を置くディレクトリ（存在しなければ作成）
        n: 最細グリッド半径方向のセル数（rpar の `N`）
        simulation_name: `@SIMULATION_NAME@` の置換値（IO::out_dir に使われる）
        walltime_hours: `@WALLTIME_HOURS@` の置換値（TerminationTrigger 用）
        overrides: 生成後の .par に対する Cactus パラメータ上書き辞書

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
