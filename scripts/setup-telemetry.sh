#!/usr/bin/env bash
# ============================================================
# Claude Code / Gemini CLI Telemetry Setup
# Run once per machine. No administrator rights required.
# ============================================================

# On macOS, run under zsh (bash 3.2 lacks mapfile; also handles curl-pipe case).
# When invoked as a file: re-exec under zsh.
# When piped via curl: BASH_SOURCE[0] is empty, so this path should never be
# reached — the gist tells macOS users to pipe to zsh, not bash.
if [[ "$(uname -s)" == "Darwin" ]] && [[ -z "${ZSH_VERSION:-}" ]]; then
    if [[ -n "${BASH_SOURCE[0]:-}" ]]; then
        exec zsh "${BASH_SOURCE[0]}" "$@"
    else
        echo "ERROR: On macOS, run this script with zsh, not bash:"
        echo "  curl -fsSL <url> | zsh"
        exit 1
    fi
fi

set -euo pipefail

# Set this to your OTEL collector's endpoint before running, e.g.:
#   OTEL_ENDPOINT="http://otel-collector.example.com:4317" ./setup-telemetry.sh
OTEL_ENDPOINT="${OTEL_ENDPOINT:-}"
if [[ -z "$OTEL_ENDPOINT" ]]; then
    echo "ERROR: OTEL_ENDPOINT is not set." >&2
    echo "  Run: OTEL_ENDPOINT=\"http://<your-collector-host>:4317\" $0" >&2
    exit 1
fi
ENV_MARKER_START="# >>> telemetry-env-vars >>>"
ENV_MARKER_END="# <<< telemetry-env-vars <<<"
DIRENV_MARKER_START="# >>> telemetry-direnv-hook >>>"
DIRENV_MARKER_END="# <<< telemetry-direnv-hook <<<"

ENV_BLOCK="${ENV_MARKER_START}
export CLAUDE_CODE_ENABLE_TELEMETRY=1
export GEMINI_TELEMETRY_ENABLED=true
export GEMINI_TELEMETRY_USE_COLLECTOR=true
export OTEL_METRICS_EXPORTER=otlp
export OTEL_LOGS_EXPORTER=otlp
export OTEL_EXPORTER_OTLP_PROTOCOL=grpc
export OTEL_EXPORTER_OTLP_ENDPOINT=${OTEL_ENDPOINT}
${ENV_MARKER_END}"

# ------------------------------------------------------------
# Helpers
# ------------------------------------------------------------

upsert_block() {
    local file="$1" block="$2" sm="$3" em="$4"
    [[ -f "$file" ]] || touch "$file"
    if grep -qF "$sm" "$file" 2>/dev/null; then
        awk -v new_block="$block" -v sm="$sm" -v em="$em" \
            'BEGIN { in_block=0; printed=0 }
             $0 == sm { in_block=1; if (!printed) { print new_block; printed=1 }; next }
             in_block && $0 == em { in_block=0; next }
             !in_block { print }' \
            "$file" > "${file}.tmp" && mv "${file}.tmp" "$file"
    else
        { echo; echo "$block"; } >> "$file"
    fi
}

rc_targets() {
    local targets=()
    [[ -f "$HOME/.bashrc" ]] && targets+=("$HOME/.bashrc")
    [[ -f "$HOME/.zshrc"  ]] && targets+=("$HOME/.zshrc")
    if [[ ${#targets[@]} -eq 0 ]]; then
        local shell_name
        shell_name=$(basename "${SHELL:-bash}")
        targets+=("$HOME/.${shell_name}rc")
    fi
    printf '%s\n' "${targets[@]}"
}

# ------------------------------------------------------------
# Banner
# ------------------------------------------------------------
echo
echo "============================================================"
echo " Telemetry Setup"
echo "============================================================"
echo

# ------------------------------------------------------------
# 1. Set persistent environment variables
# ------------------------------------------------------------
echo "[1/3] Writing environment variables..."

targets=()
while IFS= read -r line; do [[ -n "$line" ]] && targets+=("$line"); done < <(rc_targets)

for rc in "${targets[@]}"; do
    upsert_block "$rc" "$ENV_BLOCK" "$ENV_MARKER_START" "$ENV_MARKER_END"
    echo "    Written to: $rc"
done

# ------------------------------------------------------------
# 2. Install direnv
# ------------------------------------------------------------
echo
echo "[2/3] Installing direnv..."

if command -v direnv &>/dev/null; then
    echo "    direnv already installed: $(command -v direnv)"
else
    if [[ "$(uname -s)" == "Darwin" ]]; then
        if ! command -v brew &>/dev/null; then
            echo "    ERROR: Homebrew not found. Install it from https://brew.sh then re-run this script."
            exit 1
        fi
        brew install direnv
    elif command -v apt-get &>/dev/null; then
        sudo apt-get install -y direnv
    elif command -v dnf &>/dev/null; then
        sudo dnf install -y direnv
    elif command -v yum &>/dev/null; then
        sudo yum install -y direnv
    elif command -v pacman &>/dev/null; then
        sudo pacman -S --noconfirm direnv
    else
        echo "    ERROR: No supported package manager found (apt, dnf, yum, pacman, brew)."
        echo "    Install direnv manually from https://direnv.net/docs/installation.html then re-run."
        exit 1
    fi
    echo "    direnv installed."
fi

echo
echo "    Adding direnv shell hook..."

for rc in "${targets[@]}"; do
    case "$rc" in
        *zshrc)  hook_line='eval "$(direnv hook zsh)"'  ;;
        *)       hook_line='eval "$(direnv hook bash)"' ;;
    esac
    direnv_block="${DIRENV_MARKER_START}
${hook_line}
${DIRENV_MARKER_END}"
    upsert_block "$rc" "$direnv_block" "$DIRENV_MARKER_START" "$DIRENV_MARKER_END"
    echo "    Hook written to: $rc"
done

# ------------------------------------------------------------
# 3. Done
# ------------------------------------------------------------
echo
echo "[3/3] Setup complete."
echo
echo " Next steps:"
echo "   1. Reload your shell:"
echo "        source ~/.bashrc   # or ~/.zshrc"
echo "      or open a new terminal window."
echo
echo "   2. In each repo, run once to allow direnv to load the .envrc:"
echo "        cd /path/to/repo"
echo "        direnv allow"
echo "      direnv will then reload automatically on every subsequent cd."
echo
echo "   3. Verify (from inside a repo directory):"
echo "        echo \$OTEL_RESOURCE_ATTRIBUTES      # should show  project=<repo-name>"
echo "        echo \$CLAUDE_CODE_ENABLE_TELEMETRY  # should show  1"
echo "        echo \$OTEL_EXPORTER_OTLP_ENDPOINT   # should show  ${OTEL_ENDPOINT}"
echo
echo "   If any value is missing, do not proceed — flag it for debugging."
echo
