"""Bazel module extension for Unity toolchain."""

load(":defs.bzl", "unity_repository")

def _unity_extension_impl(module_ctx):
    """Extension implementation that sets up the Unity toolchain."""

    # Create the Unity toolchain repository
    unity_repository(name = "unity_toolchain")

    return module_ctx.extension_metadata(
        root_module_direct_deps = ["unity_toolchain"],
        root_module_direct_dev_deps = [],
    )

unity = module_extension(
    implementation = _unity_extension_impl,
)
