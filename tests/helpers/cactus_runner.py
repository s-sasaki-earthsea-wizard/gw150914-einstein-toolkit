"""cactus_sim サブプロセス実行ラッパ

Level 2 以降のテストで MPI 経由で cactus_sim を呼び出すための薄いヘルパ。
コンテナ内実行を前提とし、`mpirun.mpich` で MPICH を明示指定する。

環境変数で上書き可能:
    CACTUS_SIM : cactus_sim 実行ファイルの絶対パス
    MPIRUN     : mpirun 実装（デフォルト mpirun.mpich）
"""

from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path


DEFAULT_CACTUS_SIM = Path("/home/etuser/Cactus/exe/cactus_sim")
DEFAULT_MPIRUN = "mpirun.mpich"


@dataclass
class CactusResult:
    """cactus_sim の実行結果"""

    returncode: int
    stdout: str
    stderr: str
    run_dir: Path
    parfile: Path

    @property
    def ok(self) -> bool:
        return self.returncode == 0


def cactus_sim_path() -> Path:
    """cactus_sim 実行ファイルの絶対パスを返す"""
    return Path(os.environ.get("CACTUS_SIM", str(DEFAULT_CACTUS_SIM)))


def mpirun_path() -> str:
    return os.environ.get("MPIRUN", DEFAULT_MPIRUN)


def is_cactus_available() -> bool:
    """cactus_sim と mpirun が両方見つかるかを返す

    コンテナ外から pytest を呼ぶケースなどで Level 2 テストを skip する判定に使う。
    """
    return cactus_sim_path().is_file() and shutil.which(mpirun_path()) is not None


def run_cactus(
    parfile: Path,
    run_dir: Path,
    nproc: int = 1,
    timeout: float = 600.0,
) -> CactusResult:
    """cactus_sim を mpirun 経由で実行する

    Args:
        parfile: 実行する .par ファイル
        run_dir: 作業ディレクトリ（Cactus はここを基点に IO::out_dir を作る）
        nproc: MPI プロセス数
        timeout: 秒単位のタイムアウト

    Returns:
        CactusResult（非ゼロ終了でも例外は投げない）
    """
    parfile = Path(parfile).resolve()
    run_dir = Path(run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)

    cmd = [
        mpirun_path(),
        "-np",
        str(nproc),
        str(cactus_sim_path()),
        str(parfile),
    ]

    proc = subprocess.run(
        cmd,
        cwd=run_dir,
        capture_output=True,
        text=True,
        timeout=timeout,
    )

    return CactusResult(
        returncode=proc.returncode,
        stdout=proc.stdout,
        stderr=proc.stderr,
        run_dir=run_dir,
        parfile=parfile,
    )
