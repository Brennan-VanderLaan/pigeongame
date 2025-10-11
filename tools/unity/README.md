# Unity Bazel Rules

Cross-platform Bazel rules for building and running Unity projects on Windows and Linux.

## Setup

### 1. Configure Unity Path

The toolchain will auto-detect Unity installations in standard locations:

**Windows:**
- `C:/Program Files/Unity/Hub/Editor/*/Editor/Unity.exe`
- `C:/Program Files/Unity/Editor/Unity.exe`

**Linux:**
- `/opt/Unity/Editor/*/Editor/Unity`
- `~/Unity/Hub/Editor/*/Editor/Unity`
- `/usr/bin/unity-editor`

To use a specific Unity installation, set environment variables:

```bash
# Specify exact path
export UNITY_PATH="/path/to/Unity/Editor/Unity.exe"

# Or specify version (will search in standard locations)
export UNITY_VERSION="6000.2.2f1"
```

### 2. Add to MODULE.bazel

```python
# Unity toolchain
unity = use_extension("//tools/unity:extensions.bzl", "unity")
use_repo(unity, "unity_toolchain")
```

### 3. Create BUILD.bazel in Unity Project

```python
load("//tools/unity:unity.bzl", "unity_project")

unity_project(
    name = "my_game",
    project_path = ".",  # Path relative to BUILD file
    build_method = "BuildScript.Build",  # Unity C# method to call
)
```

## Usage

### Build the Game

Builds are tagged with `manual` so they don't run during `bazel build //...`:

```bash
# Build the game (uses platform-appropriate build target)
bazel build //app/Pigeon\ Game:pigeon_game

# Build output and logs are in bazel-bin/
```

### Run Unity Editor

Open the project in Unity Editor:

```bash
# Launch Unity Editor with the project
bazel run //app/Pigeon\ Game:pigeon_game_editor
```

## API Reference

### unity_project

Convenience macro that creates both build and run targets.

**Arguments:**
- `name`: Base name for targets (creates `name` for build, `name_editor` for editor)
- `project_path`: Path to Unity project directory (default: `"."`)
- `build_target`: Unity build target platform (auto-detected if not specified)
  - `"Win64"` - Windows 64-bit
  - `"Linux64"` - Linux 64-bit
- `build_method`: C# static method to execute (default: `"BuildScript.Build"`)
- `tags`: Additional Bazel tags

**Example:**
```python
unity_project(
    name = "my_game",
    project_path = ".",
    build_target = "Win64",  # Optional, auto-detected
    build_method = "BuildScript.BuildWindows",
)
```

Creates:
- `bazel build //:my_game` - Build the game
- `bazel run //:my_game_editor` - Launch in editor

### unity_build

Low-level rule for building Unity projects.

**Arguments:**
- `name`: Target name
- `project_root`: Label to a file in project root (e.g., `"ProjectSettings/ProjectVersion.txt"`)
- `srcs`: Source files (use `glob()` for Assets, ProjectSettings, etc.)
- `build_target`: Unity build target (`"Win64"`, `"Linux64"`, etc.)
- `build_method`: C# static method to execute
- `extra_unity_args`: Additional Unity command-line arguments

### unity_run

Low-level rule for launching Unity Editor.

**Arguments:**
- `name`: Target name
- `project_root`: Label to a file in project root
- `srcs`: Source files
- `scene`: Optional scene to open
- `extra_unity_args`: Additional Unity command-line arguments

## Build Script

A Unity Editor script is required to handle builds. See `Assets/Editor/BuildScript.cs` for an example that provides:

- `BuildScript.Build` - Auto-detect platform and build
- `BuildScript.BuildWindows` - Build for Windows
- `BuildScript.BuildLinux` - Build for Linux
- `BuildScript.BuildWindowsDevelopment` - Development build for Windows
- `BuildScript.BuildLinuxDevelopment` - Development build for Linux

## Cross-Platform Support

The rules automatically handle platform differences:

- **Unity executable detection**: Finds Unity in platform-specific locations
- **Path handling**: Converts paths appropriately for Windows/Linux
- **Build targets**: Defaults to correct platform if not specified
- **Wrapper scripts**: Uses `.bat` on Windows, `.sh` on Linux

## Troubleshooting

### Unity not found

Set `UNITY_PATH` environment variable:

```bash
export UNITY_PATH="/path/to/Unity.exe"
bazel clean --expunge  # Clear cache
bazel build //:target
```

### Build fails

Check the build log in `bazel-bin/`:

```bash
cat bazel-bin/app/Pigeon\ Game/pigeon_game.log
```

### No scenes in build

Make sure your scenes are added to Build Settings in Unity Editor (File > Build Settings).
