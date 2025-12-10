# Dev Log - [GCDS-Neuro-Pipeline]

---

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