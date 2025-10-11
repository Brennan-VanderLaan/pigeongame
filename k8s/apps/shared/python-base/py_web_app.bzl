"""
Bazel macro for building Python web applications with OCI images

This macro simplifies the process of creating Python web applications by:
1. Installing dependencies from requirements.txt using uv
2. Creating a py_binary for the application
3. Building an OCI image with the application and its dependencies
"""

load("@rules_python//python:defs.bzl", "py_binary")
load("@rules_uv//uv:pip.bzl", "pip_compile")
load("@rules_uv//uv:venv.bzl", "create_venv")
load("@rules_oci//oci:defs.bzl", "oci_image", "oci_load")
load("@aspect_bazel_lib//lib:tar.bzl", "tar")

def py_web_app(
        name,
        srcs,
        main,
        requirements_txt = None,
        data = [],
        port = 8000,
        base_image = "@python_linux_amd64",
        deps = [],
        **kwargs):
    """
    Creates a Python web application with an OCI image.

    Args:
        name: Name of the application
        srcs: Python source files
        main: Main entry point file (e.g., "main.py")
        requirements_txt: Optional requirements.txt file for uv venv creation
        data: Additional data files to include (e.g., templates, static files)
        port: Port the application listens on (default: 8000)
        base_image: Base OCI image to use (default: python:3.13-slim)
        deps: Additional Python dependencies
        **kwargs: Additional arguments passed to py_binary
    """

    # If requirements_txt is provided, create venv target
    if requirements_txt:
        create_venv(
            name = name + "_venv",
            requirements_txt = requirements_txt,
        )

    # Create the Python binary
    py_binary(
        name = name,
        srcs = srcs,
        main = main,
        data = data,
        deps = deps,
        **kwargs
    )

    # Create a tar of the application and its dependencies
    tar(
        name = name + "_layer",
        srcs = [name] + data,
    )

    # Create OCI image (Linux only due to rules_oci Windows limitations)
    oci_image(
        name = name + "_image",
        base = base_image,
        tars = [":" + name + "_layer"],
        entrypoint = ["/usr/local/bin/python3", main],
        exposed_ports = [str(port) + "/tcp"],
        env = {
            "PYTHONUNBUFFERED": "1",
        },
        target_compatible_with = [
            "@platforms//os:linux",
        ],
    )

    # Create loader for loading into container runtimes (tarball via --output_groups=+tarball)
    oci_load(
        name = name + "_load",
        image = ":" + name + "_image",
        repo_tags = [name + ":latest"],
        target_compatible_with = [
            "@platforms//os:linux",
        ],
    )
