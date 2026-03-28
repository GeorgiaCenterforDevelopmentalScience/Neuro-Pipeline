# Dev Log - [GCDS-Neuro-Pipeline]

---

## [0.12.2-alpha] – 2026-03-10
### Added
- Enhanced task parameter usage: CLI commands now support flexiable `--task-prep` options (e.g., `--task-prep cards`) after configuration in config files, with support for task-specific configurations like `task_afni`.
- Configurable script directories: Each project can now specify its own `script_dir` path for greater flexibility in script management.

## [0.12.1-alpha] – 2026-01-21
### Removed
- Deprecated DB function completely.

## [0.12.0-alpha] – 2025-12-15

### Added
- Automatic database file backup:
  - Each run now creates a backup.
  - Keeps a maximum of 10 backups; older backups are automatically removed.
- Default DAG job (`merge_logs`) added to automatically merge all JSON logs into a single database file after all tasks complete (archived JSONL files are excluded).  
- Standalone scripts for:
  - Manual backup of database files.
  - Manual merging of JSON logs into a database file, for flexible user use.  

### Changed
- Refactored database handling:
  - Replaced the previous DB file format with JSONL-based storage for safer, more reliable logging.  
  - Integrated new logging and merging mechanism into DAG execution flow.  

### Fixed
- Resolved critical issue where canceling jobs (e.g., via `scancel`) could corrupt the database file.  
- Improved robustness of database operations under incomplete or interrupted runs.  

### Removed
- Deprecated DB handling code prone to corruption during job interruptions.

## [0.11.1-alpha] – 2025-12-12
### Changed
- Updated `config_dir` in project config yaml.

### Fixed
- Fixed an issue where IDs could not be detected when the prefix was empty.

### Removed
- Remove WAL mode configuration from database connection setup.
- Removed hard-coded `config_dir` in dcm2bids script.

## [0.11.0-alpha] – 2025-12-10
### Changed
- Interface layout and logic were refactored for better clarity and maintainability.
- CLI command interface was revised, improving workflow handling for RS and task analyses.
- Database model and path resolution logic were improved for greater consistency.

### Added
- Database visualization page was introduced.

### Fixed
- Configuration file generation in the interface module was corrected.

### Removed
- NIfTI file viewer functionality was removed from the interface.
- `fieldmap` and `afni_surface` CLI were removed.

---

## [0.10.0-alpha] – 2025-07-06
### Added
- New CLI arguments: `session`, `prefix`, `project`.
- Automatic BIDS ID extraction.
- Project-level configuration YAML generator.
- Command history logging module.
- Job status logging system with SQL backend.
- DAG builder module and workflow plot generation.
- Environment test suite for analysis scripts.

### Changed
- Simplified resting-state pipeline; removed legacy AFNI volume-based `rest_prep`.
- Cleaned and reorganized argument structure.
- Improved debug logging (directory/file echo).
- Updated template handling, TR removal, and smoothing workflow.

### Fixed
- Enhanced workflow/error summary logging.

### Removed
- Deprecated AFNI volume-based resting-state preprocessing arguments.

---

## [0.1.0-dev] – 2025-07-01
### Added
- Initial project structure and module layout.
- Drafted CLI argument parsing and usage documentation.
- Basic DAG module structure.
- Script cleanup and inline comments.

### Changed
- Minor internal refactoring and project organization improvements.

---

## [Unreleased]
### Planned
- Additional interface improvements and CLI refinements.