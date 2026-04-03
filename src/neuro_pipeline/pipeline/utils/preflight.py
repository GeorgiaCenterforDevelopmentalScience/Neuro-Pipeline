"""
preflight.py — Schema validation and pre-flight checks for neuropipe run.

Two layers of checks:
  1. check_schema()      — structure/reference validation (no filesystem access)
  2. check_filesystem()  — existence of scripts, containers, directories
"""

import os
import yaml
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Any, List, Optional

_HPC_CONFIG_PATH = Path(__file__).parent.parent / "config" / "hpc_config.yaml"
try:
    with open(_HPC_CONFIG_PATH, "r", encoding="utf-8") as _f:
        _hpc_config: Dict[str, Any] = yaml.safe_load(_f) or {}
except FileNotFoundError:
    _hpc_config = {}

@dataclass
class Issue:
    severity: str   # "ERROR" | "WARNING"
    category: str   # "schema" | "scripts" | "containers" | "directories"
    message: str

@dataclass
class PreflightResult:
    issues: List[Issue] = field(default_factory=list)

    @property
    def errors(self) -> List[Issue]:
        return [i for i in self.issues if i.severity == "ERROR"]

    @property
    def warnings(self) -> List[Issue]:
        return [i for i in self.issues if i.severity == "WARNING"]

    @property
    def ok(self) -> bool:
        """True when there are no ERROR-level issues."""
        return len(self.errors) == 0

class PreflightChecker:
    """
    Validates project config structure and filesystem state before job submission.

    Parameters
    ----------
    project_config : dict
        Loaded project YAML (e.g. branch_config.yaml).
    global_config : dict
        Loaded global pipeline config (config.yaml).
    work_dir : str | Path
        Work directory that will be created/used for this run.
    input_dir : str | Path
        Input data directory (must already exist).
    """

    # Pipeline source root: src/neuro_pipeline/pipeline/
    # Scripts are resolved relative to this directory.
    _PIPELINE_ROOT = Path(__file__).parent.parent

    def __init__(
        self,
        project_config: Dict[str, Any],
        global_config: Dict[str, Any],
        work_dir,
        input_dir,
        hpc_config: Optional[Dict[str, Any]] = None,
    ):
        self.project_config = project_config
        self.global_config = global_config
        self.hpc_config = hpc_config if hpc_config is not None else _hpc_config
        self.work_dir = Path(work_dir)
        self.input_dir = Path(input_dir)
        self._issues: List[Issue] = []

    def _err(self, category: str, message: str) -> None:
        self._issues.append(Issue("ERROR", category, message))

    def _warn(self, category: str, message: str) -> None:
        self._issues.append(Issue("WARNING", category, message))

    def _all_global_task_names(self) -> set:
        names = set()
        for section_tasks in self.global_config.values():
            if isinstance(section_tasks, list):
                for task in section_tasks:
                    if isinstance(task, dict) and "name" in task:
                        names.add(task["name"])
        return names

    def _global_task(self, name: str) -> Optional[Dict[str, Any]]:
        for section_tasks in self.global_config.values():
            if isinstance(section_tasks, list):
                for task in section_tasks:
                    if isinstance(task, dict) and task.get("name") == name:
                        return task
        return None

    # Schema/reference validation

    def check_schema(self) -> None:
        pc = self.project_config

        # Required top-level keys in project config
        for key in ("prefix", "scripts_dir", "envir_dir", "database", "setup"):
            if key not in pc:
                self._err("schema", f"project config missing required key: '{key}'")

        # envir_dir.container_dir
        envir_dir = pc.get("envir_dir") or {}
        if "container_dir" not in envir_dir:
            self._err("schema", "project config: envir_dir.container_dir is required")

        # database.db_path
        db_config = pc.get("database") or {}
        if "db_path" not in db_config:
            self._err("schema", "project config: database.db_path is required")

        # resource_profiles live in hpc_config.yaml
        global_profiles = set((self.hpc_config.get("resource_profiles") or {}).keys())

        # modules defined in project config
        defined_modules = set((pc.get("modules") or {}).keys())

        # global task names
        global_task_names = self._all_global_task_names()

        # Validate each setup entry
        setup = pc.get("setup") or {}
        for section, tasks in setup.items():
            if not isinstance(tasks, list):
                self._err("schema", f"setup.{section} must be a list of task entries")
                continue

            for entry in tasks:
                if not isinstance(entry, dict):
                    self._err("schema", f"setup.{section}: each entry must be a mapping")
                    continue

                name = entry.get("name")
                if not name:
                    self._err("schema", f"setup.{section}: an entry is missing the 'name' field")
                    continue

                # Task must exist in global config
                if name not in global_task_names:
                    self._err(
                        "schema",
                        f"setup task '{name}' (in section '{section}') is not defined in global config.yaml",
                    )

                # Resource profile must exist
                gtask = self._global_task(name)
                if gtask:
                    profile = gtask.get("profile")
                    if profile and profile not in global_profiles:
                        self._err(
                            "schema",
                            f"task '{name}': resource profile '{profile}' is not defined in resource_profiles",
                        )

                # environ references must be defined in project config modules
                for mod in entry.get("environ") or []:
                    if mod not in defined_modules:
                        self._err(
                            "schema",
                            f"task '{name}': environ entry '{mod}' is not defined in project config modules",
                        )

    # Filesystem checks

    def check_filesystem(self) -> None:
        pc = self.project_config

        # --- Input directory -------------------------------------------------
        if not self.input_dir.exists():
            self._err("directories", f"input directory not found: {self.input_dir}")

        # --- Work directory parent must be writable --------------------------
        work_parent = self.work_dir if self.work_dir.exists() else self.work_dir.parent
        if work_parent.exists() and not os.access(work_parent, os.W_OK):
            self._err("directories", f"work directory is not writable: {work_parent}")

        # --- scripts_dir -----------------------------------------------------
        scripts_dir_rel = pc.get("scripts_dir", "")
        scripts_dir: Optional[Path] = None
        if scripts_dir_rel:
            scripts_dir = self._PIPELINE_ROOT / scripts_dir_rel
            if not scripts_dir.exists():
                self._err("scripts", f"scripts_dir not found: {scripts_dir}")
                scripts_dir = None  # skip per-script checks below

        # --- container_dir ---------------------------------------------------
        container_dir_str = (pc.get("envir_dir") or {}).get("container_dir", "")
        container_dir: Optional[Path] = None
        if container_dir_str:
            container_dir = Path(container_dir_str)
            if not container_dir.exists():
                self._warn("containers", f"container_dir not found: {container_dir}")
                container_dir = None  # skip per-container checks below

        # --- Per-task checks -------------------------------------------------
        setup = pc.get("setup") or {}
        for section, tasks in setup.items():
            if not isinstance(tasks, list):
                continue
            for entry in tasks:
                if not isinstance(entry, dict):
                    continue
                name = entry.get("name")
                if not name:
                    continue

                gtask = self._global_task(name)

                # Check each script referenced by the global task definition
                if scripts_dir and gtask:
                    for script in gtask.get("scripts") or []:
                        script_path = scripts_dir / script
                        if not script_path.exists():
                            self._err(
                                "scripts",
                                f"task '{name}': script not found: {script_path}",
                            )

                # Check container .sif file
                container_name = entry.get("container")
                if container_name and container_dir:
                    container_path = container_dir / container_name
                    if not container_path.exists():
                        self._warn(
                            "containers",
                            f"task '{name}': container not found: {container_path}",
                        )

    def run_all(self) -> PreflightResult:
        """Run schema + filesystem checks and return the combined result."""
        self._issues = []
        self.check_schema()
        self.check_filesystem()
        return PreflightResult(issues=list(self._issues))

# Reporting
def print_preflight_report(result: PreflightResult) -> None:
    """Print a structured pre-flight report to stdout."""
    n_err = len(result.errors)
    n_warn = len(result.warnings)

    if n_err == 0 and n_warn == 0:
        print("[preflight] All checks passed.")
        return

    header = f"[preflight] {n_err} error(s), {n_warn} warning(s) found"
    print(header)

    # Group by category
    by_category: Dict[str, List[Issue]] = {}
    for issue in result.issues:
        by_category.setdefault(issue.category, []).append(issue)

    for category, issues in by_category.items():
        print(f"\n  [{category}]")
        for issue in issues:
            tag = "  ERROR  " if issue.severity == "ERROR" else "  warning"
            print(f"    {tag}: {issue.message}")

    if n_err > 0:
        print(
            f"\n[preflight] {n_err} error(s) must be resolved before jobs can be submitted."
            "\n            Re-run with --skip-preflight to bypass these checks."
        )
    else:
        print(f"\n[preflight] No blocking errors. Warnings above are informational.")
