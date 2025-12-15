# Project Roadmap – GCDS-Neuro-Pipeline

This document outlines the planned development path for the GCDS-Neuro-Pipeline.  
It is intended to guide future contributions and provide clarity for collaborators and users.  

Version numbers follow semantic versioning; "x" denotes future patch-level releases within the minor version series.

---

## Vision
A robust, modular, reproducible pipeline for neuroimaging preprocessing and analysis, following BIDS standards and enabling flexible workflows across modalities (structural, functional, rs-fMRI).

---

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

## Long-Term / Exploratory
- Further high-level goals will be defined as the project matures.
