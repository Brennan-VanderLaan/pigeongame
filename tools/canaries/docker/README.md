# Docker Canary Check

This directory contains the canary check for [Docker](https://www.docker.com/), a containerization platform.

## What it does

Docker is a platform for developing, shipping, and running applications in containers. It provides containerization technology that packages applications and their dependencies into portable containers that can run consistently across different environments. We abuse it to get talos up and running locally. 

## Check script

The `check.sh` script verifies that `docker` command is available in the system PATH and provides installation guidance if not found.