# GCDS Neuroimaging Pipeline

A comprehensive neuroimaging data processing pipeline designed for managing and analyzing fMRI and structural MRI data. This tool provides both a user-friendly graphical interface (GUI) and a powerful command-line interface (CLI) for processing neuroimaging datasets on HPC clusters.

## Table of Contents

- [Overview](#overview)
- [Installation](#installation)
- [Getting Started](#getting-started)
  - [Option 1: Graphical Interface (GUI)](#option-1-graphical-interface-gui)
  - [Option 2: Command Line (CLI)](#option-2-command-line-cli)
- [GUI User Guide](#gui-user-guide)
- [CLI User Guide](#cli-user-guide)
- [Common Workflows](#common-workflows)
- [Troubleshooting](#troubleshooting)

---

## Overview

The GCDS Neuroimaging Pipeline automates the entire workflow of neuroimaging data processing, from raw data organization to advanced analysis. It supports:

- **Data Preparation**: Unzipping, DICOM to BIDS conversion
- **Structural Processing**: Volume-based structural analysis with AFNI
- **Resting State fMRI**: Preprocessing with fMRIPrep and postprocessing with XCP-D
- **Task fMRI**: Processing for various task paradigms (KidVid, Cards, etc.)
- **Quality Control**: Automated quality assessment with MRIQC
- **Job Management**: Integrated job monitoring and database tracking for HPC environments

---

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

---

## Getting Started

You have two options to use this pipeline: a web-based graphical interface (GUI) or command-line interface (CLI).

### Option 1: Graphical Interface (GUI)

**Best for**: Users who prefer visual interfaces, beginners, or one-time analyses

**Advantages**:
- User-friendly point-and-click interface
- Visual job monitoring with charts and dashboards
- Built-in configuration editor
- No need to remember command syntax

**Launch the GUI**:
```bash
neuropipe-gui
```

Then open your web browser to `http://localhost:8050`

![using_GUI](images/using_GUI.png)

### Option 2: Command Line (CLI)

**Best for**: Advanced users, automated workflows, batch processing, or scripting

**Advantages**:
- Easy to integrate into scripts
- Can be run from anywhere on the HPC system
- Better for automation

**Basic CLI command**:
```bash
neuropipe run \
  --subjects 001,002 \
  --input /path/to/data \
  --output /path/to/output \
  --work /path/to/work \
  --project my_project \
  --prep unzip_recon
```

---

## GUI User Guide

### Step 1: Configure Your Project

Before processing data, you need a project configuration file.

**To create a new configuration**:

1. Navigate to the **Project Config** tab
2. Enter your project name (e.g., "my_study")
3. Specify output directory for the config file
4. Click **Generate Configuration Template**
5. Click **Load Config** to edit the generated file
6. Modify settings as needed:
   - Update directory paths
   - Configure container locations
   - Set resource requirements
7. Click **Save Configuration**

**Important settings to configure**:
- `prefix`: Subject prefix (usually "sub-")
- `envir_dir.container_dir`: Path to Singularity containers
- `envir_dir.template_dir`: Path to templates and atlases
- Resource profiles (memory, time limits)

![](images/tab3_1.png)
![](images/tab3_2.png)

An example of [config file](src/neuro_pipeline/pipeline/config/project_config/branch_config.yaml)

> [!NOTE]
> If you are familiar with the analysis process, you can modify the corresponding analysis scripts. Otherwise, please use the default configuration.
> Additionally, the [global configuration file](src/neuro_pipeline/pipeline/config/config.yaml) provides a place for modifying analysis scripts and adjusting HPC resource allocation. However, unless you have specific requirements, it is recommended to use the default configuration.

### Step 2: Select Subjects

**Option A: Automatic Detection**
1. Go to **Analysis Control** tab
2. Enter subject prefix (default: "sub-")
3. Enter directory path containing subjects
4. Click **Detect Subjects**
5. Review the detected subjects list

![](images/tab1_0.png)

**Option B: Manual Entry**
1. In the "Manual Entry" field, enter subject IDs
2. Format: `001,002,003`
3. The system will automatically handle the prefix

![](images/tab1_1.png)

### Step 3: Configure Processing Pipeline

Select the processing steps you need:

**Preparation**:
- `None`: Skip Preparation
- `Unzip`: Extract compressed data
- `Recon`: Convert DICOM to BIDS
- `Unzip + Recon`: Do both

**Structural Processing**:
- `None`: Skip structural processing
- `Volume`: Volume-based analysis with AFNI

**Resting State fMRI**:
- Preprocessing: `fMRIPrep`
- Postprocessing: `XCP-D`, compute functional connectivity

**Task fMRI**:
- Select tasks to preprocess (KidVid, Cards)
- Select tasks to postprocess (KidVid, Cards)

**Quality Control (MRIQC)**:
- `Individual`: Per-subject QC
- `Group`: Group-level QC
- `All`: Both individual and group

### Step 4: Set Directories

Fill in the required paths:
- **Input Directory**: Location of data you want to process. 
  - For example, if you want to perform `recon`, you should enter the DICOM file directory. If you want to preprocess AFNI structural volumes, you should enter the BIDS path.
- **Output Directory**: Where processed data will be saved
- **Work Directory**: Temporary files, working log, and job database

![](images/tab1_2.png)

### Step 5: Execute Pipeline

1. **Optional**: Check "Dry Run" to preview commands without execution
2. Click **Generate Command** to preview the exact commands
3. Review the command preview
4. Click **Execute Pipeline** to submit jobs
5. Monitor execution status in the alert box

![](images/tab1_3.png)

### Step 6: Monitor Jobs

Navigate to the **Job Monitor** tab to track your jobs:

**Features**:
- **Database Configuration**: Input the directory of database
- **Query Configuration**: Use SQL to query job history
- **Visualizations**: View charts showing job statistics
- **Export CSV**: Download current query results as CSV
- **Query Results**: A data table for database

![](images/tab2_1.png)
![](images/tab2_2.png)
![](images/tab2_3.png)

**Example queries command**:
```sql
-- View all jobs for a project
SELECT * FROM pipeline_executions WHERE project_name = 'my_study';

-- Find failed jobs
SELECT * FROM pipeline_executions WHERE status = 'FAILED';

-- Jobs from the last 7 days
SELECT * FROM pipeline_executions 
WHERE start_time > datetime('now', '-7 days');
```

> [!IMPORTANT]  
> - The `unzip` program automatically extracts all compressed files in the input path. Subsequently, it checks `prefix+ID` for further analysis.
> - The `--project` parameter automatically reads the task configuration file, which is `{project}_config.yaml` in the [config path](src/neuro_pipeline/pipeline/config/project_config). Similarly, when creating a project configuration file, it generates the `{project}_config.yaml` file.
> - Data analysis scripts are located in `src/neuro_pipeline/pipeline/scripts`

---

## CLI User Guide

### Basic Syntax

```bash
neuropipe run [OPTIONS]
```

### Required Arguments

| Argument | Description | Example |
|----------|-------------|---------|
| `--subjects` | Subject IDs (comma-separated) or file path | `001,002` or `subjects.txt`. You should specify the `prefix` in your project configuration file. |
| `--input` | Input directory | `/data/raw` |
| `--output` | Output directory | `/data/processed` |
| `--work` | Work directory | `/data/work` |
| `--project` | Project name | `my_study` |

### Processing Options

| Option | Values | Description |
|--------|--------|-------------|
| `--prep` | `unzip`, `recon`, `unzip_recon` | Preprocessing steps |
| `--structural` | `volume` | Structural processing with AFNI |
| `--rest-prep` | `fmriprep` | Resting state preprocessing |
| `--rest-post` | `xcpd` | Resting state postprocessing with fMRIPrep |
| `--task-prep` | `kidvid`, `cards`, `all` | Task preprocessing with AFNI |
| `--task-post` | `kidvid`, `cards`, `all` | Task postprocessing with AFNI (under development) |
| `--mriqc` | `individual`, `group`, `all` | Quality control with MRIQC |
| `--session` | Session ID | Default: `01` |

### Execution Options

| Option | Description |
|--------|-------------|
| `--dry-run` | Preview commands without execution |
| `--wait` | Wait for jobs to complete (default) |
| `--polling-interval` | Check job status every N seconds (default: 60) |

### CLI Examples

**Example 1: Complete processing pipeline**
```bash
neuropipe run \
  --subjects 001,002,003 \
  --input /data/zip_files \
  --output /data/processed \
  --work /data/work \
  --project my_study \
  --prep unzip_recon \
  --structural volume \
  --rest-prep fmriprep \
  --rest-post xcpd \
  --task-prep kidvid,cards \
  --task-post kidvid,cards \
  --mriqc all
```

**Example 2: Preparation only**
```bash
neuropipe run \
  --subjects 001,002 \
  --input /data/zip_files \
  --output /data/processed \
  --work /data/work \
  --project my_study \
  --prep unzip_recon
```

**Example 3: Resting state analysis**
```bash
neuropipe run \
  --subjects 001,002 \
  --input /data/BIDS \
  --output /data/processed \
  --work /data/work \
  --project my_study \
  --rest-prep fmriprep \
  --rest-post xcpd
```

**Example 4: Using subject list from file**
```bash
# Create subjects.txt with one subject per line
echo "001" > subjects.txt
echo "002" >> subjects.txt

neuropipe run \
  --subjects subjects.txt \
  --input /data/zip_files \
  --output /data/processed \
  --work /data/work \
  --project my_study \
  --prep unzip_recon
```

**Example 5: Dry run to preview**
```bash
neuropipe run \
  --subjects 001 \
  --input /data/zip_files \
  --output /data/processed \
  --work /data/work \
  --project my_study \
  --prep unzip_recon \
  --dry-run
```

**Example 6: Process multiple tasks**
```bash
neuropipe run \
  --subjects 001,002 \
  --input /data/BIDS \
  --output /data/processed \
  --work /data/work \
  --project my_study \
  --task-prep kidvid,cards \
  --task-post kidvid,cards
```

### Utility Commands

**Detect subjects in directory**:
```bash
neuropipe detect-subjects /data/raw --output subjects.txt

neuropipe detect-subjects /data/BIDS

neuropipe detect-subjects /data/raw --prefix "sub-" --output subjects.txt

```

**List available tasks**:
```bash
neuropipe list-tasks
```

---

## Common Workflows

### Workflow 1: First-Time Complete Processing

For processing raw data through the complete pipeline:

**Using GUI**:
1. Create project configuration
2. Detect subjects
3. Select: Prep → Structural → Rest → Task → MRIQC (all)
4. Execute pipeline
5. Monitor in Job Monitor tab

**Using CLI**:
```bash
neuropipe run \
  --subjects 001,002,003 \
  --input /data/raw_zip_files \
  --output /data/processed \
  --work /data/work \
  --project my_study \
  --prep unzip_recon \
  --structural volume \
  --rest-prep fmriprep \
  --rest-post xcpd \
  --task-prep all \
  --task-post all \
  --mriqc all
```

### Workflow 2: Preparation (unzip+recon)

Unzip files:
```bash
neuropipe run \
  --subjects 001,002,003 \
  --input /data/raw_zip_files \
  --output /data/processed \
  --work /data/work \
  --project my_study \
  --prep unzip
```

Reconstruct to BIDS:
```bash
neuropipe run \
  --subjects 001,002 \
  --input /data/raw \
  --output /data/processed \
  --work /data/work \
  --project my_study \
  --prep recon
```

### Workflow 3: Reprocessing (Skip preparation phase)

If you already have BIDS data:

**Using CLI**:

Only preprocess structural MRI:
```bash
neuropipe run \
  --subjects 001,002 \
  --input /data/BIDS \
  --output /data/processed \
  --work /data/work \
  --project my_study \
  --structural volume
```

For RS data:
```bash
neuropipe run \
  --subjects 001,002 \
  --input /data/BIDS \
  --output /data/processed \
  --work /data/work \
  --project my_study \
  --rest-prep fmriprep \
  --rest-post xcpd
```
For task data:
```bash
neuropipe run \
  --subjects 001,002 \
  --input /data/BIDS \
  --output /data/processed \
  --work /data/work \
  --project my_study \
  --task-prep kidvid \
  --task-post kidvid
```

### Workflow 4: Only Quality Control

Run MRIQC on existing BIDS data:

**Using CLI**:
```bash
neuropipe run \
  --subjects 001,002 \
  --input /data/BIDS \
  --output /data/processed \
  --work /data/work \
  --project my_study \
  --mriqc all
```

---

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

## Troubleshooting

### Common Issues

**1. "No subjects found"**

- Check subject prefix matches your directory naming
- Verify input directory path is correct
- Ensure you have read permissions

**2. "Project configuration not found"**

- Verify project name matches config file name
- Check config file is in correct location: `src/neuro_pipeline/pipeline/config/project_config/`
- Use GUI to generate template if needed

**3. Jobs not submitting**

- Verify SLURM is available: `squeue`
- Check HPC account permissions
- Review resource limits in project config

**4. "Permission denied" errors**

- Check file permissions: `ls -la`
- Verify you can write to output/work directories
- Ensure containers are accessible

**5. GUI won't start**

- Check port 8050 is not in use: `lsof -i :8050`
- Try different port: `neuropipe-gui --port 8051`
- Check firewall settings

**6. Task preprocessing/postprocessing not found**

- Ensure tasks are defined in project config
- Check script files exist in correct location
- Verify task names match config exactly

### Getting Help

**Check job logs**:
```bash
# Find log directory
ls /data/work/project_name/log/

# View SLURM output
cat slurm-JOBID.out
```

**Query job database** (via GUI or directly):
```sql
SELECT * FROM pipeline_executions 
WHERE status = 'FAILED' 
ORDER BY start_time DESC;
```

**Use dry-run mode**:
```bash
neuropipe run ... --dry-run
```

**Verify configuration**:
```bash
# Check if project config exists
ls src/neuro_pipeline/pipeline/config/project_config/my_study_config.yaml
```

---

## Best Practices

1. **Always test with dry-run first**: Preview commands before execution
2. **Start small**: Test with 1-2 subjects before processing full dataset
3. **Monitor regularly**: Check Job Monitor tab or database for errors
4. **Organize data properly**: Follow BIDS naming conventions
5. **Backup configurations**: Keep copies of project config files
6. **Use appropriate resources**: Adjust memory/time limits in config based on data size
7. **Check logs**: Review SLURM logs when jobs fail
8. **Use subject lists**: For large datasets, use text files instead of command-line lists

---

## Advanced Tips

### Custom Resource Profiles

Edit project config to adjust resources:

```yaml
resource_profiles:
  heavy_long:
    memory: "128gb"    # Increase for large datasets
    time: "48:00:00"   # Extend time limit
```

### Database Queries

Access job history programmatically:

```python
import sqlite3
conn = sqlite3.connect('/data/work/project/log/pipeline_jobs.db')
df = pd.read_sql_query("SELECT * FROM pipeline_executions", conn)
```

---

## FAQ

**Q: Can I process subjects in batches?**  
A: Yes, either submit multiple commands or use a subject list file with batches.

**Q: How do I check if processing completed successfully?**  
A: Use the Job Monitor tab or query the database for job status. Or check the output file and log files.

**Q: Can I reprocess only failed subjects?**  
A: Yes, query the database for failed subjects and create a new subject list.

**Q: What if I need to stop processing?**  
A: Cancel jobs in SLURM: `scancel JOBID` or `scancel -u $USER`

**Q: How much disk space do I need?**  
A: Work directory (for fMRIPrep and MRIQC) needs ~10-20GB per subject. Output depends on processing steps. Please regularly clean up working files, but retain logs and databases.

**Q: Can I use this on local computers?**  
A: The pipeline is designed for HPC/SLURM environments. Local execution would require modifications.

**Q: What if analysis script failed to run?**  
A: Verify the exported variables and environment settings by checking the contents of the `log/wrapper` folder in the working directory, paying particular attention to paths and submitted Slurm commands. Next, inspect the Slurm logs located under `log/subjects`. Finally, review the analysis script to ensure its code is correct. It is recommended to use `echo` or `print` statements to confirm that variables are being passed as intended.

---

**Version**: 0.1.0  
**Last Updated**: December 2025

For questions or issues, please contact the pipeline maintainer, [QiuyuYu](https://github.com/QiuyuYu3), or submit an issue to the repository.
