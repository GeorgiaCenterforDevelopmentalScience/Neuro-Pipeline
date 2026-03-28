# Project Roadmap – GCDS-Neuro-Pipeline

This document outlines the planned development path for the GCDS-Neuro-Pipeline.  
It is intended to guide future contributions and provide clarity for collaborators and users.  

Version numbers follow semantic versioning; "x" denotes future patch-level releases within the minor version series.

---

## Vision
A robust, modular, reproducible pipeline for neuroimaging preprocessing and analysis, following BIDS standards and enabling flexible workflows across modalities (structural, functional, rs-fMRI).

---

# Completed Features (v0.12.x)
- Enhanced task parameter usage in CLI: Simplified `--task-prep` options (e.g., `--task-prep cards`) with task-specific configurations.
- Configurable script directories per project for flexible script management.

# Milestones

## v0.13.x
### Core Features
- Complete DAG visualization and pipeline graph rendering (e.g., `T1 → sswarper → task preprocessing`).
- Improve argument structure for task-level configurations.

### Testing & Validation
- Expand test environment for all major analysis modules.
- Add unit tests for workflow components and DAG builder.

### Documentation
- Developer documentation for pipeline components.

---

## v0.14.x – Modalities Expansion
### Pipeline Enhancements
- Optimize CLI commands.
- Optimize DAG-related code to reduce hard-coding.

### Documentation
- Full CLI documentation (usage, examples, help messages).

---

## v0.15.x – Validation & Standards
### Standards & Interoperability
- Optimize task-related CLI commands to automatically detect tasks and generate CLI instructions instead of hard-coding them.

### New Modules
- Add graph theory and group analysis pipeline.

---

## Refactoring & Improvements

### Architecture
- Move input_from path resolution from hpc_utils into DAGExecutor — submit_slurm_job currently contains a dependency_mapping dict that duplicates logic already handled in dag.py. The SLURM submission layer should only be responsible for job submission, not path inference. See # TODO: MOVE TO DAG? comment in hpc_utils.py.
- Derive dependency mapping from config instead of hardcoding — Both dag.py and hpc_utils.py maintain a hand-written dependency_mapping dict. This relationship is already implicitly expressed via the input_from field in config.yaml. Consider inferring it directly from config to avoid keeping two sources of truth in sync.

### Robustness
- Unify subject parsing logic — Subject list parsing (comma-separated string vs. file path) is duplicated across core.py, submit_slurm_job, and wrapper_functions.sh with slightly different implementations. Extract into a single shared utility function.
- Harden `$WORK_DIR substitution in db path resolution — db_path.replace('$WORK_DIR', original_work_dir)` is a fragile string replacement. A typo in the config variable name will silently produce a malformed path. Consider using a more explicit template mechanism or adding a post-resolution existence check.


## Long-Term / Exploratory
- Further high-level goals will be defined as the project matures.
