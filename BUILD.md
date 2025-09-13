# Build Documentation

## Overview

PigeonGame uses Bazel as its primary build system with remote caching and execution via BuildBuddy. The build is configured for cross-platform development with Linux-specific networking components.

## Quick Start

### Prerequisites
- Bazel 7.x (installed via Bazelisk recommended)
- Go 1.21+ (for local development)
- Docker (for container builds on Linux)

### Essential Commands
```bash
# Build all targets
bazel build //...

# Run performance test server
bazel run //k8s/apps/pisp-perf:server

# Run performance test client
bazel run //k8s/apps/pisp-perf:client

# Build CNI plugin (Linux only)
bazel build //k8s/cni:pigeon-cni-image
```

## Architecture

### Module System (bzlmod)
- **Module**: `pigeon-game@0.0.0`
- **Core Dependencies**: rules_go, rules_oci, aspect_bazel_lib
- **Go Dependencies**: External packages resolved from `//k8s/cni:go.mod`

### Build Configuration
- **Remote Cache**: `grpcs://pigeonisp.buildbuddy.io` (10m timeout)
- **Build Events**: Streamed to BuildBuddy for analysis
- **Workspace Status**: Git metadata injected via `tools/workspace_status.sh`
- **Performance Profiling**: Enabled with target labels and primary outputs

## Target Reference

### Root Package (`//`)
No build targets - BUILD files are manually maintained.

### CNI Package (`//k8s/cni`)
Platform: Linux only

| Target | Type | Description |
|--------|------|-------------|
| `pigeon-cni-lib` | go_library | CNI plugin implementation library |
| `pigeon-cni` | go_binary | CNI plugin binary |
| `pigeon-cni-image` | oci_image | Container image with CNI plugin |
| `pigeon-cni-layer` | genrule | Tarball layer for container image |
| `pigeon-cni-build` | alias | Platform-aware build target |
| `pigeon-cni-image-windows-notice` | genrule | Windows compatibility message |

**Dependencies**: 
- CNI libraries (`containernetworking/cni`)
- Netlink libraries (`vishvananda/netlink`, `vishvananda/netns`)

### Performance Testing (`//k8s/apps/pisp-perf`)
Platform: Cross-platform

| Target | Type | Description |
|--------|------|-------------|
| `pisp-perf-lib` | go_library | Core performance testing library |
| `pisp-perf` | go_binary | Main performance testing binary |
| `server` | alias | Server mode (default) |
| `run` | alias | Convenience alias for server |
| `client` | alias | Client mode with `-mode=client` flag |

## Platform Support

### Linux
Full support for all targets including CNI networking components.

### Windows  
Limited support:
- ✅ Performance testing tools (`pisp-perf`)
- ❌ CNI networking (Linux networking APIs required)
- ℹ️  CNI targets show helpful error messages on Windows

### Platform-Specific Builds
```bash
# Platform selection is automatic, but can be overridden:
bazel build --platforms=@platforms//os:linux //k8s/cni:pigeon-cni
```

## Development Workflows

### Adding New Targets
1. Follow naming convention: `component-name` (hyphens)
2. Libraries use `-lib` suffix: `component-name-lib`
3. Add convenience aliases for common operations: `run`, `build`, `test`
4. Use `target_compatible_with` for platform restrictions

### Dependency Management
BUILD files are manually maintained. External Go dependencies are automatically resolved from `k8s/cni/go.mod` via the `go_deps` extension.

### Container Images
All OCI images use Alpine Linux base and include:
- Minimal runtime environment
- Shell scripts for initialization
- Platform compatibility checks

## Build Performance

### Remote Caching
- **Endpoint**: `grpcs://pigeonisp.buildbuddy.io`
- **Timeout**: 10 minutes
- **Mode**: Read/write with local result upload disabled

### Profiling
Build profiles include:
- Target labels for attribution
- Primary output tracking
- Progress limited to 60s intervals

### Local Optimization
```bash
# Use local cache only
bazel build --remote_cache= //...

# Verbose build analysis
bazel build --profile=profile.json //...
```

## Configuration Files

### Core Configuration
- `.bazelrc` - Main configuration with modular imports
- `MODULE.bazel` - Bzlmod module definition and dependencies
- `tools/workspace_status.sh` - Git metadata injection

### Modular Configuration (`.bazelrc.d/`)
- `main.rc` - Workspace status integration  
- `performance.rc` - Profiling and progress settings
- `buildbuddy.rc` - Remote cache and build event streaming

## Troubleshooting

### Common Issues

**Build Failures on Windows**
- CNI targets are Linux-only by design
- Use WSL2 or Linux container for CNI development

**Remote Cache Timeouts**
- Check network connectivity to BuildBuddy
- Fallback: `bazel build --remote_cache= //...`

**Dependency Issues**
- BUILD files are manually maintained - check for syntax errors
- Check `go.mod` files are up to date

### Debug Commands
```bash
# Query all targets
bazel query //...

# Analyze target dependencies  
bazel query 'deps(//k8s/cni:pigeon-cni)'

# Check configuration
bazel info

# Verbose failure output
bazel build --verbose_failures //target
```

## Auto-Documentation Metadata

<!-- AUTODOC_METADATA
build_system: bazel
version: 7.x
remote_cache: pigeonisp.buildbuddy.io
platforms: [linux, windows]
languages: [go]
container_runtime: oci
-->

### Targets Schema
```yaml
packages:
  - name: "root"
    path: "//"
    targets: []
    
  - name: "cni"
    path: "//k8s/cni"
    platform_requirements: ["linux"]
    targets: ["pigeon-cni-lib", "pigeon-cni", "pigeon-cni-image"]
    
  - name: "pisp-perf" 
    path: "//k8s/apps/pisp-perf"
    platform_requirements: ["cross-platform"]
    targets: ["pisp-perf-lib", "pisp-perf", "server", "client", "run"]
```

---
*This documentation is structured for future integration with Sphinx, GitBook, or similar auto-documentation systems.*