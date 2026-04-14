---
title: CLI Reference
---

# CLI Reference

## Commands

| Command | Description |
|---------|-------------|
| `neuropipe run` | Submit pipeline jobs to SLURM |
| `neuropipe check-outputs` | Inspect which subjects completed a task |
| `neuropipe detect-subjects` | Find subject IDs in a directory |
| `neuropipe list-tasks` | List all configured tasks |
| `neuropipe generate-config` | Generate a blank project config template |
| `neuropipe generate-checks` | Generate a blank results-check config template |
| `neuropipe merge-logs` | Manually merge JSONL logs into the SQLite database |
| `neuropipe force-rebuild` | Rebuild a fresh database from all JSONL logs, including archived |
| `neuropipe generate-report` | Generate a standalone HTML report from the job database |
| `neuropipe-gui` | Launch the web-based GUI |

---

::::{grid} 2
:::{card} neuropipe run
:link: run
All flags for submitting pipeline jobs — subjects, stages, dry-run, resume, wait.
:::
:::{card} Database Commands
:link: database-commands
`check-outputs`, `merge-logs`, `force-rebuild`, `generate-report`, and the database schema.
:::
:::{card} Utility Commands
:link: utility-commands
`detect-subjects`, `list-tasks`, `neuropipe-gui`, `generate-config`, `generate-checks`.
:::
::::
