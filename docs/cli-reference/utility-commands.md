---
title: Utility Commands
---

# Utility Commands

---

## `neuropipe detect-subjects`

Scans a directory for subject folders matching the given prefix.

```bash
# Print detected subjects to stdout
neuropipe detect-subjects /data/BIDS

# Save to a text file (comma-separated, one line)
neuropipe detect-subjects /data/BIDS --output subjects.txt

# With explicit prefix (default is "sub-")
neuropipe detect-subjects /data/raw --prefix "sub-" -o subjects.txt
```

The saved file can be passed directly to `--subjects` in `neuropipe run`:

```bash
neuropipe run --subjects subjects.txt ...
```

**Arguments / Options:**

| Argument/Option | Description |
|-----------------|-------------|
| `input_dir` | Directory to scan (positional, required) |
| `--output` / `-o` | Output file path — prints to stdout if omitted |
| `--prefix` / `-p` | Subject folder prefix to match (default: `sub-`) |

---

## `neuropipe list-tasks`

Lists all task names, scripts, and dependencies from `config.yaml`.

```bash
neuropipe list-tasks
```

---

## `neuropipe-gui`

Launches the web dashboard.

```bash
neuropipe-gui                 # default port 8050
neuropipe-gui --port 8051     # if 8050 is in use
```

Open `http://localhost:8050`. The GUI has three tabs:

| Tab | Purpose |
|-----|---------|
| **Analysis Control** | Select subjects, configure pipeline, execute/dry-run, generate command preview |
| **Project Config** | Create/edit project YAML configs and results-check YAMLs |
| **Job Monitor** | Query job database, read logs, track running jobs |

---

## `neuropipe generate-config`

Generate a blank project config template (`{project}_config.yaml`). Equivalent to clicking **Generate Template** in the GUI Project Config tab.

```bash
neuropipe generate-config branch

# Write to a custom directory
neuropipe generate-config branch --output-dir /scratch/my_project/config/project_config
```

**Arguments / Options:**

| | Description |
|---|-------------|
| `PROJECT_NAME` | Project name — determines the output filename |
| `--output-dir` / `-o` | Output directory (default: `config/project_config/`) |

The generated file is a fully-commented YAML template. Open it in the GUI editor or any text editor and fill in paths, modules, and task parameters.

---

## `neuropipe generate-checks`

Generate a blank results-check config template (`{project}_checks.yaml`). Equivalent to clicking **New** in the GUI Results Check Config tab.

```bash
neuropipe generate-checks branch

# Write to a custom directory
neuropipe generate-checks branch --output-dir /scratch/my_project/config/results_check
```

**Arguments / Options:**

| | Description |
|---|-------------|
| `PROJECT_NAME` | Project name — determines the output filename |
| `--output-dir` / `-o` | Output directory (default: `config/results_check/`) |

The generated file contains commented examples for both `required_files` and `count_check` block types. See [Output Checks Configuration](../configuration/output-checks.md) for the full reference.
