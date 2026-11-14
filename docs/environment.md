# Phase 1 environment inspection

Observed 14 November 2026 (Asia/Calcutta). Workspace initially empty; no existing
Git repository or project instructions were found in the workspace or its parent.

| Check | Observed result |
| --- | --- |
| Python | 3.10.9 |
| Git | 2.51.1.windows.1 |
| Docker CLI / engine | 29.8.2 / 29.8.2 |
| Docker Compose | v5.5.1 |
| WSL | 3.0.5.0; kernel 6.1.58.1-1 |
| Windows version from WSL | 10.0.26200.8037 |
| Physical RAM | 16,989,736,960 bytes (about 15.8 GiB) |
| Logical processors | 16 |
| WSL distributions | docker-desktop, version 2, reported Stopped |
| Real datasets | Both absent |

Docker engine answered a version query, but that does not establish usable container
capacity. The WSL distribution state and engine response are separate observations.
No containers were started. Available RAM and Docker/WSL memory allocation remain unverified.
The OS caption/free-memory query did not render useful values in the combined output.

## Commands and what they mean

Run in PowerShell. These inspect the machine without installing software:

```powershell
Get-ChildItem -Force
git status --short
python --version
git --version
docker --version
docker compose version
wsl --version
Get-CimInstance Win32_ComputerSystem | Select-Object TotalPhysicalMemory,NumberOfLogicalProcessors
Get-CimInstance Win32_OperatingSystem | Select-Object Caption,Version,FreePhysicalMemory
docker info --format '{{json .ServerVersion}}'
wsl --list --verbose
```

`Get-ChildItem` lists files, including hidden files. `git status` checks whether this
folder is a repository (initially it was not). The version commands identify installed
clients. CIM reads hardware/OS details, Docker info checks engine reachability, and
the last command lists WSL distributions. Sandbox access initially blocked CIM,
Docker engine and WSL enumeration; the approved read-only retry retrieved hardware,
engine and distribution information.

Airbyte currently recommends at least 4 CPUs and 8 GB for best performance:
https://docs.airbyte.com/platform/using-airbyte/getting-started/oss-quickstart
This is not a guarantee that Airbyte and Airflow fit concurrently. Inspect Docker Desktop
resource settings before installation, and plan sequential workloads if needed.

## Next-phase blockers

Acquire and inspect the two datasets; record their provenance. Select a connector-accessible
file location. Then obtain approval for Phase 2, choose a GCP project, region and authentication
method, and discuss billing before any paid action. No cloud credentials are needed now.
