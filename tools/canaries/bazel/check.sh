#!/usr/bin/env bash
# Bazel canary check

set -euo pipefail

check_bazel() {
    if command -v bazel >/dev/null 2>&1; then
        return 0
    else
        return 1
    fi
}

get_bazel_version() {
    if command -v bazel >/dev/null 2>&1; then
        bazel --version 2>&1 | head -1 | grep -oE '[0-9]+\.[0-9]+(\.[0-9]+)*' | head -1
    else
        echo "unknown"
    fi
}

provide_guidance() {
    local os="$1"
    
    echo "Installation guidance for Bazel:"
    
    case "$os" in
        "linux")
            echo "  • Ubuntu/Debian: sudo apt install bazel"
            echo "  • Or download from: https://github.com/bazelbuild/bazelisk/releases"
            ;;
        "macos")
            echo "  • Homebrew: brew install bazelisk"
            echo "  • Or download from: https://github.com/bazelbuild/bazelisk/releases"
            ;;
        "windows")
            echo "  • Chocolatey: choco install bazelisk"
            echo "  • Scoop: scoop install bazelisk"
            echo "  • Or download from: https://github.com/bazelbuild/bazelisk"
            ;;
        *)
            echo "  • Try to use bazelisk - it will make your life easier otherwise you can do it live"
            echo "  • Download from: https://github.com/bazelbuild/bazel/releases"
            ;;
    esac
}

if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    check_bazel
fi