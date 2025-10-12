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
                # Try to find any matching version by reading directory
                # Extract the directory containing the wildcard (everything before /*)
                parent = path.split("/*")[0]
                parent_path = repository_ctx.path(parent)

                if parent_path.exists:
                    # List directories in parent and find Unity executable
                    # Use platform-appropriate directory listing command
                    list_cmd = ["cmd", "/c", "dir", "/b", parent] if is_windows else ["ls", "-1", parent]
                    result = repository_ctx.execute(list_cmd)
                    if result.return_code == 0:
                        for version_dir in result.stdout.strip().split("\n"):
                            if version_dir:
                                potential_path = "{}/{}/Editor/{}".format(parent, version_dir.strip(), unity_exe)
                                if repository_ctx.path(potential_path).exists:
                                    found_unity = potential_path
                                    break
                if found_unity:
                    break
            else:
                expanded_path = path.replace("~", repository_ctx.os.environ.get("HOME", ""))
                if repository_ctx.path(expanded_path).exists:
                    found_unity = expanded_path
                    break

    # Determine builtin packages directory and UPM server path
    builtin_packages_dir = ""
    upm_server_dir = ""
    if found_unity:
        # Unity builtin packages are at Editor/Data/Resources/PackageManager/BuiltInPackages
        # Unity path is like: .../Editor/Unity.exe, so we need to go up to Editor/ then to Data/
        editor_dir = found_unity.rsplit("/", 1)[0]  # Remove Unity.exe
        builtin_packages_dir = editor_dir + "/Data/Resources/PackageManager/BuiltInPackages"
        upm_server_dir = editor_dir + "/Data/Resources/PackageManager/Server"

    # Create BUILD file
    build_content = """# Unity toolchain
exports_files(["unity_wrapper.sh", "unity_wrapper.bat", "upm_wrapper.sh", "upm_wrapper.bat", "unity_info.bzl"])

filegroup(
    name = "unity_runtime",
    srcs = [],
    visibility = ["//visibility:public"],
)

filegroup(
    name = "upm_runtime",
    srcs = ["upm_wrapper.bat"] if {is_windows} else ["upm_wrapper.sh"],
    visibility = ["//visibility:public"],
)
""".format(is_windows = "True" if is_windows else "False")

    # Create Unity wrapper scripts
    if is_windows:
        wrapper_content = """@echo off
"{unity_path}" %*
""".format(unity_path = found_unity.replace("/", "\\") if found_unity else "")
        repository_ctx.file("unity_wrapper.bat", wrapper_content, executable = True)

    wrapper_sh_content = """#!/bin/bash
"{unity_path}" "$@"
""".format(unity_path = found_unity if found_unity else "/usr/bin/echo 'Unity not found'")
    repository_ctx.file("unity_wrapper.sh", wrapper_sh_content, executable = True)

    # Create UPM wrapper scripts
    if is_windows:
        upm_exe = upm_server_dir.replace("/", "\\") + "\\UnityPackageManager.exe" if upm_server_dir else ""
        upm_wrapper_content = """@echo off
"{upm_exe}" %*
""".format(upm_exe = upm_exe)
        repository_ctx.file("upm_wrapper.bat", upm_wrapper_content, executable = True)

    upm_wrapper_sh_content = """#!/bin/bash
"{upm_exe}" "$@"
""".format(upm_exe = upm_server_dir + "/UnityPackageManager" if upm_server_dir else "/usr/bin/echo 'UPM not found'")
    repository_ctx.file("upm_wrapper.sh", upm_wrapper_sh_content, executable = True)

    # Create info file
    info_content = """# Unity toolchain information
UNITY_PATH = "{unity_path}"
UNITY_FOUND = {found}
UNITY_OS = "{os}"
UNITY_BUILTIN_PACKAGES_DIR = "{builtin_packages_dir}"
UNITY_UPM_SERVER_DIR = "{upm_server_dir}"
""".format(
        unity_path = found_unity,
        found = "True" if found_unity else "False",
        os = "windows" if is_windows else "linux",
        builtin_packages_dir = builtin_packages_dir,
        upm_server_dir = upm_server_dir,
    )
    repository_ctx.file("unity_info.bzl", info_content)
    repository_ctx.file("BUILD.bazel", build_content)

    return None

unity_repository = repository_rule(
    implementation = _unity_repository_impl,
    environ = ["UNITY_PATH", "UNITY_VERSION", "HOME"],
    local = True,
)
