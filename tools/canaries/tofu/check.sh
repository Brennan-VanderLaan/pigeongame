#!/usr/bin/env bash
# OpenTofu canary check

set -euo pipefail

check_tofu() {
    if command -v tofu >/dev/null 2>&1; then
        return 0
    else
        return 1
    fi
}

get_tofu_version() {
    if command -v tofu >/dev/null 2>&1; then
        tofu --version 2>&1 | head -1 | grep -oE '[0-9]+\.[0-9]+(\.[0-9]+)*' | head -1
    else
        echo "unknown"
    fi
}

provide_guidance() {
    local os="$1"
    
    echo "Installation guidance for OpenTofu:"
    
    case "$os" in
        "linux")
            echo "  • Download from: https://github.com/opentofu/opentofu/releases"
            echo "  • Or use package manager if available"
            ;;
        "macos")
            echo "  • Homebrew: brew install opentofu"
            echo "  • Or download from: https://github.com/opentofu/opentofu/releases"
            ;;
        "windows")
            echo "  • Chocolatey: choco install opentofu"
            echo "  • Or download from: https://github.com/opentofu/opentofu/releases"
            ;;
        *)
            echo "  • Download from: https://github.com/opentofu/opentofu/releases"
            ;;
    esac
}

if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    check_tofu
fi