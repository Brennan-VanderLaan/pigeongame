# OpenTofu Canary Check

This directory contains the canary check for [OpenTofu](https://opentofu.org/), an open-source infrastructure as code tool.

## What it does

OpenTofu is a community-driven fork of Terraform that provides infrastructure as code capabilities. It allows you to define, provision, and manage cloud infrastructure using declarative configuration files.

## Check script

The `check.sh` script verifies that `tofu` command is available in the system PATH and provides installation guidance if not found.