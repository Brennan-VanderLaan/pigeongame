# kubectl Canary Check

This directory contains the canary check for [kubectl](https://kubernetes.io/docs/reference/kubectl/), the Kubernetes command-line tool.

## What it does

kubectl is the primary command-line interface for interacting with Kubernetes clusters. It allows you to deploy applications, inspect and manage cluster resources, and view logs.

It's your swiss-army-knife for talking to kubernetes clusters and viewing or modifying state.

## Check script

The `check.sh` script verifies that `kubectl` command is available in the system PATH and provides installation guidance if not found.