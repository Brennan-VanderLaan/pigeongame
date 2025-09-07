# Bazel Canary Check

This directory contains the canary check for [Bazel](https://bazel.build/), a fast, scalable, multi-language and extensible build tool.

## What it does

Bazel is used for building and testing software projects. It supports multiple programming languages and can handle large codebases efficiently with advanced caching and parallelization - if you set
that up. It sounds great. It is - once it is fully set up. Until then, enjoy friction~

## Check script

The `check.sh` script verifies that `bazel` command is available in the system PATH and provides installation guidance if not found.