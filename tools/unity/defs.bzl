"""Repository rule for detecting Unity installations on Windows and Linux."""

def _unity_repository_impl(repository_ctx):
    """Detects Unity installation and creates a repository with Unity toolchain info."""

    # Determine OS
    os_name = repository_ctx.os.name.lower()
    is_windows = "windows" in os_name
    is_linux = "linux" in os_name

    if not is_windows and not is_linux:
        fail("Unsupported OS: {}. Only Windows and Linux are supported.".format(os_name))

    # Check for user-provided Unity path
    unity_path = repository_ctx.os.environ.get("UNITY_PATH", "")
    unity_version = repository_ctx.os.environ.get("UNITY_VERSION", "")

    # Default search paths by platform
    search_paths = []
    unity_exe = ""

    if is_windows:
        unity_exe = "Unity.exe"
        if unity_version:
            search_paths.append("C:/Program Files/Unity/Hub/Editor/{}/Editor/Unity.exe".format(unity_version))
        search_paths.extend([
            "C:/Program Files/Unity/Hub/Editor/*/Editor/Unity.exe",
            "C:/Program Files/Unity/Editor/Unity.exe",
        ])
    elif is_linux:
        unity_exe = "Unity"
        if unity_version:
            search_paths.append("/opt/Unity/Editor/{}/Editor/Unity".format(unity_version))
            search_paths.append("~/Unity/Hub/Editor/{}/Editor/Unity".format(unity_version))
        search_paths.extend([
            "/opt/Unity/Editor/*/Editor/Unity",
            "~/Unity/Hub/Editor/*/Editor/Unity",
            "/usr/bin/unity-editor",
        ])

    # Try user-provided path first
    found_unity = ""
    if unity_path:
        if repository_ctx.path(unity_path).exists:
            found_unity = unity_path

    # Search for Unity in standard locations
    if not found_unity:
        for path in search_paths:
            # Handle glob patterns
            if "*" in path:
                # Try to find any matching version
                parent = path.rsplit("/", 2)[0]
                if repository_ctx.path(parent).exists:
                    # Read directory and find Unity
                    result = repository_ctx.execute(["bash", "-c", "ls -1d {} 2>/dev/null | head -1".format(path)])
                    if result.return_code == 0 and result.stdout.strip():
                        potential_path = result.stdout.strip()
                        if repository_ctx.path(potential_path).exists:
                            found_unity = potential_path
                            break
            else:
                expanded_path = path.replace("~", repository_ctx.os.environ.get("HOME", ""))
                if repository_ctx.path(expanded_path).exists:
                    found_unity = expanded_path
                    break

    # Create BUILD file
    build_content = """# Unity toolchain
exports_files(["unity_wrapper.sh", "unity_wrapper.bat", "unity_info.bzl"])

filegroup(
    name = "unity_runtime",
    srcs = [],
    visibility = ["//visibility:public"],
)
"""

    # Create wrapper scripts
    if is_windows:
        wrapper_content = """@echo off
"{unity_path}" %*
""".format(unity_path = found_unity.replace("/", "\\") if found_unity else "")
        repository_ctx.file("unity_wrapper.bat", wrapper_content, executable = True)

    wrapper_sh_content = """#!/bin/bash
"{unity_path}" "$@"
""".format(unity_path = found_unity if found_unity else "/usr/bin/echo 'Unity not found'")
    repository_ctx.file("unity_wrapper.sh", wrapper_sh_content, executable = True)

    # Create info file
    info_content = """# Unity toolchain information
UNITY_PATH = "{unity_path}"
UNITY_FOUND = {found}
UNITY_OS = "{os}"
""".format(
        unity_path = found_unity,
        found = "True" if found_unity else "False",
        os = "windows" if is_windows else "linux",
    )
    repository_ctx.file("unity_info.bzl", info_content)
    repository_ctx.file("BUILD.bazel", build_content)

    return None

unity_repository = repository_rule(
    implementation = _unity_repository_impl,
    environ = ["UNITY_PATH", "UNITY_VERSION", "HOME"],
    local = True,
)
