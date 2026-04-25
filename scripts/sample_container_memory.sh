#!/usr/bin/env bash
# Docker コンテナのメモリ使用量を一定間隔でサンプリングして追記するデーモン.
#
# 目的: シミュレーション実行中のコンテナ合計メモリを時系列で記録し、
# 後段で peak を求めるために使う (Phase 3b / 3c の feasibility 計測).
#
# usage: sample_container_memory.sh <container-name> <output-file> [interval_seconds]
#
# 親プロセスから SIGTERM を受けた時点でクリーン終了する。
# docker stats が取得不能になっても (コンテナ停止等) 継続する。

set -u

CONTAINER="${1:?container name required}"
OUTFILE="${2:?output file required}"
INTERVAL="${3:-2}"

trap 'exit 0' TERM INT

# ヘッダ書き込み (先頭行のみ).
if [ ! -s "$OUTFILE" ]; then
    echo "# timestamp_epoch  mem_usage  /  mem_limit  mem_percent" >> "$OUTFILE"
fi

while true; do
    ts=$(date +%s)
    # --no-stream にすると 1 回だけ取得して返す。
    # エラー (コンテナ未起動等) は空文字を返して継続。
    stats=$(docker stats --no-stream \
        --format '{{.MemUsage}} {{.MemPerc}}' \
        "$CONTAINER" 2>/dev/null || echo "unavailable")
    echo "$ts $stats" >> "$OUTFILE"
    sleep "$INTERVAL"
done
