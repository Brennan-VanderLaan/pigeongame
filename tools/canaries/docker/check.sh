#!/usr/bin/env bash
# Docker canary check

set -euo pipefail

check_docker() {
    if command -v docker >/dev/null 2>&1; then
        return 0
    else
        return 1
    fi
}

get_docker_version() {
    if command -v docker >/dev/null 2>&1; then
        docker --version 2>/dev/null | grep -oE '[0-9]+\.[0-9]+(\.[0-9]+)*' | head -1 || \
        echo "unknown"
    else
        echo "unknown"
    fi
}

provide_guidance() {
    local os="$1"
    
    echo "Installation guidance for Docker:"
    
    case "$os" in
        "linux")
            echo "  • Ubuntu/Debian: sudo apt-get install docker.io"
            echo "  • Or install Docker Engine: https://docs.docker.com/engine/install/"
            echo "  • Don't forget to add your user to docker group: sudo usermod -aG docker \$USER"
            ;;
        "macos")
            echo "  • Docker Desktop: https://www.docker.com/products/docker-desktop/"
            echo "  • Homebrew: brew install --cask docker"
            ;;
        "windows")
            echo "  • Docker Desktop: https://www.docker.com/products/docker-desktop/"
            echo "  • Chocolatey: choco install docker-desktop"
            ;;
        *)
            echo "  • Download from: https://docs.docker.com/get-docker/"
            ;;
    esac
}

if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    check_docker
fi