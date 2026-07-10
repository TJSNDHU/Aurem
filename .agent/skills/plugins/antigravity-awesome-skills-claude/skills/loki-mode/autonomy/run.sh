#!/bin/bash
#===============================================================================
# Loki Mode - Autonomous Runner
# Single script that handles prerequisites, setup, and autonomous execution
#
# Usage:
#   ./autonomy/run.sh [PRD_PATH]
#   ./autonomy/run.sh ./docs/requirements.md
#   ./autonomy/run.sh                          # Interactive mode
#
# Environment Variables:
#   LOKI_MAX_RETRIES    - Max retry attempts (default: 50)
#   LOKI_BASE_WAIT      - Base wait time in seconds (default: 60)
#   LOKI_MAX_WAIT       - Max wait time in seconds (default: 3600)
#   LOKI_SKIP_PREREQS   - Skip prerequisite checks (default: false)
#   LOKI_DASHBOARD      - Enable web dashboard (default: true)
#   LOKI_DASHBOARD_PORT - Dashboard port (default: 57374)
#
# Resource Monitoring (prevents system overload):
#   LOKI_RESOURCE_CHECK_INTERVAL - Check resources every N seconds (default: 300 = 5min)
#   LOKI_RESOURCE_CPU_THRESHOLD  - CPU % threshold to warn (default: 80)
#   LOKI_RESOURCE_MEM_THRESHOLD  - Memory % threshold to warn (default: 80)
#
# Security & Autonomy Controls (Enterprise):
#   LOKI_STAGED_AUTONOMY    - Require approval before execution (default: false)
#   LOKI_AUDIT_LOG          - Enable audit logging (default: false)
#   LOKI_MAX_PARALLEL_AGENTS - Limit concurrent agent spawning (default: 10)
#   LOKI_SANDBOX_MODE       - Run in sandboxed container (default: false, requires Docker)
#   LOKI_ALLOWED_PATHS      - Comma-separated paths agents can modify (default: all)
#   LOKI_BLOCKED_COMMANDS   - Comma-separated blocked shell commands (default: rm -rf /)
#
# SDLC Phase Controls (all enabled by default, set to 'false' to skip):
#   LOKI_PHASE_UNIT_TESTS      - Run unit tests (default: true)
#   LOKI_PHASE_API_TESTS       - Functional API testing (default: true)
#   LOKI_PHASE_E2E_TESTS       - E2E/UI testing with Playwright (default: true)
#   LOKI_PHASE_SECURITY        - Security scanning OWASP/auth (default: true)
#   LOKI_PHASE_INTEGRATION     - Integration tests SAML/OIDC/SSO (default: true)
#   LOKI_PHASE_CODE_REVIEW     - 3-reviewer parallel code review (default: true)
#   LOKI_PHASE_WEB_RESEARCH    - Competitor/feature gap research (default: true)
#   LOKI_PHASE_PERFORMANCE     - Load/performance testing (default: true)
#   LOKI_PHASE_ACCESSIBILITY   - WCAG compliance testing (default: true)
#   LOKI_PHASE_REGRESSION      - Regression testing (default: true)
#   LOKI_PHASE_UAT             - UAT simulation (default: true)
#
# Autonomous Loop Controls (Ralph Wiggum Mode):
#   LOKI_COMPLETION_PROMISE    - EXPLICIT stop condition text (default: none - runs forever)
#                                Example: "ALL TESTS PASSING 100%"
#                                Only stops when Claude outputs this EXACT text
#   LOKI_MAX_ITERATIONS        - Max loop iterations before exit (default: 1000)
#   LOKI_PERPETUAL_MODE        - Ignore ALL completion signals (default: false)
#                                Set to 'true' for truly infinite operation
#===============================================================================

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

#===============================================================================
# Self-Copy Protection
# Bash reads scripts incrementally, so editing a running script corrupts execution.
# Solution: Copy ourselves to /tmp and run from there. The original can be safely edited.
#===============================================================================
if [[ -z "${LOKI_RUNNING_FROM_TEMP:-}" ]]; then
    TEMP_SCRIPT="/tmp/loki-run-$$.sh"
    cp "${BASH_SOURCE[0]}" "$TEMP_SCRIPT"
    chmod +x "$TEMP_SCRIPT"
    export LOKI_RUNNING_FROM_TEMP=1
    export LOKI_ORIGINAL_SCRIPT_DIR="$SCRIPT_DIR"
    export LOKI_ORIGINAL_PROJECT_DIR="$PROJECT_DIR"
    exec "$TEMP_SCRIPT" "$@"
fi

# Restore original paths when running from temp
SCRIPT_DIR="${LOKI_ORIGINAL_SCRIPT_DIR:-$SCRIPT_DIR}"
PROJECT_DIR="${LOKI_ORIGINAL_PROJECT_DIR:-$PROJECT_DIR}"

# Clean up temp script on exit
trap 'rm -f "${BASH_SOURCE[0]}" 2>/dev/null' EXIT

# Configuration
MAX_RETRIES=${LOKI_MAX_RETRIES:-50}
BASE_WAIT=${LOKI_BASE_WAIT:-60}
MAX_WAIT=${LOKI_MAX_WAIT:-3600}
SKIP_PREREQS=${LOKI_SKIP_PREREQS:-false}
ENABLE_DASHBOARD=${LOKI_DASHBOARD:-true}
DASHBOARD_PORT=${LOKI_DASHBOARD_PORT:-57374}
RESOURCE_CHECK_INTERVAL=${LOKI_RESOURCE_CHECK_INTERVAL:-300}  # Check every 5 minutes
RESOURCE_CPU_THRESHOLD=${LOKI_RESOURCE_CPU_THRESHOLD:-80}     # CPU % threshold
RESOURCE_MEM_THRESHOLD=${LOKI_RESOURCE_MEM_THRESHOLD:-80}     # Memory % threshold

# Security & Autonomy Controls
STAGED_AUTONOMY=${LOKI_STAGED_AUTONOMY:-false}           # Require plan approval
AUDIT_LOG_ENABLED=${LOKI_AUDIT_LOG:-false}               # Enable audit logging
MAX_PARALLEL_AGENTS=${LOKI_MAX_PARALLEL_AGENTS:-10}      # Limit concurrent agents
SANDBOX_MODE=${LOKI_SANDBOX_MODE:-false}                 # Docker sandbox mode
ALLOWED_PATHS=${LOKI_ALLOWED_PATHS:-""}                  # Empty = all paths allowed
BLOCKED_COMMANDS=${LOKI_BLOCKED_COMMANDS:-"rm -rf /,dd if=,mkfs,:(){ :|:& };:"}

STATUS_MONITOR_PID=""
DASHBOARD_PID=""
RESOURCE_MONITOR_PID=""

# SDLC Phase Controls (all enabled by default)
PHASE_UNIT_TESTS=${LOKI_PHASE_UNIT_TESTS:-true}
PHASE_API_TESTS=${LOKI_PHASE_API_TESTS:-true}
PHASE_E2E_TESTS=${LOKI_PHASE_E2E_TESTS:-true}
PHASE_SECURITY=${LOKI_PHASE_SECURITY:-true}
PHASE_INTEGRATION=${LOKI_PHASE_INTEGRATION:-true}
PHASE_CODE_REVIEW=${LOKI_PHASE_CODE_REVIEW:-true}
PHASE_WEB_RESEARCH=${LOKI_PHASE_WEB_RESEARCH:-true}
PHASE_PERFORMANCE=${LOKI_PHASE_PERFORMANCE:-true}
PHASE_ACCESSIBILITY=${LOKI_PHASE_ACCESSIBILITY:-true}
PHASE_REGRESSION=${LOKI_PHASE_REGRESSION:-true}
PHASE_UAT=${LOKI_PHASE_UAT:-true}

# Autonomous Loop Controls (Ralph Wiggum Mode)
# Default: No auto-completion - runs until max iterations or explicit promise
COMPLETION_PROMISE=${LOKI_COMPLETION_PROMISE:-""}
MAX_ITERATIONS=${LOKI_MAX_ITERATIONS:-1000}
ITERATION_COUNT=0
# Perpetual mode: never stop unless max iterations (ignores all completion signals)
PERPETUAL_MODE=${LOKI_PERPETUAL_MODE:-false}

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

#===============================================================================
# Logging Functions
#===============================================================================

log_header() {
    echo ""
    echo -e "${BLUE}╔════════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║${NC} ${BOLD}$1${NC}"
    echo -e "${BLUE}╚════════════════════════════════════════════════════════════════╝${NC}"
}

log_info() { echo -e "${GREEN}[INFO]${NC} $*"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $*"; }
log_warning() { log_warn "$@"; }  # Alias for backwards compatibility
log_error() { echo -e "${RED}[ERROR]${NC} $*"; }
log_step() { echo -e "${CYAN}[STEP]${NC} $*"; }

#===============================================================================
# Prerequisites Check
#===============================================================================

check_prerequisites() {
    log_header "Checking Prerequisites"

    local missing=()

    # Check Claude Code CLI
    log_step "Checking Claude Code CLI..."
    if command -v claude &> /dev/null; then
        local version=$(claude --version 2>/dev/null | head -1 || echo "unknown")
        log_info "Claude Code CLI: $version"
    else
        missing+=("claude")
        log_error "Claude Code CLI not found"
        log_info "Install: https://claude.ai/code or npm install -g @anthropic-ai/claude-code"
    fi

    # Check Python 3
    log_step "Checking Python 3..."
    if command -v python3 &> /dev/null; then
        local py_version=$(python3 --version 2>&1)
        log_info "Python: $py_version"
    else
        missing+=("python3")
        log_error "Python 3 not found"
    fi

    # Check Git
    log_step "Checking Git..."
    if command -v git &> /dev/null; then
        local git_version=$(git --version)
        log_info "Git: $git_version"
    else
        missing+=("git")
        log_error "Git not found"
    fi

    # Check Node.js (optional but recommended)
    log_step "Checking Node.js (optional)..."
    if command -v node &> /dev/null; then
        local node_version=$(node --version)
        log_info "Node.js: $node_version"
    else
        log_warn "Node.js not found (optional, needed for some builds)"
    fi

    # Check npm (optional)
    if command -v npm &> /dev/null; then
        local npm_version=$(npm --version)
        log_info "npm: $npm_version"
    fi

    # Check curl (for web fetches)
    log_step "Checking curl..."
    if command -v curl