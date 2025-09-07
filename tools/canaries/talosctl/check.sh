#!/usr/bin/env bash
# talosctl canary check

set -euo pipefail

check_talosctl() {
    if command -v talosctl >/dev/null 2>&1; then
        return 0
    else
        return 1
    fi
}

get_talosctl_version() {
    if command -v talosctl >/dev/null 2>&1; then
        talosctl version --client 2>/dev/null | grep -oE '[0-9]+\.[0-9]+(\.[0-9]+)*' | head -1 || \
        echo "unknown"
    else
        echo "unknown"
    fi
}

provide_guidance() {
    local os="$1"
    
    echo "Installation guidance for talosctl:"
    
    case "$os" in
        "linux")
            echo "  • curl -sL https://talos.dev/install | sh"
            echo "  • Or download from: https://github.com/siderolabs/talos/releases"
            ;;
        "macos")
            echo "  • Homebrew: brew install siderolabs/tap/talosctl"
            echo "  • Or curl -sL https://talos.dev/install | sh"
            echo "  • Or download from: https://github.com/siderolabs/talos/releases"
            ;;
        "windows")
            echo "  • Download from: https://github.com/siderolabs/talos/releases"
            echo "  • Or use WSL and install via curl"
            ;;
        *)
            echo "  • Download from: https://github.com/siderolabs/talos/releases"
            ;;
    esac
}

if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    check_talosctl
fi