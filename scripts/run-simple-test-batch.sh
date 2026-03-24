#!/usr/bin/env bash

set -u

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TARGET_SCRIPT="$ROOT_DIR/scripts/simple-test.sh"
TIMESTAMP="$(date +"%Y%m%d-%H%M%S")"
LOG_DIR="$ROOT_DIR/logs/simple-test-$TIMESTAMP"
ROUNDS="${ROUNDS:-10}"
CONCURRENCY="${CONCURRENCY:-20}"
ROUND_INTERVAL_SECONDS="${ROUND_INTERVAL_SECONDS:-5}"

mkdir -p "$LOG_DIR"

echo "target_script=$TARGET_SCRIPT"
echo "rounds=$ROUNDS"
echo "concurrency=$CONCURRENCY"
echo "round_interval_seconds=$ROUND_INTERVAL_SECONDS"
echo "log_dir=$LOG_DIR"

all_pids=()

for round in $(seq 1 "$ROUNDS"); do
  echo "starting round $round/$ROUNDS"

  for req in $(seq 1 "$CONCURRENCY"); do
    log_file="$LOG_DIR/round-${round}-request-${req}.log"

    (
      echo "round=$round request=$req started_at=$(date +"%Y-%m-%d %H:%M:%S")"
      bash "$TARGET_SCRIPT"
      status=$?
      echo
      echo "round=$round request=$req finished_at=$(date +"%Y-%m-%d %H:%M:%S") status=$status"
      exit "$status"
    ) >"$log_file" 2>&1 &

    all_pids+=("$!")
  done

  echo "launched round $round/$ROUNDS"
  if [ "$round" -lt "$ROUNDS" ]; then
    sleep "$ROUND_INTERVAL_SECONDS"
  fi
done

failures=0
for pid in "${all_pids[@]}"; do
  if ! wait "$pid"; then
    failures=$((failures + 1))
  fi
done

echo "all rounds finished"
echo "failures=$failures"
echo "logs saved to $LOG_DIR"
