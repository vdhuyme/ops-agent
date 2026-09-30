#!/usr/bin/env bash
# deamon.sh — controller script for the ops-agent LangGraph backend.
#
# Usage:
#   ./scripts/deamon.sh install    # one-time: create .venv (uv or python3 -m venv) + install deps
#   ./scripts/deamon.sh start      # run `langgraph dev --host 0.0.0.0` in background (detached)
#   ./scripts/deamon.sh stop       # stop the running daemon gracefully (SIGTERM → SIGKILL)
#   ./scripts/deamon.sh restart    # stop then start
#   ./scripts/deamon.sh status     # show pid + last log lines
#   ./scripts/deamon.sh logs       # tail -f the log file
#
# Run this on Ubuntu. It assumes Python >=3.10 is available as `python3`.
# `uv` is preferred when present (pyproject.toml uses PEP 735 dependency-groups),
# otherwise it falls back to `python3 -m venv` + `pip install -e ".[dev]"`.

set -euo pipefail

# POSIX-only: refuse early on Windows shells (Git Bash, MSYS2, Cygwin).
# nohup / setsid / kill -0 are not real there and the script would fail
# with cryptic errors. Run it on Ubuntu (native, VM, or WSL).
case "$(uname -s 2>/dev/null || echo unknown)" in
  MINGW*|MSYS*|CYGWIN*|Windows_NT)
    echo "[deamon] ERROR: this script is POSIX-only (uses nohup/setsid/kill -0)." >&2
    echo "[deamon] Detected Windows shell. Run it on Ubuntu — native, VM, or WSL." >&2
    exit 1
    ;;
esac

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
VENV_DIR="$PROJECT_DIR/.venv"
RUN_DIR="$PROJECT_DIR/.run"
LOG_DIR="$PROJECT_DIR/logs"
PID_FILE="$RUN_DIR/ops-agent.pid"
LOG_FILE="$LOG_DIR/ops-agent.log"

ACTION="${1:-status}"

mkdir -p "$RUN_DIR" "$LOG_DIR"

# ---- helpers -------------------------------------------------------------

ensure_venv() {
  if [[ -x "$VENV_DIR/bin/python" ]]; then
    return 0
  fi
  echo "[deamon] creating virtualenv at $VENV_DIR"
  if command -v uv >/dev/null 2>&1; then
    ( cd "$PROJECT_DIR" && uv venv "$VENV_DIR" )
  else
    python3 -m venv "$VENV_DIR"
  fi
}

ensure_deps() {
  ensure_venv
  # shellcheck disable=SC1091
  source "$VENV_DIR/bin/activate"
  if ! command -v langgraph >/dev/null 2>&1; then
    echo "[deamon] installing project + dev deps (langgraph-cli lives in [dev])"
    if command -v uv >/dev/null 2>&1; then
      ( cd "$PROJECT_DIR" && uv sync --group dev )
    else
      python -m pip install --upgrade pip
      python -m pip install -e ".[dev]"
    fi
  fi
}

is_running() {
  [[ -f "$PID_FILE" ]] || return 1
  local pid
  pid="$(cat "$PID_FILE" 2>/dev/null || true)"
  [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null
}

pid_of() {
  cat "$PID_FILE" 2>/dev/null || true
}

# ---- actions -------------------------------------------------------------

do_install() {
  ensure_deps
  echo "[deamon] install ok — venv: $VENV_DIR"
}

do_start() {
  if is_running; then
    echo "[deamon] already running (pid $(pid_of))"
    return 0
  fi
  ensure_deps
  # Truncate the log so each fresh start begins with a clean file.
  : > "$LOG_FILE"
  echo "[deamon] starting 'langgraph dev --host 0.0.0.0' (logs: $LOG_FILE)"
  # shellcheck disable=SC1091
  source "$VENV_DIR/bin/activate"
  cd "$PROJECT_DIR"
  # nohup + setsid + & → fully detached from the controlling terminal.
  nohup setsid langgraph dev --host 0.0.0.0 \
    >> "$LOG_FILE" 2>&1 < /dev/null &
  echo $! > "$PID_FILE"
  sleep 1
  if ! is_running; then
    echo "[deamon] failed to start — last log lines:" >&2
    tail -n 50 "$LOG_FILE" >&2 || true
    return 1
  fi
  echo "[deamon] started (pid $(pid_of))"
}

do_stop() {
  if ! is_running; then
    echo "[deamon] not running"
    rm -f "$PID_FILE"
    return 0
  fi
  local pid
  pid="$(pid_of)"
  echo "[deamon] stopping (pid $pid)"
  kill "$pid" 2>/dev/null || true
  for _ in $(seq 1 30); do
    kill -0 "$pid" 2>/dev/null || break
    sleep 1
  done
  if kill -0 "$pid" 2>/dev/null; then
    echo "[deamon] still alive, sending SIGKILL"
    kill -9 "$pid" 2>/dev/null || true
  fi
  rm -f "$PID_FILE"
}

do_restart() {
  do_stop
  do_start
}

do_status() {
  if is_running; then
    echo "[deamon] running (pid $(pid_of)) — log: $LOG_FILE"
  else
    echo "[deamon] not running"
  fi
  echo "----- last 20 log lines -----"
  tail -n 20 "$LOG_FILE" 2>/dev/null || echo "(log file missing)"
}

do_logs() {
  tail -n +1 -f "$LOG_FILE"
}

case "$ACTION" in
  install)  do_install ;;
  start)    do_start ;;
  stop)     do_stop ;;
  restart)  do_restart ;;
  status)   do_status ;;
  logs)     do_logs ;;
  *)
    echo "Usage: $0 {install|start|stop|restart|status|logs}" >&2
    exit 2
    ;;
esac