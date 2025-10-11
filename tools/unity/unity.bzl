"""Bazel rules and macros for building and running Unity projects."""

load("@unity_toolchain//:unity_info.bzl", "UNITY_FOUND", "UNITY_OS", "UNITY_PATH")

def _get_unity_wrapper():
    """Returns the appropriate Unity wrapper script based on platform."""
    if UNITY_OS == "windows":
        return "@unity_toolchain//:unity_wrapper.bat"
    else:
        return "@unity_toolchain//:unity_wrapper.sh"

def _unity_build_impl(ctx):
    """Implementation for unity_build rule."""
    if not UNITY_FOUND:
        fail("Unity not found. Set UNITY_PATH environment variable or install Unity in a standard location.")

    # Get project root
    project_root = ctx.file.project_root.dirname

    # Outputs
    output_dir = ctx.actions.declare_directory(ctx.label.name + "_output")
    build_log = ctx.actions.declare_file(ctx.label.name + ".log")

    # Determine build target
    build_target = ctx.attr.build_target
    if not build_target:
        build_target = "Win64" if UNITY_OS == "windows" else "Linux64"

    # Create build script
    script_file = ctx.actions.declare_file(ctx.label.name + "_build_script.sh")

    script_content = """#!/bin/bash
set -e

UNITY_EXE="{unity_path}"
PROJECT_PATH="{project_path}"
BUILD_TARGET="{build_target}"
BUILD_METHOD="{build_method}"
OUTPUT_DIR="{output_dir}"
BUILD_LOG="{build_log}"

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
"$UNITY_EXE" \\
    -quit \\
    -batchmode \\
    -nographics \\
    -silent-crashes \\
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

# Create a marker file
echo "Build completed at $(date)" > "$OUTPUT_DIR/build_complete.txt"
""".format(
        unity_path = UNITY_PATH,
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
        "extra_unity_args": attr.string_list(
            doc = "Additional arguments to pass to Unity",
            default = [],
        ),
    },
)

def _unity_run_impl(ctx):
    """Implementation for unity_run rule."""
    if not UNITY_FOUND:
        fail("Unity not found. Set UNITY_PATH environment variable or install Unity in a standard location.")

    project_root = ctx.file.project_root.dirname

    # Create launcher script
    launcher = ctx.actions.declare_file(ctx.label.name + ".sh")

    scene_args = ""
    if ctx.attr.scene:
        scene_args = '-scene "{}"'.format(ctx.attr.scene)

    launcher_content = """#!/bin/bash
UNITY_EXE="{unity_path}"
PROJECT_PATH="{project_path}"

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
        unity_path = UNITY_PATH,
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
        "extra_unity_args": attr.string_list(
            doc = "Additional arguments to pass to Unity",
            default = [],
        ),
    },
)

def unity_project(name, project_path = ".", build_target = None, build_method = "BuildScript.Build", tags = []):
    """Macro to create both build and run targets for a Unity project.

    This creates two targets:
    - `name`: Build target (manual tag, run with `bazel build //path/to:name`)
    - `name_editor`: Run target (run with `bazel run //path/to:name_editor`)

    Args:
        name: Base name for the targets
        project_path: Relative path to Unity project directory (default: current package)
        build_target: Unity build target (Win64, Linux64, etc.). Auto-detected if not specified.
        build_method: C# method to call for building
        tags: Additional tags to apply to targets
    """

    # Glob all Unity project files
    srcs = native.glob([
        project_path + "/Assets/**/*",
        project_path + "/ProjectSettings/**/*",
        project_path + "/Packages/**/*",
    ], exclude = [
        project_path + "/Library/**",
        project_path + "/.vs/**",
        project_path + "/Temp/**",
        project_path + "/Logs/**",
        project_path + "/obj/**",
        project_path + "/Build/**",
        project_path + "/Builds/**",
        "**/*.meta",  # Exclude meta files for performance
    ])

    # Build target
    unity_build(
        name = name,
        project_root = project_path + "/ProjectSettings/ProjectVersion.txt",
        srcs = srcs,
        build_target = build_target,
        build_method = build_method,
        tags = ["manual"] + tags,
    )

    # Editor run target
    unity_run(
        name = name + "_editor",
        project_root = project_path + "/ProjectSettings/ProjectVersion.txt",
        srcs = srcs,
        tags = tags,
    )
