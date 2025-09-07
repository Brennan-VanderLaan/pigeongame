# k9s Canary Check

This directory contains the canary check for [k9s](https://k9scli.io/), a terminal-based UI for managing Kubernetes clusters.

## What it does

k9s provides a terminal-based user interface for interacting with Kubernetes clusters. It offers a convenient way to observe and manage your Kubernetes resources with real-time updates, resource navigation, and cluster monitoring capabilities. Most of the documentation in the future will reference debugging using k9s or kubectl.

## Check script

The `check.sh` script verifies that `k9s` command is available in the system PATH and provides installation guidance if not found.