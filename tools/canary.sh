#!/usr/bin/env bash
# Dependency checker script - checks for required tools and provides installation guidance
# Designed to be portable across Unix-like systems and Windows (via MSYS2/Git Bash)

set -euo pipefail


# Show usage information
show_usage() {
    echo "Usage: $0 [options]"
    echo ""
    echo "Options:"
    echo "  -h, --help              Show this help message"
    echo "  -q, --quiet             Suppress informational output"
    echo "  -v, --versions          Show version information for available tools"
    echo "  --add-canary TOOLNAME   Create a new canary check for the specified tool"
    echo ""
    echo "This script checks for required dependencies and provides installation guidance."
    echo "Dependencies are automatically discovered from tools/canaries/ directory."
    echo ""
    echo "Exit codes:"
    echo "  0 - All dependencies satisfied (or canary successfully created)"
    echo "  1 - One or more dependencies missing (or error creating canary)"
}

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

# Function to get version from tool canary script
get_tool_version() {
    local tool="$1"
    local canary_script="tools/canaries/$tool/check.sh"
    
    if [[ ! -f "$canary_script" ]]; then
        echo "unknown"
        return 1
    fi
    
    # Source the script and call get_version function if it exists
    (
        source "$canary_script" 2>/dev/null
        if declare -f "get_${tool}_version" >/dev/null 2>&1; then
            "get_${tool}_version" 2>/dev/null || echo "unknown"
        else
            echo "unknown"
        fi
    )
}

# Function to run tool-specific canary checks
run_canary_check() {
    local tool="$1"
    local show_version="${2:-false}"
    local canary_script="tools/canaries/$tool/check.sh"
    
    if [[ ! -f "$canary_script" ]]; then
        echo "${RED}✗${RESET} Canary script not found: $canary_script"
        return 1
    fi
    
    # Execute the check script directly
    if "$canary_script"; then
        if [[ "$show_version" == "true" ]]; then
            local version
            version=$(get_tool_version "$tool")
            echo "${GREEN}✓${RESET} $tool is available (version: $version)"
        else
            echo "${GREEN}✓${RESET} $tool is available"
        fi
        return 0
    else
        echo "${RED}✗${RESET} $tool is not found"
        # Source the script temporarily to get access to the guidance function
        (
            source "$canary_script"
            echo "${YELLOW}Installation guidance for $tool:${RESET}"
            provide_guidance "$(detect_os)"
        )
        echo ""
        return 1
    fi
}

# Function to auto-discover tools from canaries directory
discover_tools() {
    local canaries_dir="tools/canaries"
    local tools=()
    
    if [[ ! -d "$canaries_dir" ]]; then
        echo "${RED}✗${RESET} Canaries directory not found: $canaries_dir"
        return 1
    fi
    
    # Find all directories in canaries/ that contain a check.sh script
    for tool_dir in "$canaries_dir"/*; do
        if [[ -d "$tool_dir" && -f "$tool_dir/check.sh" ]]; then
            local tool_name=$(basename "$tool_dir")
            tools+=("$tool_name")
        fi
    done
    
    # Sort tools alphabetically for consistent output
    IFS=$'\n' tools=($(sort <<<"${tools[*]}"))
    unset IFS
    
    printf '%s\n' "${tools[@]}"
}

# Main dependency checking function
check_dependencies() {
    local show_versions="${1:-false}"
    echo "${BLUE}Checking dependencies...${RESET}"
    echo ""
    
    # Auto-discover tools from canaries directory
    local tools
    mapfile -t tools < <(discover_tools)
    
    if [[ ${#tools[@]} -eq 0 ]]; then
        echo "${YELLOW}No canary checks found in tools/canaries/${RESET}"
        return 0
    fi
    
    for tool in "${tools[@]}"; do
        if ! run_canary_check "$tool" "$show_versions"; then
            ((MISSING_DEPS++))
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

# Function to process template file by replacing placeholders
process_template() {
    local template_file="$1"
    local tool="$2"
    local output_file="$3"
    
    if [[ ! -f "$template_file" ]]; then
        echo "${RED}Error: Template file not found: $template_file${RESET}" >&2
        return 1
    fi
    
    # Replace {{TOOL}} placeholder with actual tool name
    sed "s/{{TOOL}}/$tool/g" "$template_file" > "$output_file"
}

# Function to create a new canary check
create_canary_check() {
    local tool="$1"
    local canary_dir="tools/canaries/$tool"
    local template_dir="tools/canaries.template"
    
    if [[ -z "$tool" ]]; then
        echo "${RED}Error: Tool name is required${RESET}" >&2
        echo "Usage: $0 --add-canary TOOLNAME" >&2
        return 1
    fi
    
    # Validate tool name (alphanumeric, hyphens, underscores only)
    if [[ ! "$tool" =~ ^[a-zA-Z0-9_-]+$ ]]; then
        echo "${RED}Error: Invalid tool name '$tool'. Use only alphanumeric characters, hyphens, and underscores.${RESET}" >&2
        return 1
    fi
    
    # Check if template directory exists
    if [[ ! -d "$template_dir" ]]; then
        echo "${RED}Error: Template directory not found: $template_dir${RESET}" >&2
        return 1
    fi
    
    if [[ -d "$canary_dir" ]]; then
        echo "${YELLOW}Warning: Canary check for '$tool' already exists at $canary_dir${RESET}"
        echo "Overwrite? (y/N): "
        read -r response
        if [[ ! "$response" =~ ^[Yy]$ ]]; then
            echo "Cancelled."
            return 1
        fi
    fi
    
    # Create directory
    mkdir -p "$canary_dir"
    
    # Create check.sh from template
    echo "${BLUE}Creating $canary_dir/check.sh...${RESET}"
    if ! process_template "$template_dir/check.sh.template" "$tool" "$canary_dir/check.sh"; then
        echo "${RED}Error: Failed to create check.sh from template${RESET}" >&2
        return 1
    fi
    chmod +x "$canary_dir/check.sh"
    
    # Create README.md from template
    echo "${BLUE}Creating $canary_dir/README.md...${RESET}"
    if ! process_template "$template_dir/README.md.template" "$tool" "$canary_dir/README.md"; then
        echo "${RED}Error: Failed to create README.md from template${RESET}" >&2
        return 1
    fi
    
    echo "${GREEN}✓ Canary check for '$tool' created successfully!${RESET}"
    echo ""
    echo "Next steps:"
    echo "1. Edit $canary_dir/README.md to add proper description and documentation"
    echo "2. Update $canary_dir/check.sh if needed (default checks for '$tool' command in PATH)"
    echo "3. The canary will be automatically discovered on next run"
    
    return 0
}

# Parse command line arguments
QUIET=false
SHOW_VERSIONS=false
ADD_CANARY=""
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
        -v|--versions)
            SHOW_VERSIONS=true
            shift
            ;;
        --add-canary)
            if [[ -z "${2:-}" ]]; then
                echo "Error: --add-canary requires a tool name" >&2
                show_usage >&2
                exit 1
            fi
            ADD_CANARY="$2"
            shift 2
            ;;
        *)
            echo "Unknown option: $1" >&2
            show_usage >&2
            exit 1
            ;;
    esac
done

# Main execution
if [[ -n "$ADD_CANARY" ]]; then
    # Create new canary check
    create_canary_check "$ADD_CANARY"
else
    # Run dependency checks
    if [[ "$QUIET" == "false" ]]; then
        check_dependencies "$SHOW_VERSIONS"
    else
        check_dependencies "$SHOW_VERSIONS" >/dev/null 2>&1
    fi
fi

