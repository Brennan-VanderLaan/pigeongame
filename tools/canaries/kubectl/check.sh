#!/usr/bin/env bash
# kubectl canary check

set -euo pipefail

check_kubectl() {
    if command -v kubectl >/dev/null 2>&1; then
        return 0
    else
        return 1
    fi
}

get_kubectl_version() {
    if command -v kubectl >/dev/null 2>&1; then
        kubectl version --client --short 2>/dev/null | grep -oE '[0-9]+\.[0-9]+(\.[0-9]+)*' | head -1 || \
        kubectl version --client 2>/dev/null | grep -oE '[0-9]+\.[0-9]+(\.[0-9]+)*' | head -1 || \
        echo "unknown"
    else
        echo "unknown"
    fi
}

provide_guidance() {
    local os="$1"
    
    echo "Installation guidance for kubectl:"
    
    case "$os" in
        "linux")
            echo "  • Ubuntu/Debian: sudo apt-get install kubectl"
            echo "  • Or curl -LO \"https://dl.k8s.io/release/\$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl\""
            ;;
        "macos")
            echo "  • Homebrew: brew install kubectl"
            echo "  • Or curl -LO \"https://dl.k8s.io/release/\$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/darwin/amd64/kubectl\""
            ;;
        "windows")
            echo "  • Chocolatey: choco install kubernetes-cli"
            echo "  • Scoop: scoop install kubectl"
            echo "  • Or download from: https://kubernetes.io/docs/tasks/tools/install-kubectl-windows/"
            ;;
        *)
            echo "  • Download from: https://kubernetes.io/docs/tasks/tools/"
            ;;
    esac
}

if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    check_kubectl
fi