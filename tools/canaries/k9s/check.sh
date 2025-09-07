#!/usr/bin/env bash
# k9s canary check

set -euo pipefail

check_k9s() {
    if command -v k9s >/dev/null 2>&1; then
        return 0
    else
        return 1
    fi
}

get_k9s_version() {
    if command -v k9s >/dev/null 2>&1; then
        k9s version 2>/dev/null | grep -oE '[0-9]+\.[0-9]+(\.[0-9]+)*' | head -1 || \
        echo "unknown"
    else
        echo "unknown"
    fi
}

provide_guidance() {
    local os="$1"
    
    echo "Installation guidance for k9s:"
    
    case "$os" in
        "linux")
            echo "  • Download from: https://github.com/derailed/k9s/releases"
            echo "  • Snap: sudo snap install k9s"
            echo "  • Or use package manager if available"
            ;;
        "macos")
            echo "  • Homebrew: brew install k9s"
            echo "  • Or download from: https://github.com/derailed/k9s/releases"
            ;;
        "windows")
            echo "  • Chocolatey: choco install k9s"
            echo "  • Scoop: scoop install k9s"
            echo "  • Or download from: https://github.com/derailed/k9s/releases"
            ;;
        *)
            echo "  • Download from: https://github.com/derailed/k9s/releases"
            ;;
    esac
}

if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    check_k9s
fi