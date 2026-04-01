# GCDS Neuroimaging Pipeline

A comprehensive neuroimaging data processing pipeline designed for managing and analyzing fMRI and structural MRI data. This tool provides both a user-friendly graphical interface (GUI) and a powerful command-line interface (CLI) for processing neuroimaging datasets on HPC clusters.

**Full documentation:** 

## Supported Pipelines

| Pipeline | Tools |
|----------|-------|
| Data preparation | unzip, dcm2bids (DICOM → BIDS) |
| Structural MRI | AFNI (`@SSwarper`) |
| Resting-state fMRI | fMRIPrep + XCP-D |
| Task fMRI | AFNI (`afni_proc.py`) |
| Diffusion MRI (DWI) | QSIPrep + QSIRecon |
| Quality control | MRIQC |

## Installation

### Prerequisites

- Python 3.10 or higher
- Access to an HPC cluster with SLURM scheduler
- Required neuroimaging software (fMRIPrep, XCP-D, AFNI, etc.) installed on your HPC system

### Install the Pipeline

1. Clone or download the repository to your HPC system:
   ```bash
   git clone <repository-url>
   cd Neuro_Pipeline
   ```

2. Install the package:
   ```bash
   pip install -e .

   # Or developmental mode
   # pip install -e .[dev]
   ```

3. Verify installation:
   ```bash
   neuropipe --help
   neuropipe-gui --help
   ```

## Directory Structure

### Input Directory Structure

If you start with unpacking, the unpacking path can be in any format as long as it contains the files to be unpacked.

Your raw BIDS data will be organized as:

```
input_directory/
├── sub-001/
│   └── ses-01/
│       ├── anat/
│       ├── func/
│       └── ...
├── sub-002/
│   └── ses-01/
│       └── ...
└── ...
```

### Output Directory Structure

The pipeline creates:

```
output_directory/
└── project_name/
    ├── raw/                    # Extracted raw data
    ├── BIDS/                   # BIDS-formatted data
    ├── AFNI_derivatives/       # AFNI outputs
    ├── BIDS_derivatives/
    │   ├── fmriprep/          # fMRIPrep outputs
    │   └── xcpd/              # XCP-D outputs
    └── quality_control/
        └── mriqc/             # MRIQC reports

work_directory/
└── project_name/
    ├── log/
    │   └── pipeline_jobs.db   # Job tracking database
    └── [temporary files]
```

---

## Quick Start

```bash
# Launch the GUI
neuropipe-gui   # then open http://localhost:8050

# Or use the CLI — dry-run a single subject first
neuropipe run \
  --subjects 001 \
  --input /data/BIDS \
  --output /data/processed \
  --work /data/work \
  --project my_study \
  --structural volume \
  --dry-run
```

## Complete Pipeline Example

A full run processing structural, resting-state, task fMRI, DWI, and QC for a cohort:

```bash
neuropipe run \
  --subjects 001,002,003,004,005 \
  --input /data/BIDS \
  --output /data/processed \
  --work /data/work \
  --project my_study \
  --prep unzip_recon \
  --structural volume \
  --rest-prep fmriprep \
  --rest-post xcpd \
  --task-prep all \
  --dwi-prep qsiprep \
  --dwi-post qsirecon \
  --mriqc individual
```

Tasks run in dependency order: unzip → recon_bids → structural/fmriprep/mriqc → xcpd/task fMRI → DWI post. Each dependency is enforced by SLURM's `--dependency=afterok`.

### Resume: Skip Already-Completed Subjects

`--resume` checks each subject's output files before submitting and silently skips subjects that already have valid outputs:

```bash
neuropipe run \
  --subjects 001,002,003,004,005 \
  --input /data/BIDS \
  --output /data/processed \
  --work /data/work \
  --project my_study \
  --structural volume \
  --resume
```

Before submitting each task's array job, the pipeline reads `config/results_check/{project}_checks.yaml` and tests whether each subject's expected output files exist (and optionally meet a minimum size or count). Only subjects that fail the check are included in the submitted array — subjects that already passed are silently skipped.

If no checks file exists for a task, a warning is printed and all subjects are submitted.

## Key CLI Options

| Option | Description |
|--------|-------------|
| `--prep` | `unzip`, `recon`, `unzip_recon` |
| `--structural` | `volume` (AFNI) |
| `--rest-prep` / `--rest-post` | `fmriprep` / `xcpd` |
| `--task-prep` / `--task-post` | `kidvid`, `cards`, `all` |
| `--dwi-prep` / `--dwi-post` | `qsiprep` / `qsirecon` |
| `--mriqc` | `individual`, `group`, `all` |
| `--dry-run` | Preview without submitting |
| `--resume` | Skip completed subjects |

## Configuration

Each project needs a `{project}_config.yaml` in `src/neuro_pipeline/pipeline/config/project_config/`. Use the GUI's **Project Config** tab to generate a template, then fill in your HPC paths and module names.

See [docs/configuration/](docs/configuration/) for a full annotated example.

## Checking Job Status

```bash
# Check which subjects finished
neuropipe check-outputs --project my_study --work /data/work --subjects 001,002,003

# Query the SQLite job database
sqlite3 /data/work/my_study/database/pipeline_jobs.db \
  "SELECT subject, task_name, status, error_msg FROM job_status WHERE status='FAILED';"
```


**Version**: 0.1.0  
**Last Updated**: March 2026

For questions or issues, please contact the pipeline maintainer, [QiuyuYu](https://github.com/QiuyuYu3), or submit an issue to the repository.
