#!/usr/bin/env bash
# Dependency checker script - checks for required tools and provides installation guidance
# Designed to be portable across Unix-like systems and Windows (via MSYS2/Git Bash)

set -euo pipefail

# Color codes for output (with fallback for systems that don't support them)
if [[ -t 1 ]] && command -v tput >/dev/null 2>&1; then
    RED=$(tput setaf 1)
    GREEN=$(tput setaf 2)
    YELLOW=$(tput setaf 3)
    BLUE=$(tput setaf 4)
    RESET=$(tput sgr0)
else
    RED=""
    GREEN=""
    YELLOW=""
    BLUE=""
    RESET=""
fi

# Track overall status
MISSING_DEPS=0

# Function to detect OS for installation guidance
detect_os() {
    case "$(uname -s)" in
        Linux*)     echo "linux" ;;
        Darwin*)    echo "macos" ;;
        CYGWIN*)    echo "windows" ;;
        MINGW*)     echo "windows" ;;
        MSYS*)      echo "windows" ;;
        *)          echo "unknown" ;;
    esac
}

# Function to check if a command exists
check_command() {
    local cmd="$1"
    local display_name="${2:-$cmd}"
    
    if command -v "$cmd" >/dev/null 2>&1; then
        echo "${GREEN}✓${RESET} $display_name is available"
        return 0
    else
        echo "${RED}✗${RESET} $display_name is not found"
        return 1
    fi
}

# Function to provide installation guidance
provide_guidance() {
    local tool="$1"
    local os="$2"
    
    echo "${YELLOW}Installation guidance for $tool:${RESET}"
    
    case "$tool" in
        "bazel")
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
                    echo "  • Try to use bazelisk - it will make your life easier"
                    echo "  • Download from: https://github.com/bazelbuild/bazel/releases"
                    ;;
            esac
            ;;
        "tofu")
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
            ;;
        *)
            echo "  • Please check the official documentation for $tool"
            ;;
    esac
    echo ""
}

# Main dependency checking function
check_dependencies() {
    local os
    os=$(detect_os)
    
    echo "${BLUE}Checking dependencies...${RESET}"
    echo ""
    
    # Define dependencies to check
    # Format: "command:display_name" or just "command" if they're the same
    local deps=(
        "bazel"
        "tofu:OpenTofu"
    )
    
    for dep in "${deps[@]}"; do
        IFS=':' read -r cmd display_name <<< "$dep"
        display_name="${display_name:-$cmd}"
        
        if ! check_command "$cmd" "$display_name"; then
            ((MISSING_DEPS++))
            provide_guidance "$cmd" "$os"
        fi
    done
    
    echo ""
    if [[ $MISSING_DEPS -eq 0 ]]; then
        echo "${GREEN}✓ All dependencies are satisfied!${RESET}"
        return 0
    else
        echo "${RED}✗ $MISSING_DEPS dependencies are missing${RESET}"
        return 1
    fi
}

# Function to add new dependency checks (for future expansion)
add_dependency_check() {
    local cmd="$1"
    local display_name="${2:-$cmd}"
    
    echo "# To add a new dependency check, add it to the deps array in check_dependencies()"
    echo "# Example: deps+=(\"$cmd:$display_name\")"
}

# Show usage information
show_usage() {
    echo "Usage: $0 [options]"
    echo ""
    echo "Options:"
    echo "  -h, --help     Show this help message"
    echo "  -q, --quiet    Suppress informational output"
    echo ""
    echo "This script checks for required dependencies and provides installation guidance."
    echo "Exit codes:"
    echo "  0 - All dependencies satisfied"
    echo "  1 - One or more dependencies missing"
}

# Parse command line arguments
QUIET=false
while [[ $# -gt 0 ]]; do
    case $1 in
        -h|--help)
            show_usage
            exit 0
            ;;
        -q|--quiet)
            QUIET=true
            shift
            ;;
        *)
            echo "Unknown option: $1" >&2
            show_usage >&2
            exit 1
            ;;
    esac
done

# Main execution
if [[ "$QUIET" == "false" ]]; then
    check_dependencies
else
    check_dependencies >/dev/null 2>&1
fi

