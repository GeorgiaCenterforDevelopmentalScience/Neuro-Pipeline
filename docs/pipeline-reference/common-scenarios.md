---
title: Common Scenarios
---
# Common Scenarios

Quick reference for the most common `neuropipe run` workflows. All examples use generic paths — substitute your actual directories and subject list.

---

## Workflow 1: Full Pipeline (all stages)

Run everything from raw data to postprocessing in a single command:

```bash
neuropipe run \
  --subjects subjects.txt \
  --input /data/raw_zip_files \
  --output /data/processed \
  --work /data/work \
  --config-dir /data/config \
  --project my_study \
  --session 01 \
  --prep unzip_recon \
  --intermed volume,bfc \
  --bids-prep rest,dwi \
  --bids-post rest,dwi \
  --staged-prep cards,kidvid \
  --mriqc all
```

---

## Workflow 2: Preparation Only

**Unzip raw data:**

```bash
neuropipe run \
  --subjects 001,002,003 \
  --input /data/raw_zip_files \
  --output /data/processed \
  --work /data/work \
  --config-dir /data/config \
  --project my_study \
  --session 01 \
  --prep unzip
```

**Reconstruct to BIDS (assumes raw data already extracted):**

```bash
neuropipe run \
  --subjects 001,002,003 \
  --input /data/raw \
  --output /data/processed \
  --work /data/work \
  --config-dir /data/config \
  --project my_study \
  --session 01 \
  --prep recon
```

**Unzip then reconstruct in one go:**

```bash
neuropipe run \
  --subjects 001,002,003 \
  --input /data/raw_zip_files \
  --output /data/processed \
  --work /data/work \
  --config-dir /data/config \
  --project my_study \
  --session 01 \
  --prep unzip_recon
```

---

## Workflow 3: Skip Preparation (BIDS data already exists)

If you already have a BIDS dataset and only need to run downstream processing:

**Intermediate structural processing only:**

```bash
neuropipe run \
  --subjects 001,002,003 \
  --input /data/BIDS \
  --output /data/processed \
  --work /data/work \
  --config-dir /data/config \
  --project my_study \
  --session 01 \
  --intermed volume
```

**Resting-state fMRI:**

```bash
neuropipe run \
  --subjects 001,002,003 \
  --input /data/BIDS \
  --output /data/processed \
  --work /data/work \
  --config-dir /data/config \
  --project my_study \
  --session 01 \
  --bids-prep rest \
  --bids-post rest
```

**DWI:**

```bash
neuropipe run \
  --subjects 001,002,003 \
  --input /data/BIDS \
  --output /data/processed \
  --work /data/work \
  --config-dir /data/config \
  --project my_study \
  --session 01 \
  --bids-prep dwi \
  --bids-post dwi
```

**Task fMRI (staged — requires intermed first):**

```bash
neuropipe run \
  --subjects 001,002,003 \
  --input /data/BIDS \
  --output /data/processed \
  --work /data/work \
  --config-dir /data/config \
  --project my_study \
  --session 01 \
  --intermed volume \
  --staged-prep cards,kidvid
```

---

## Workflow 4: Quality Control Only

Run MRIQC on existing BIDS data:

```bash
neuropipe run \
  --subjects 001,002,003 \
  --input /data/BIDS \
  --output /data/processed \
  --work /data/work \
  --config-dir /data/config \
  --project my_study \
  --session 01 \
  --mriqc all
```

Individual and group reports separately:

```bash
# Individual subject reports first
neuropipe run ... --config-dir /data/config --mriqc individual

# Then group report (after individual jobs finish)
neuropipe run ... --config-dir /data/config --mriqc group
```

---

## Workflow 5: BIDS conversion through to task fMRI (recon → intermed → staged)

```bash
neuropipe run \
  --subjects 001,002,003 \
  --input /data/raw \
  --output /data/processed \
  --work /data/work \
  --config-dir /data/config \
  --project my_study \
  --session 01 \
  --prep recon \
  --intermed volume \
  --staged-prep cards,kidvid
```

---

## Workflow 6: BIDS conversion through to fMRI preprocessing and postprocessing (recon → bids-prep → bids-post)

```bash
neuropipe run \
  --subjects 001,002,003 \
  --input /data/raw \
  --output /data/processed \
  --work /data/work \
  --config-dir /data/config \
  --project my_study \
  --session 01 \
  --prep recon \
  --bids-prep rest \
  --bids-post rest
```

---

## Workflow 7: Dry Run (preview before submitting)

Check the execution plan and generated wrapper scripts without submitting anything to SLURM:

```bash
neuropipe run \
  --subjects 001,002,003 \
  --input /data/BIDS \
  --output /data/processed \
  --work /data/work \
  --config-dir /data/config \
  --project my_study \
  --session 01 \
  --intermed volume \
  --bids-prep rest \
  --dry-run
```

Wrapper scripts are written to `{work_dir}/log/wrapper/` so you can inspect the exact `sbatch` commands and exported variables before committing.

---

## Workflow 8: Resume Interrupted Run

If a previous run was interrupted or some subjects failed, resubmit only the subjects with incomplete outputs:

```bash
neuropipe run \
  --subjects subjects.txt \
  --input /data/BIDS \
  --output /data/processed \
  --work /data/work \
  --config-dir /data/config \
  --project my_study \
  --session 01 \
  --intermed volume \
  --bids-prep rest \
  --resume
```

`--resume` checks `{project}_checks.yaml` and skips subjects that already have valid outputs. Requires the checks config to be set up — see [Output Checks Configuration](../configuration/output-checks.md).
