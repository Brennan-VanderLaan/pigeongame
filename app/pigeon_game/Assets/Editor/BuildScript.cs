using UnityEditor;
using UnityEngine;
using System;
using System.Linq;

/// <summary>
/// Build script for Bazel integration.
/// Provides static methods that can be called from command line builds.
/// </summary>
public class BuildScript
{
    private static string[] GetScenes()
    {
        return EditorBuildSettings.scenes
            .Where(scene => scene.enabled)
            .Select(scene => scene.path)
            .ToArray();
    }

    private static void PerformBuild(BuildTarget target, string outputPath, BuildOptions options = BuildOptions.None)
    {
        var scenes = GetScenes();

        if (scenes.Length == 0)
        {
            Debug.LogError("No scenes found in build settings!");
            EditorApplication.Exit(1);
            return;
        }

        Debug.Log($"Building for {target}...");
        Debug.Log($"Output path: {outputPath}");
        Debug.Log($"Scenes: {string.Join(", ", scenes)}");

        var report = BuildPipeline.BuildPlayer(scenes, outputPath, target, options);

        if (report.summary.result == UnityEditor.Build.Reporting.BuildResult.Succeeded)
        {
            Debug.Log($"Build succeeded: {report.summary.totalSize} bytes");
            EditorApplication.Exit(0);
        }
        else
        {
            Debug.LogError($"Build failed: {report.summary.result}");
            EditorApplication.Exit(1);
        }
    }

    /// <summary>
    /// Generic build method - detects platform and builds accordingly.
    /// Can be overridden with -buildTarget command line argument.
    /// </summary>
    [MenuItem("Build/Build Current Platform")]
    public static void Build()
    {
        var target = EditorUserBuildSettings.activeBuildTarget;
        var extension = GetExecutableExtension(target);
        var platformName = GetPlatformName(target);
        var outputPath = $"Builds/{platformName}/Game{extension}";

        PerformBuild(target, outputPath);
    }

    /// <summary>
    /// Build for Windows (64-bit).
    /// </summary>
    [MenuItem("Build/Build Windows")]
    public static void BuildWindows()
    {
        PerformBuild(BuildTarget.StandaloneWindows64, "Builds/Windows/Game.exe");
    }

    /// <summary>
    /// Build for Linux (64-bit).
    /// </summary>
    [MenuItem("Build/Build Linux")]
    public static void BuildLinux()
    {
        PerformBuild(BuildTarget.StandaloneLinux64, "Builds/Linux/Game");
    }

    /// <summary>
    /// Build for Windows with development options.
    /// </summary>
    [MenuItem("Build/Build Windows (Development)")]
    public static void BuildWindowsDevelopment()
    {
        PerformBuild(
            BuildTarget.StandaloneWindows64,
            "Builds/Windows-Dev/Game.exe",
            BuildOptions.Development | BuildOptions.AllowDebugging
        );
    }

    /// <summary>
    /// Build for Linux with development options.
    /// </summary>
    [MenuItem("Build/Build Linux (Development)")]
    public static void BuildLinuxDevelopment()
    {
        PerformBuild(
            BuildTarget.StandaloneLinux64,
            "Builds/Linux-Dev/Game",
            BuildOptions.Development | BuildOptions.AllowDebugging
        );
    }

    private static string GetExecutableExtension(BuildTarget target)
    {
        switch (target)
        {
            case BuildTarget.StandaloneWindows:
            case BuildTarget.StandaloneWindows64:
                return ".exe";
            case BuildTarget.StandaloneLinux64:
                return "";
            default:
                return "";
        }
    }

    private static string GetPlatformName(BuildTarget target)
    {
        switch (target)
        {
            case BuildTarget.StandaloneWindows:
            case BuildTarget.StandaloneWindows64:
                return "Windows";
            case BuildTarget.StandaloneLinux64:
                return "Linux";
            default:
                return target.ToString();
        }
    }
}
