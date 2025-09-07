# talosctl Canary Check

This directory contains the canary check for [talosctl](https://www.talos.dev/), the command-line tool for Talos Linux.

## What it does

talosctl is the CLI tool for managing Talos Linux, a modern OS designed for Kubernetes. It provides secure, immutable, and minimal Linux distribution built specifically for running Kubernetes clusters.

If you bypass the way talosctl brings up a cluster and run the images raw by hand, you can do wild things with dynamic clustering.

## Check script

The `check.sh` script verifies that `talosctl` command is available in the system PATH and provides installation guidance if not found.