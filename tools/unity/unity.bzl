"""Bazel rules and macros for building and running Unity projects."""

load("@unity_toolchain//:unity_info.bzl", "UNITY_BUILTIN_PACKAGES_DIR", "UNITY_FOUND", "UNITY_HUB_PATH", "UNITY_OS", "UNITY_PATH", "UNITY_UPM_SERVER_DIR")

def _get_unity_wrapper():
    """Returns the appropriate Unity wrapper script based on platform."""
    if UNITY_OS == "windows":
        return "@unity_toolchain//:unity_wrapper.bat"
    else:
        return "@unity_toolchain//:unity_wrapper.sh"

def _get_upm_wrapper():
    """Returns the appropriate UPM wrapper script based on platform."""
    if UNITY_OS == "windows":
        return "@unity_toolchain//:upm_wrapper.bat"
    else:
        return "@unity_toolchain//:upm_wrapper.sh"

def _unity_build_impl(ctx):
    """Implementation for unity_build rule."""

    # Determine Unity path based on version or use detected one
    unity_path = UNITY_PATH
    upm_server_dir = UNITY_UPM_SERVER_DIR

    # If unity_version is specified, construct the path
    if ctx.attr.unity_version:
        if UNITY_HUB_PATH:
            # Use the provided Unity Hub path
            if UNITY_OS == "windows":
                unity_path = "{}/{}/Editor/Unity.exe".format(UNITY_HUB_PATH, ctx.attr.unity_version)
                upm_server_dir = "{}/{}/Editor/Data/Resources/PackageManager/Server".format(UNITY_HUB_PATH, ctx.attr.unity_version)
            else:
                unity_path = "{}/{}/Editor/Unity".format(UNITY_HUB_PATH, ctx.attr.unity_version)
                upm_server_dir = "{}/{}/Editor/Data/Resources/PackageManager/Server".format(UNITY_HUB_PATH, ctx.attr.unity_version)
        else:
            # Fall back to default paths
            if UNITY_OS == "windows":
                unity_path = "C:/Program Files/Unity/Hub/Editor/{}/Editor/Unity.exe".format(ctx.attr.unity_version)
                upm_server_dir = "C:/Program Files/Unity/Hub/Editor/{}/Editor/Data/Resources/PackageManager/Server".format(ctx.attr.unity_version)
            else:
                unity_path = "/opt/Unity/Hub/Editor/{}/Editor/Unity".format(ctx.attr.unity_version)
                upm_server_dir = "/opt/Unity/Hub/Editor/{}/Editor/Data/Resources/PackageManager/Server".format(ctx.attr.unity_version)

    if not unity_path or not UNITY_FOUND and not ctx.attr.unity_version:
        fail("Unity not found. Set UNITY_PATH environment variable, install Unity in a standard location, or specify unity_version attribute.")

    # Get project root (parent of ProjectSettings directory)
    # project_root file is ProjectSettings/ProjectVersion.txt
    # dirname gives us ProjectSettings, we need to go up one more level
    project_root = ctx.file.project_root.dirname.rsplit("/", 1)[0]

    # Outputs
    output_dir = ctx.actions.declare_directory(ctx.label.name + "_output")
    build_log = ctx.actions.declare_file(ctx.label.name + ".log")

    # Determine build target
    build_target = ctx.attr.build_target
    if not build_target:
        build_target = "Win64" if UNITY_OS == "windows" else "Linux64"

    # Create platform-appropriate build script
    script_ext = ".bat" if UNITY_OS == "windows" else ".sh"
    script_file = ctx.actions.declare_file(ctx.label.name + "_build_script" + script_ext)

    # Create script content based on platform
    if UNITY_OS == "windows":
        script_content = """@echo off
setlocal enabledelayedexpansion

set "UNITY_EXE={unity_path}"
set "PROJECT_PATH_REL={project_path}"
set "BUILD_TARGET={build_target}"
set "BUILD_METHOD={build_method}"
set "OUTPUT_DIR={output_dir}"
set "BUILD_LOG={build_log}"

REM Set environment variables for Unity's build system
if not defined USERPROFILE set "USERPROFILE=%HOMEDRIVE%%HOMEPATH%"
if not defined LOCALAPPDATA set "LOCALAPPDATA=%USERPROFILE%\\AppData\\Local"
if not defined TEMP set "TEMP=%LOCALAPPDATA%\\Temp"
if not defined TMP set "TMP=%TEMP%"

REM Ensure Unity cache directories exist
if not exist "%LOCALAPPDATA%\\Unity" mkdir "%LOCALAPPDATA%\\Unity"
if not exist "%LOCALAPPDATA%\\Unity\\cache" mkdir "%LOCALAPPDATA%\\Unity\\cache"

REM Add Unity's UPM server and all its subdirectories to PATH so all UPM dependencies are accessible
set "PATH={upm_server_dir};{upm_server_dir}\\app;{upm_server_dir}\\bin;{upm_server_dir}\\node_modules;%PATH%"

REM Save the execroot directory for resolving relative paths
set "EXECROOT=%CD%"

REM Convert relative project path to absolute
pushd "%PROJECT_PATH_REL%" 2>nul
if errorlevel 1 (
    echo ERROR: Project path does not exist: %PROJECT_PATH_REL%
    exit /b 1
)
set "PROJECT_PATH=%CD%"
popd

echo ========================================
echo Unity Build
echo ========================================
echo Unity:   %UNITY_EXE%
echo Project: %PROJECT_PATH%
echo Target:  %BUILD_TARGET%
echo Method:  %BUILD_METHOD%
echo ========================================

REM Convert output paths to absolute (they're relative to execroot)
set "OUTPUT_DIR_ABS=%EXECROOT%\\%OUTPUT_DIR%"
set "BUILD_LOG_ABS=%EXECROOT%\\%BUILD_LOG%"

REM Make sure output directory exists
if not exist "%OUTPUT_DIR_ABS%" mkdir "%OUTPUT_DIR_ABS%"

REM Change to project directory before launching Unity so child processes spawn correctly
cd /d "%PROJECT_PATH%"

REM Pre-launch Unity Package Manager to work around IPC spawn issue
set "UPM_EXE={upm_server_dir}\\UnityPackageManager.exe"
set "UPM_IPC_NAME=Bazel-ipc"
set "UPM_IPC_PATH=Unity-%UPM_IPC_NAME%"

echo ========================================
echo Starting Unity Package Manager
echo ========================================
echo UPM: %UPM_EXE%
echo IPC Path: %UPM_IPC_PATH%
echo ========================================

REM Launch UPM directly
"%UPM_EXE%" -cl 5 -ipc -ipc-path "%UPM_IPC_PATH%"

REM Run Unity build
echo Starting Unity build...
"%UNITY_EXE%" ^
    -quit ^
    -batchmode ^
    -nographics ^
    -silent-crashes ^
    -accept-apiupdate ^
    -projectPath "%PROJECT_PATH%" ^
    -buildTarget "%BUILD_TARGET%" ^
    -executeMethod "%BUILD_METHOD%" ^
    -logFile "%BUILD_LOG_ABS%" ^
    -upmIpcPath "%UPM_IPC_NAME%" ^
    {extra_args}

set BUILD_EXIT_CODE=%ERRORLEVEL%

REM Kill UPM process
TASKKILL /F /IM UnityPackageManager.exe >nul 2>&1

if %BUILD_EXIT_CODE% neq 0 (
    echo ========================================
    echo Build FAILED with exit code %BUILD_EXIT_CODE%
    echo ========================================
    if exist "%BUILD_LOG_ABS%" (
        echo Build log:
        type "%BUILD_LOG_ABS%"
    )
    exit /b %BUILD_EXIT_CODE%
)

echo ========================================
echo Build completed successfully!
echo ========================================

REM Copy build artifacts to Bazel output directory
echo Copying build artifacts to output directory...

REM Try to find the build artifacts directory - Unity's BuildScript.cs uses GetPlatformName()
REM which returns "Windows" for Win64 builds, not the BuildTarget name
set "BUILD_ARTIFACTS_DIR="
if exist "%PROJECT_PATH%\\Builds\\%BUILD_TARGET%" (
    set "BUILD_ARTIFACTS_DIR=%PROJECT_PATH%\\Builds\\%BUILD_TARGET%"
) else if exist "%PROJECT_PATH%\\Builds\\Windows" (
    set "BUILD_ARTIFACTS_DIR=%PROJECT_PATH%\\Builds\\Windows"
) else if exist "%PROJECT_PATH%\\Builds\\Linux" (
    set "BUILD_ARTIFACTS_DIR=%PROJECT_PATH%\\Builds\\Linux"
)

if defined BUILD_ARTIFACTS_DIR (
    echo Copying from: %BUILD_ARTIFACTS_DIR%
    echo Copying to:   %OUTPUT_DIR_ABS%
    REM Use full path to xcopy to ensure it's available
    %SystemRoot%\\System32\\xcopy.exe "%BUILD_ARTIFACTS_DIR%" "%OUTPUT_DIR_ABS%" /E /I /Q /Y
    if errorlevel 1 (
        echo ERROR: Failed to copy build artifacts
        exit /b 1
    )
    echo Build artifacts copied successfully!
) else (
    echo ERROR: Could not find build artifacts in %PROJECT_PATH%\\Builds\\
    echo Expected one of: %BUILD_TARGET%, Windows, Linux
    exit /b 1
)

REM Create a marker file
echo Build completed at %DATE% %TIME% > "%OUTPUT_DIR_ABS%\\build_complete.txt"
""".format(
            unity_path = unity_path,
            project_path = project_root,
            build_target = build_target,
            build_method = ctx.attr.build_method,
            output_dir = output_dir.path,
            build_log = build_log.path,
            upm_server_dir = upm_server_dir,
            upm_wrapper = ctx.executable._upm_wrapper.path,
            extra_args = " ^\n    ".join(["-{}".format(arg) for arg in ctx.attr.extra_unity_args]),
        )
    else:
        script_content = """#!/bin/bash
set -e

# Create a temp bin directory and symlink uname for Unity
TEMP_BIN="$(pwd)/.unity_bin"
mkdir -p "$TEMP_BIN"
ln -sf /usr/bin/uname "$TEMP_BIN/uname"
export PATH="$TEMP_BIN:$PATH"

UNITY_EXE="{unity_path}"
PROJECT_PATH_REL="{project_path}"
BUILD_TARGET="{build_target}"
BUILD_METHOD="{build_method}"
OUTPUT_DIR="{output_dir}"
BUILD_LOG="{build_log}"

# Set environment variables for Unity's build system
export HOME="${{HOME:-${{USERPROFILE:-/tmp}}}}"
export TMPDIR="${{TMPDIR:-/tmp}}"

# Convert relative project path to absolute
if [ ! -d "$PROJECT_PATH_REL" ]; then
    echo "ERROR: Project path does not exist: $PROJECT_PATH_REL"
    exit 1
fi
PROJECT_PATH="$(cd "$PROJECT_PATH_REL" && pwd)"

echo "========================================"
echo "Unity Build"
echo "========================================"
echo "Unity:   $UNITY_EXE"
echo "Project: $PROJECT_PATH"
echo "Target:  $BUILD_TARGET"
echo "Method:  $BUILD_METHOD"
echo "========================================"

# Make sure output directory exists
mkdir -p "$OUTPUT_DIR"

# Run Unity build
echo "Starting Unity build..."
"$UNITY_EXE" \\
    -quit \\
    -batchmode \\
    -nographics \\
    -silent-crashes \\
    -accept-apiupdate \\
    -projectPath "$PROJECT_PATH" \\
    -buildTarget "$BUILD_TARGET" \\
    -executeMethod "$BUILD_METHOD" \\
    -logFile "$BUILD_LOG" \\
    {extra_args}

BUILD_EXIT_CODE=$?

if [ $BUILD_EXIT_CODE -ne 0 ]; then
    echo "========================================"
    echo "Build FAILED with exit code $BUILD_EXIT_CODE"
    echo "========================================"
    if [ -f "$BUILD_LOG" ]; then
        echo "Build log:"
        cat "$BUILD_LOG"
    fi
    exit $BUILD_EXIT_CODE
fi

echo "========================================"
echo "Build completed successfully!"
echo "========================================"

# Copy build artifacts to Bazel output directory
echo "Copying build artifacts to output directory..."

# Try to find the build artifacts directory - Unity's BuildScript.cs uses GetPlatformName()
# which returns "Windows" for Win64 builds or "Linux" for Linux64, not the BuildTarget name
BUILD_ARTIFACTS_DIR=""
if [ -d "$PROJECT_PATH/Builds/$BUILD_TARGET" ]; then
    BUILD_ARTIFACTS_DIR="$PROJECT_PATH/Builds/$BUILD_TARGET"
elif [ -d "$PROJECT_PATH/Builds/Windows" ]; then
    BUILD_ARTIFACTS_DIR="$PROJECT_PATH/Builds/Windows"
elif [ -d "$PROJECT_PATH/Builds/Linux" ]; then
    BUILD_ARTIFACTS_DIR="$PROJECT_PATH/Builds/Linux"
fi

if [ -n "$BUILD_ARTIFACTS_DIR" ]; then
    echo "Copying from: $BUILD_ARTIFACTS_DIR"
    echo "Copying to:   $OUTPUT_DIR"
    cp -r "$BUILD_ARTIFACTS_DIR"/* "$OUTPUT_DIR/"
    if [ $? -ne 0 ]; then
        echo "ERROR: Failed to copy build artifacts"
        exit 1
    fi
    echo "Build artifacts copied successfully!"
else
    echo "ERROR: Could not find build artifacts in $PROJECT_PATH/Builds/"
    echo "Expected one of: $BUILD_TARGET, Windows, Linux"
    exit 1
fi

# Create a marker file
echo "Build completed at $(date)" > "$OUTPUT_DIR/build_complete.txt"
""".format(
            unity_path = unity_path,
            project_path = project_root,
            build_target = build_target,
            build_method = ctx.attr.build_method,
            output_dir = output_dir.path,
            build_log = build_log.path,
            extra_args = " \\\n    ".join(["-{}".format(arg) for arg in ctx.attr.extra_unity_args]),
        )

    ctx.actions.write(
        output = script_file,
        content = script_content,
        is_executable = True,
    )

    # Execute build
    ctx.actions.run(
        inputs = ctx.files.srcs + [ctx.file.project_root],
        outputs = [output_dir, build_log],
        executable = script_file,
        tools = [ctx.executable._upm_wrapper],
        mnemonic = "UnityBuild",
        progress_message = "Building Unity project %s" % ctx.label.name,
        execution_requirements = {
            "no-sandbox": "1",  # Unity needs access to project files
        },
    )

    return [DefaultInfo(
        files = depset([output_dir, build_log]),
        runfiles = ctx.runfiles(files = [output_dir]),
    )]

unity_build = rule(
    implementation = _unity_build_impl,
    attrs = {
        "project_root": attr.label(
            doc = "Label pointing to a file in the Unity project root (e.g., ProjectSettings/ProjectVersion.txt)",
            allow_single_file = True,
            mandatory = True,
        ),
        "srcs": attr.label_list(
            doc = "Source files (Assets, ProjectSettings, etc.)",
            allow_files = True,
        ),
        "build_target": attr.string(
            doc = "Unity build target (Win64, Linux64, Android, etc.). Defaults to platform-specific.",
        ),
        "build_method": attr.string(
            doc = "Unity C# static method to execute for building",
            default = "BuildScript.Build",
        ),
        "unity_version": attr.string(
            doc = "Unity editor version to use (e.g., '6000.2.2f1'). If not specified, uses auto-detected Unity.",
        ),
        "extra_unity_args": attr.string_list(
            doc = "Additional arguments to pass to Unity",
            default = [],
        ),
        "_upm_wrapper": attr.label(
            default = Label(_get_upm_wrapper()),
            allow_single_file = True,
            executable = True,
            cfg = "exec",
        ),
    },
)

def _unity_run_impl(ctx):
    """Implementation for unity_run rule."""

    # Determine Unity path based on version or use detected one
    unity_path = UNITY_PATH

    # If unity_version is specified, construct the path
    if ctx.attr.unity_version:
        if UNITY_HUB_PATH:
            # Use the provided Unity Hub path
            if UNITY_OS == "windows":
                unity_path = "{}/{}/Editor/Unity.exe".format(UNITY_HUB_PATH, ctx.attr.unity_version)
            else:
                unity_path = "{}/{}/Editor/Unity".format(UNITY_HUB_PATH, ctx.attr.unity_version)
        else:
            # Fall back to default paths
            if UNITY_OS == "windows":
                unity_path = "C:/Program Files/Unity/Hub/Editor/{}/Editor/Unity.exe".format(ctx.attr.unity_version)
            else:
                unity_path = "/opt/Unity/Hub/Editor/{}/Editor/Unity".format(ctx.attr.unity_version)

    if not unity_path and not UNITY_FOUND and not ctx.attr.unity_version:
        fail("Unity not found. Set UNITY_PATH environment variable, install Unity in a standard location, or specify unity_version attribute.")

    # Get project root (parent of ProjectSettings directory)
    project_root = ctx.file.project_root.dirname.rsplit("/", 1)[0]

    # Create platform-appropriate launcher script
    launcher_ext = ".bat" if UNITY_OS == "windows" else ".sh"
    launcher = ctx.actions.declare_file(ctx.label.name + launcher_ext)

    scene_args = ""
    if ctx.attr.scene:
        scene_args = '-scene "{}"'.format(ctx.attr.scene)

    # Create script content based on platform
    if UNITY_OS == "windows":
        launcher_content = """@echo off

set "UNITY_EXE={unity_path}"
set "PROJECT_PATH_REL={project_path}"

REM Use BUILD_WORKING_DIRECTORY if set (bazel run), otherwise use current directory
if defined BUILD_WORKING_DIRECTORY (
    set "WORKSPACE_ROOT=%BUILD_WORKING_DIRECTORY%"
) else (
    set "WORKSPACE_ROOT=%CD%"
)

REM Convert relative project path to absolute
pushd "%WORKSPACE_ROOT%\\%PROJECT_PATH_REL%" 2>nul
if errorlevel 1 (
    echo ERROR: Project path does not exist: %WORKSPACE_ROOT%\\%PROJECT_PATH_REL%
    exit /b 1
)
set "PROJECT_PATH=%CD%"
popd

echo ========================================
echo Launching Unity Editor
echo ========================================
echo Unity:   %UNITY_EXE%
echo Project: %PROJECT_PATH%
echo ========================================

"%UNITY_EXE%" ^
    -projectPath "%PROJECT_PATH%" ^
    {scene_args} ^
    {extra_args}
""".format(
            unity_path = unity_path,
            project_path = project_root,
            scene_args = scene_args,
            extra_args = " ^\n    ".join(["-{}".format(arg) for arg in ctx.attr.extra_unity_args]),
        )
    else:
        launcher_content = """#!/bin/bash
UNITY_EXE="{unity_path}"
PROJECT_PATH_REL="{project_path}"

# Use BUILD_WORKING_DIRECTORY if set (bazel run), otherwise use current directory
if [ -n "$BUILD_WORKING_DIRECTORY" ]; then
    WORKSPACE_ROOT="$BUILD_WORKING_DIRECTORY"
else
    WORKSPACE_ROOT="$(pwd)"
fi

# Convert relative project path to absolute
FULL_PROJECT_PATH="$WORKSPACE_ROOT/$PROJECT_PATH_REL"
if [ ! -d "$FULL_PROJECT_PATH" ]; then
    echo "ERROR: Project path does not exist: $FULL_PROJECT_PATH"
    exit 1
fi
PROJECT_PATH="$(cd "$FULL_PROJECT_PATH" && pwd)"

echo "========================================"
echo "Launching Unity Editor"
echo "========================================"
echo "Unity:   $UNITY_EXE"
echo "Project: $PROJECT_PATH"
echo "========================================"

"$UNITY_EXE" \\
    -projectPath "$PROJECT_PATH" \\
    {scene_args} \\
    {extra_args}
""".format(
            unity_path = unity_path,
            project_path = project_root,
            scene_args = scene_args,
            extra_args = " \\\n    ".join(["-{}".format(arg) for arg in ctx.attr.extra_unity_args]),
        )

    ctx.actions.write(
        output = launcher,
        content = launcher_content,
        is_executable = True,
    )

    return [DefaultInfo(
        executable = launcher,
        runfiles = ctx.runfiles(files = ctx.files.srcs + [ctx.file.project_root]),
    )]

unity_run = rule(
    implementation = _unity_run_impl,
    executable = True,
    attrs = {
        "project_root": attr.label(
            doc = "Label pointing to a file in the Unity project root",
            allow_single_file = True,
            mandatory = True,
        ),
        "srcs": attr.label_list(
            doc = "Source files (Assets, ProjectSettings, etc.)",
            allow_files = True,
        ),
        "scene": attr.string(
            doc = "Scene to open (optional)",
        ),
        "unity_version": attr.string(
            doc = "Unity editor version to use (e.g., '6000.2.2f1'). If not specified, uses auto-detected Unity.",
        ),
        "extra_unity_args": attr.string_list(
            doc = "Additional arguments to pass to Unity",
            default = [],
        ),
    },
)

def _generate_package_references(project_path, packages):
    """Generate assembly reference arguments for Unity packages.

    Args:
        project_path: Path to Unity project
        packages: List of package identifiers (e.g., ["textmeshpro", "inputsystem", "ugui"])

    Returns:
        List of Unity command-line arguments for assembly references
    """
    if not packages:
        return []

    # Common package name mappings to their assembly DLL names
    package_dll_map = {
        "textmeshpro": ["Unity.TextMeshPro"],
        "inputsystem": ["Unity.InputSystem"],
        "ugui": ["UnityEngine.UI"],
        "ai.navigation": ["Unity.AI.Navigation"],
        "render-pipelines.universal": ["Unity.RenderPipelines.Universal.Runtime", "Unity.RenderPipelines.Core.Runtime"],
        "visualscripting": ["Unity.VisualScripting.Core", "Unity.VisualScripting.Flow"],
        "timeline": ["Unity.Timeline"],
    }

    args = []
    for pkg in packages:
        pkg_lower = pkg.lower().replace("com.unity.", "").replace("-", "")

        if pkg_lower in package_dll_map:
            for dll_name in package_dll_map[pkg_lower]:
                # Reference pre-compiled DLLs from Library/ScriptAssemblies
                dll_path = project_path + "/Library/ScriptAssemblies/" + dll_name + ".dll"
                args.append('referenceAssembly="{}"'.format(dll_path))

    return args

def unity_project(name, project_path = ".", build_target = None, build_method = "BuildScript.Build", unity_version = None, packages = [], tags = []):
    """Macro to create both build and run targets for a Unity project.

    This creates two targets:
    - `name`: Build target (manual tag, run with `bazel build //path/to:name`)
    - `name_editor`: Run target (run with `bazel run //path/to:name_editor`)

    Args:
        name: Base name for the targets
        project_path: Relative path to Unity project directory (default: current package)
        build_target: Unity build target (Win64, Linux64, etc.). Auto-detected if not specified.
        build_method: C# method to call for building
        unity_version: Unity editor version to use (e.g., '6000.2.2f1'). If not specified, uses auto-detected Unity.
        packages: List of Unity packages to reference (e.g., ["textmeshpro", "inputsystem"])
        tags: Additional tags to apply to targets
    """

    # Glob all Unity project files - include everything Unity needs
    srcs = native.glob([
        project_path + "/**/*",
    ], exclude = [
        # Exclude only truly temporary/cache files that would cause issues
        project_path + "/Temp/**",
        project_path + "/Logs/**",
        project_path + "/obj/**",
        project_path + "/Build/**",
        project_path + "/Builds/**",
        project_path + "/.vs/**",
        project_path + "/**/*.csproj",  # Generated project files
        project_path + "/**/*.sln",  # Generated solution files
    ], allow_empty = True)

    # Generate package assembly references
    package_refs = _generate_package_references(project_path, packages)

    # Build target
    unity_build(
        name = name,
        project_root = project_path + "/ProjectSettings/ProjectVersion.txt",
        srcs = srcs,
        build_target = build_target,
        build_method = build_method,
        unity_version = unity_version,
        extra_unity_args = package_refs,
        tags = ["manual"] + tags,
    )

    # Editor run target
    unity_run(
        name = name + "_editor",
        project_root = project_path + "/ProjectSettings/ProjectVersion.txt",
        srcs = srcs,
        unity_version = unity_version,
        tags = tags,
    )
