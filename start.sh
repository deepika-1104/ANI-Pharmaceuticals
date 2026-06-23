#!/usr/bin/env bash
# =============================================================================
#  ANI-VOXA — Development Launcher (macOS / Linux)
#  Usage:  ./start.sh            # launch both services
#          ./start.sh backend    # backend only
#          ./start.sh frontend   # frontend only
# =============================================================================

set -euo pipefail

# ── Colours ──────────────────────────────────────────────────────────────────
RED='\033[0;31m'
GRN='\033[0;32m'
YLW='\033[0;33m'
BLU='\033[0;34m'
CYN='\033[0;36m'
WHT='\033[1;37m'
DIM='\033[2m'
RST='\033[0m'

info()  { echo -e "${BLU}  [INFO] ${RST} $*"; }
ok()    { echo -e "${GRN}  [ OK ] ${RST} $*"; }
warn()  { echo -e "${YLW}  [WARN] ${RST} $*"; }
error() { echo -e "${RED} [ERROR] ${RST} $*" >&2; }
die()   { error "$*"; exit 1; }

# ── Banner ────────────────────────────────────────────────────────────────────
echo ""
echo -e "${CYN}  ============================================================${RST}"
echo -e "${WHT}   ANI-VOXA  |  Development Launcher${RST}"
echo -e "${CYN}  ============================================================${RST}"
echo ""

# ── Paths ─────────────────────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$SCRIPT_DIR/backend"
FRONTEND_DIR="$SCRIPT_DIR/frontend"
ENV_FILE="$BACKEND_DIR/.env"
ENV_EXAMPLE="$BACKEND_DIR/.env.example"
MODE="${1:-both}"   # both | backend | frontend

# ── OS detection ──────────────────────────────────────────────────────────────
OS="$(uname -s)"
case "$OS" in
  Darwin) PLATFORM="macOS" ;;
  Linux)  PLATFORM="Linux" ;;
  *)      die "Unsupported OS: $OS (Windows users: use start.bat)" ;;
esac
info "Platform: $PLATFORM"

# ── Sanity checks ─────────────────────────────────────────────────────────────
[[ -f "$BACKEND_DIR/main.py" ]]     || die "backend/main.py not found. Run from the project root."
[[ -f "$FRONTEND_DIR/package.json" ]] || die "frontend/package.json not found."

# ── Python version check ──────────────────────────────────────────────────────
if command -v python3 &>/dev/null; then
  PY_BIN="python3"
elif command -v python &>/dev/null; then
  PY_BIN="python"
else
  die "Python not found. Install Python 3.10+ first.\n  macOS:  brew install python@3.12\n  Ubuntu: sudo apt install python3 python3-venv python3-pip"
fi

PY_VER="$("$PY_BIN" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
PY_MAJOR="${PY_VER%%.*}"
PY_MINOR="${PY_VER#*.}"

if [[ "$PY_MAJOR" -lt 3 ]] || { [[ "$PY_MAJOR" -eq 3 ]] && [[ "$PY_MINOR" -lt 10 ]]; }; then
  die "Python 3.10+ required (found $PY_VER).\n  macOS:  brew install python@3.12\n  Ubuntu: sudo apt install python3.12"
fi
ok "Python $PY_VER ($PY_BIN)"

# ── Node version check ────────────────────────────────────────────────────────
if ! command -v node &>/dev/null; then
  die "Node.js not found. Install Node.js 18+ first.\n  macOS:  brew install node\n  Ubuntu: curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash - && sudo apt install -y nodejs"
fi

NODE_VER="$(node --version)"   # e.g. v20.11.0
NODE_MAJOR="${NODE_VER#v}"
NODE_MAJOR="${NODE_MAJOR%%.*}"
if [[ "$NODE_MAJOR" -lt 18 ]]; then
  die "Node.js 18+ required (found $NODE_VER)."
fi
ok "Node.js $NODE_VER"

# ── .env check ────────────────────────────────────────────────────────────────
if [[ ! -f "$ENV_FILE" ]]; then
  if [[ -f "$ENV_EXAMPLE" ]]; then
    warn ".env not found — copying from .env.example"
    cp "$ENV_EXAMPLE" "$ENV_FILE"
    echo ""
    echo -e "${YLW}  ┌─────────────────────────────────────────────────────────┐${RST}"
    echo -e "${YLW}  │  ACTION REQUIRED: edit backend/.env before continuing    │${RST}"
    echo -e "${YLW}  │                                                          │${RST}"
    echo -e "${YLW}  │  Minimum required fields:                                │${RST}"
    echo -e "${YLW}  │    LLM_PROVIDER=groq                                     │${RST}"
    echo -e "${YLW}  │    LLM_API_KEY=gsk_...                                   │${RST}"
    echo -e "${YLW}  │    MONGO_URI=mongodb+srv://user:pass@cluster...          │${RST}"
    echo -e "${YLW}  │    MONGO_DB_NAME=voxa                                    │${RST}"
    echo -e "${YLW}  │    JWT_SECRET=<long-random-string>                       │${RST}"
    echo -e "${YLW}  └─────────────────────────────────────────────────────────┘${RST}"
    echo ""
    echo -e "  Open ${CYN}backend/.env${RST} in your editor, fill in the values, then re-run this script."
    exit 1
  else
    die ".env not found and .env.example is missing. Re-clone the repository."
  fi
fi
ok ".env found"

# ── Virtual environment ───────────────────────────────────────────────────────
VENV_DIR="$BACKEND_DIR/.venv"
if [[ ! -d "$VENV_DIR" ]]; then
  info "Creating Python virtual environment ..."
  "$PY_BIN" -m venv "$VENV_DIR" || die "Failed to create venv. Install python3-venv:\n  sudo apt install python3-venv"
  ok "Virtual environment created at backend/.venv"
fi

PY_VENV="$VENV_DIR/bin/python"
PIP_VENV="$VENV_DIR/bin/pip"

# ── Install Python dependencies ───────────────────────────────────────────────
REQS_FILE="$BACKEND_DIR/requirements.txt"
STAMP_FILE="$VENV_DIR/.install_stamp"

if [[ ! -f "$STAMP_FILE" ]] || [[ "$REQS_FILE" -nt "$STAMP_FILE" ]]; then
  info "Installing Python dependencies (this may take a minute first time) ..."
  "$PIP_VENV" install --upgrade pip -q
  "$PIP_VENV" install -r "$REQS_FILE" -q || die "pip install failed. Check requirements.txt."
  touch "$STAMP_FILE"
  ok "Python dependencies installed"
else
  ok "Python dependencies up-to-date"
fi

# ── Install Node dependencies ─────────────────────────────────────────────────
if [[ ! -d "$FRONTEND_DIR/node_modules" ]]; then
  info "Installing Node dependencies (first-time setup) ..."
  (cd "$FRONTEND_DIR" && npm install --silent) || die "npm install failed."
  ok "Node dependencies installed"
else
  ok "Node dependencies up-to-date"
fi

# ── Free port 8000 if occupied ────────────────────────────────────────────────
if lsof -ti tcp:8000 &>/dev/null; then
  PIDS="$(lsof -ti tcp:8000)"
  warn "Port 8000 in use (PIDs: $PIDS) — killing ..."
  kill -9 $PIDS 2>/dev/null || true
  sleep 1
  ok "Port 8000 freed"
fi

# ── Log files ─────────────────────────────────────────────────────────────────
LOG_DIR="$SCRIPT_DIR/.logs"
mkdir -p "$LOG_DIR"
BACKEND_LOG="$LOG_DIR/backend.log"
FRONTEND_LOG="$LOG_DIR/frontend.log"

# ── PID tracking ──────────────────────────────────────────────────────────────
BACKEND_PID=""
FRONTEND_PID=""

# ── Cleanup on Ctrl+C ─────────────────────────────────────────────────────────
cleanup() {
  echo ""
  info "Stopping ANI-VOXA services ..."
  [[ -n "$BACKEND_PID" ]]  && kill "$BACKEND_PID"  2>/dev/null && ok "Backend stopped"
  [[ -n "$FRONTEND_PID" ]] && kill "$FRONTEND_PID" 2>/dev/null && ok "Frontend stopped"
  # Belt and braces: kill anything still on 8000 / 5173
  lsof -ti tcp:8000 | xargs kill -9 2>/dev/null || true
  lsof -ti tcp:5173 | xargs kill -9 2>/dev/null || true
  echo ""
  echo -e "${DIM}  Logs saved to .logs/backend.log and .logs/frontend.log${RST}"
  echo ""
  exit 0
}
trap cleanup SIGINT SIGTERM

# ── Helper: open new terminal window ─────────────────────────────────────────
# Returns 0 if a window was opened, 1 if no suitable terminal was found.
open_terminal() {
  local title="$1"
  local cmd="$2"

  if [[ "$PLATFORM" == "macOS" ]]; then
    osascript -e "tell application \"Terminal\"
      do script \"echo -e '\\\\033[0;36m  $title\\\\033[0m'; $cmd\"
      set custom title of front window to \"$title\"
    end tell" &>/dev/null && return 0
  fi

  # Linux — try common terminal emulators in order
  for term in gnome-terminal xterm konsole xfce4-terminal lxterminal mate-terminal tilix; do
    if command -v "$term" &>/dev/null; then
      case "$term" in
        gnome-terminal) gnome-terminal --title="$title" -- bash -c "$cmd; exec bash" &>/dev/null & return 0 ;;
        xterm)          xterm -T "$title" -e bash -c "$cmd; exec bash" &>/dev/null & return 0 ;;
        konsole)        konsole --title "$title" -e bash -c "$cmd; exec bash" &>/dev/null & return 0 ;;
        *)              "$term" -e bash -c "$cmd; exec bash" &>/dev/null & return 0 ;;
      esac
    fi
  done
  return 1
}

# ── Launch backend ────────────────────────────────────────────────────────────
launch_backend() {
  info "Starting backend  →  http://localhost:8000"

  BACKEND_CMD="cd '$BACKEND_DIR' && '$PY_VENV' -m uvicorn main:app --reload --host 0.0.0.0 --port 8000"

  if open_terminal "ANI-VOXA Backend" "$BACKEND_CMD"; then
    ok "Backend launched in a new terminal window"
    BACKEND_PID=""
  else
    info "No terminal emulator found — running backend in background"
    bash -c "$BACKEND_CMD" >> "$BACKEND_LOG" 2>&1 &
    BACKEND_PID=$!
    ok "Backend started (PID $BACKEND_PID) — logs: .logs/backend.log"
  fi
}

# ── Launch frontend ───────────────────────────────────────────────────────────
launch_frontend() {
  info "Starting frontend →  http://localhost:5173"

  FRONTEND_CMD="cd '$FRONTEND_DIR' && npm run dev"

  if open_terminal "ANI-VOXA Frontend" "$FRONTEND_CMD"; then
    ok "Frontend launched in a new terminal window"
    FRONTEND_PID=""
  else
    info "No terminal emulator found — running frontend in background"
    bash -c "$FRONTEND_CMD" >> "$FRONTEND_LOG" 2>&1 &
    FRONTEND_PID=$!
    ok "Frontend started (PID $FRONTEND_PID) — logs: .logs/frontend.log"
  fi
}

# ── Mode dispatch ─────────────────────────────────────────────────────────────
case "$MODE" in
  backend)
    launch_backend
    ;;
  frontend)
    launch_frontend
    ;;
  both)
    launch_backend
    sleep 2       # give the backend a moment before the frontend hits the health check
    launch_frontend
    ;;
  *)
    die "Unknown mode '$MODE'. Usage: ./start.sh [both|backend|frontend]"
    ;;
esac

# ── Status monitor ────────────────────────────────────────────────────────────
sleep 2
echo ""
echo -e "${CYN}  ============================================================${RST}"
echo -e "${WHT}   ANI-VOXA  |  Services Running${RST}"
echo -e "${CYN}  ============================================================${RST}"
echo ""
echo -e "   Backend   :  ${GRN}http://localhost:8000${RST}"
echo -e "   Frontend  :  ${GRN}http://localhost:5173${RST}"
echo -e "   API docs  :  ${GRN}http://localhost:8000/docs${RST}"
echo -e "   Health    :  ${GRN}http://localhost:8000/api/health${RST}"
echo ""
echo -e "${CYN}  ============================================================${RST}"
echo ""

# ── Wait / keep-alive ─────────────────────────────────────────────────────────
# If both services are in background processes, wait on them.
# If they're in separate windows we just block until Ctrl+C.
if [[ -n "$BACKEND_PID" || -n "$FRONTEND_PID" ]]; then
  echo -e "${DIM}  Services running in background. Press Ctrl+C to stop.${RST}"
  echo ""
  # Stream a live tail of backend logs so the terminal isn't silent
  if [[ -f "$BACKEND_LOG" ]]; then
    echo -e "${DIM}  ── backend log (live) ─────────────────────────────${RST}"
    tail -f "$BACKEND_LOG" &
    TAIL_PID=$!
    # Wait for background service processes
    wait "$BACKEND_PID" "$FRONTEND_PID" 2>/dev/null || true
    kill "$TAIL_PID" 2>/dev/null || true
  else
    wait "$BACKEND_PID" "$FRONTEND_PID" 2>/dev/null || true
  fi
else
  # Services are in separate windows — just keep this terminal open
  echo -e "${DIM}  Services are running in their own terminal windows.${RST}"
  echo -e "${DIM}  Press Ctrl+C here to stop everything.${RST}"
  echo ""
  while true; do sleep 60; done
fi
