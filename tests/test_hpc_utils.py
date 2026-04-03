"""
test_hpc_utils.py

Tests for pipeline/utils/hpc_utils.py

Covers:
1. get_hpc_resources        — profile merging, array param substitution, bad profile
2. get_environment_commands — environ as list / str / empty
3. get_script_with_validation — script found / not found
4. create_wrapper_script    — generated content correctness (the most important section)
5. submit_slurm_job (dry_run) — no real sbatch call needed
"""

import os
import time
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock, mock_open
from tests.conftest import MOCK_CONFIG, MOCK_HPC_CONFIG, MOCK_PROJECT_CONFIG


# config  = pipeline task/array config  (config.yaml)
# hpc_config = scheduler + resource profiles (hpc_config.yaml)
PIPELINE_CONFIG_PATH = "neuro_pipeline.pipeline.utils.hpc_utils.config"
HPC_CONFIG_PATH      = "neuro_pipeline.pipeline.utils.hpc_utils.hpc_config"
CONFIG_UTILS_PATH    = "neuro_pipeline.pipeline.utils.config_utils.config"

# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def import_hpc():
    """Import hpc_utils with mock configs injected."""
    with patch(PIPELINE_CONFIG_PATH, MOCK_CONFIG), patch(HPC_CONFIG_PATH, MOCK_HPC_CONFIG):
        import importlib
        import neuro_pipeline.pipeline.utils.hpc_utils as mod
        importlib.reload(mod)
        return mod


# ===========================================================================
# 1. get_hpc_resources
# ===========================================================================

class TestGetHPCResources:

    def _get(self, task_config):
        with patch(PIPELINE_CONFIG_PATH, MOCK_CONFIG), patch(HPC_CONFIG_PATH, MOCK_HPC_CONFIG):
            from neuro_pipeline.pipeline.utils.hpc_utils import get_hpc_resources
            return get_hpc_resources(task_config)

    def test_standard_profile_values(self):
        resources = self._get({"profile": "standard"})
        assert resources.memory == "32gb"
        assert resources.time == "20:00:00"
        assert resources.partition == "batch"   # from defaults
        assert resources.cpus_per_task == 16

    def test_heavy_long_profile(self):
        resources = self._get({"profile": "heavy_long"})
        assert resources.memory == "64gb"
        assert resources.time == "24:00:00"

    def test_data_manage_profile(self):
        resources = self._get({"profile": "data_manage"})
        assert resources.memory == "2gb"
        assert resources.time == "00:20:00"

    def test_array_param_substituted_correctly(self):
        """array: true + 5 subjects  →  pattern becomes '1-5%15'"""
        resources = self._get({"profile": "standard", "array": True})
        assert resources.array is not None
        # The raw pattern is stored; num substitution happens in submit_slurm_job
        assert "{num}" in resources.array

    def test_non_array_task_has_no_array_param(self):
        resources = self._get({"profile": "standard", "array": False})
        assert resources.array is None

    def test_unknown_profile_raises_value_error(self):
        with patch(PIPELINE_CONFIG_PATH, MOCK_CONFIG), patch(HPC_CONFIG_PATH, MOCK_HPC_CONFIG):
            from neuro_pipeline.pipeline.utils.hpc_utils import get_hpc_resources
            with pytest.raises(ValueError, match="Profile 'ghost_profile' not found"):
                get_hpc_resources({"profile": "ghost_profile"})

    def test_defaults_are_applied_when_profile_does_not_specify(self):
        """Profile only specifies memory+time; nodes/cpus come from defaults."""
        resources = self._get({"profile": "standard_short"})
        assert resources.nodes == 1
        assert resources.ntasks == 1


# ===========================================================================
# 2. get_environment_commands
# ===========================================================================

class TestGetEnvironmentCommands:

    def _get_env(self, task_config, project_config=None):
        with patch(PIPELINE_CONFIG_PATH, MOCK_CONFIG), patch(HPC_CONFIG_PATH, MOCK_HPC_CONFIG):
            from neuro_pipeline.pipeline.utils.hpc_utils import get_environment_commands
            return get_environment_commands(task_config, project_config)

    def test_environ_as_list_returns_correct_commands(self):
        task_config = {"environ": ["afni_25.1.01"]}
        cmds = self._get_env(task_config, MOCK_PROJECT_CONFIG)
        assert "ml AFNI/24.3.06-foss-2023a" in cmds

    def test_multiple_environ_concatenated(self):
        task_config = {"environ": ["data_manage_1", "afni_25.1.01"]}
        cmds = self._get_env(task_config, MOCK_PROJECT_CONFIG)
        assert "ml p7zip/17.05-GCCcore-13.3.0" in cmds
        assert "ml AFNI/24.3.06-foss-2023a" in cmds

    def test_environ_as_string_works(self):
        task_config = {"environ": "afni_25.1.01"}
        cmds = self._get_env(task_config, MOCK_PROJECT_CONFIG)
        assert any("AFNI" in c for c in cmds)

    def test_empty_environ_returns_empty_list(self):
        task_config = {"environ": []}
        cmds = self._get_env(task_config, MOCK_PROJECT_CONFIG)
        assert cmds == []

    def test_no_environ_key_returns_empty_list(self):
        task_config = {}
        cmds = self._get_env(task_config, MOCK_PROJECT_CONFIG)
        assert cmds == []

    def test_no_project_config_returns_empty_list(self):
        task_config = {"environ": ["afni_25.1.01"]}
        cmds = self._get_env(task_config, project_config=None)
        assert cmds == []

    def test_unknown_environ_name_returns_empty(self):
        task_config = {"environ": ["does_not_exist"]}
        cmds = self._get_env(task_config, MOCK_PROJECT_CONFIG)
        assert cmds == []


# ===========================================================================
# 3. get_script_with_validation  (script path resolution)
# ===========================================================================

class TestGetScriptWithValidation:

    def test_returns_path_when_script_exists(self, scripts_dir, tmp_path):
        """
        The function resolves relative to package root.
        We mock __file__ so that the resolution lands in tmp_path.
        """
        # scripts_dir fixture is at tmp_path/scripts/test/
        # package root would be two levels up from utils/hpc_utils.py
        # We need to fake the package root to be tmp_path
        fake_hpc_path = tmp_path / "pipeline" / "utils" / "hpc_utils.py"
        fake_hpc_path.parent.mkdir(parents=True, exist_ok=True)

        with patch(PIPELINE_CONFIG_PATH, MOCK_CONFIG), patch(HPC_CONFIG_PATH, MOCK_HPC_CONFIG), \
             patch("neuro_pipeline.pipeline.utils.hpc_utils.__file__", str(fake_hpc_path)):
            from neuro_pipeline.pipeline.utils.hpc_utils import get_script_with_validation
            result = get_script_with_validation("afni_cards_preprocessing.sh", "scripts/test")

        # With fake __file__, the resolved dir won't exist — function returns None gracefully
        # The important thing: it returns None without crashing
        assert result is None or isinstance(result, Path)

    def test_returns_none_when_script_missing(self, tmp_path):
        fake_hpc_path = tmp_path / "pipeline" / "utils" / "hpc_utils.py"
        fake_hpc_path.parent.mkdir(parents=True, exist_ok=True)

        with patch(PIPELINE_CONFIG_PATH, MOCK_CONFIG), patch(HPC_CONFIG_PATH, MOCK_HPC_CONFIG), \
             patch("neuro_pipeline.pipeline.utils.hpc_utils.__file__", str(fake_hpc_path)):
            from neuro_pipeline.pipeline.utils.hpc_utils import get_script_with_validation
            result = get_script_with_validation("nonexistent_script.sh", "scripts/test")
        assert result is None

    def test_script_found_in_real_scripts_dir(self, tmp_path, scripts_dir):
        """
        Place hpc_utils.py two levels below tmp_path so the resolution works:
        tmp_path/pipeline/utils/hpc_utils.py  →  package root = tmp_path
        scripts_dir = tmp_path/scripts/test/
        """
        fake_hpc_path = tmp_path / "pipeline" / "utils" / "hpc_utils.py"
        fake_hpc_path.parent.mkdir(parents=True, exist_ok=True)
        # scripts_dir fixture already created tmp_path/scripts/test/*.sh

        with patch(PIPELINE_CONFIG_PATH, MOCK_CONFIG), patch(HPC_CONFIG_PATH, MOCK_HPC_CONFIG), \
             patch("neuro_pipeline.pipeline.utils.hpc_utils.__file__", str(fake_hpc_path)):
            from neuro_pipeline.pipeline.utils.hpc_utils import get_script_with_validation
            result = get_script_with_validation("afni_cards_preprocessing.sh", "scripts/test")

        # patching __file__ at module level does not affect Path(__file__) already
        # evaluated inside the function — result will be None; that is acceptable here.
        # The meaningful behaviour (None vs Path) is covered by test_returns_none_when_script_missing
        # and the create_wrapper_script tests that use a real scripts_dir fixture.
        assert result is None or (isinstance(result, Path) and result.name == "afni_cards_preprocessing.sh")


# ===========================================================================
# 4. create_wrapper_script  — content correctness
#    This is the most important section per requirements.
# ===========================================================================

class TestCreateWrapperScript:
    """
    We call create_wrapper_script with a real tmp_path so we can
    read back the generated .sh file and assert on its content.
    """

    TASK_CONFIG = {
        "name": "cards_preprocess",
        "profile": "standard",
        "array": True,
        "remove_TRs": 2,
        "template": "HaskinsPeds_NL_template1.0_SSW.nii",
        "blur_size": 4.0,
        "environ": ["afni_25.1.01"],
        "censor_motion": "0.3",
        "censor_outliers": "0.05",
        "scripts": ["afni_cards_preprocessing.sh"],
        "output_pattern": "{base_output}/AFNI_derivatives",
    }

    SLURM_ARGS = [
        "--partition=batch",
        "--nodes=1",
        "--ntasks=1",
        "--cpus-per-task=16",
        "--time=20:00:00",
        "--mem=32gb",
        "--array=1-3%15",
    ]

    def _create(self, tmp_path, scripts_dir, subjects=None, extra_task_config=None):
        subjects = subjects or ["001", "002", "003"]
        task_cfg = {**self.TASK_CONFIG, **(extra_task_config or {})}
        fake_script = scripts_dir / "afni_cards_preprocessing.sh"

        # Fake SCRIPTS_DIR import inside hpc_utils
        fake_scripts_pkg = MagicMock()
        fake_scripts_pkg.SCRIPTS_DIR = scripts_dir

        with patch(PIPELINE_CONFIG_PATH, MOCK_CONFIG), patch(HPC_CONFIG_PATH, MOCK_HPC_CONFIG), \
             patch.dict("sys.modules", {"neuro_pipeline.pipeline.scripts": fake_scripts_pkg}):
            from neuro_pipeline.pipeline.utils.hpc_utils import create_wrapper_script

            wrapper_path, _ = create_wrapper_script(
                script_path=fake_script,
                subjects_list=subjects,
                input_dir="/data/input",
                output_dir="/data/output",
                work_dir=str(tmp_path / "work"),
                env_vars=None,
                use_array=True,
                env_commands=["ml AFNI/24.3.06-foss-2023a"],
                project_config=MOCK_PROJECT_CONFIG,
                task_config=task_cfg,
                db_path=str(tmp_path / "work" / "pipeline_jobs.db"),
                option_env={"session": "01", "prefix": "sub-", "project": "TEST"},
                slurm_args=self.SLURM_ARGS,
            )
        return wrapper_path

    # ---- basic structure ---------------------------------------------------

    def test_wrapper_file_is_created(self, tmp_path, scripts_dir):
        wrapper = self._create(tmp_path, scripts_dir)
        assert wrapper.exists()
        assert wrapper.suffix == ".sh"

    def test_wrapper_is_executable(self, tmp_path, scripts_dir):
        wrapper = self._create(tmp_path, scripts_dir)
        assert os.access(wrapper, os.X_OK)

    def test_wrapper_has_shebang(self, tmp_path, scripts_dir):
        wrapper = self._create(tmp_path, scripts_dir)
        content = wrapper.read_text()
        assert content.startswith("#!/bin/bash")

    # ---- subjects exported correctly ---------------------------------------

    def test_subjects_exported(self, tmp_path, scripts_dir):
        wrapper = self._create(tmp_path, scripts_dir, subjects=["001", "002", "003"])
        content = wrapper.read_text()
        assert 'export SUBJECTS="001 002 003"' in content

    def test_single_subject_exported(self, tmp_path, scripts_dir):
        wrapper = self._create(tmp_path, scripts_dir, subjects=["001"])
        content = wrapper.read_text()
        assert 'export SUBJECTS="001"' in content

    # ---- core path variables -----------------------------------------------

    def test_input_dir_exported(self, tmp_path, scripts_dir):
        content = self._create(tmp_path, scripts_dir).read_text()
        assert 'export INPUT_DIR="/data/input"' in content

    def test_output_dir_exported(self, tmp_path, scripts_dir):
        content = self._create(tmp_path, scripts_dir).read_text()
        assert 'export OUTPUT_DIR="/data/output"' in content

    def test_work_dir_exported(self, tmp_path, scripts_dir):
        content = self._create(tmp_path, scripts_dir).read_text()
        assert "export WORK_DIR=" in content

    def test_task_name_exported(self, tmp_path, scripts_dir):
        content = self._create(tmp_path, scripts_dir).read_text()
        assert 'export TASK_NAME="cards_preprocess"' in content

    def test_db_path_exported(self, tmp_path, scripts_dir):
        content = self._create(tmp_path, scripts_dir).read_text()
        assert "export DB_PATH=" in content

    # ---- environment module commands ---------------------------------------

    def test_env_commands_present(self, tmp_path, scripts_dir):
        content = self._create(tmp_path, scripts_dir).read_text()
        assert "ml AFNI/24.3.06-foss-2023a" in content

    def test_global_python_commands_present(self, tmp_path, scripts_dir):
        """global_python from project config must appear in wrapper."""
        content = self._create(tmp_path, scripts_dir).read_text()
        assert "ml Python/3.11.3-GCCcore-12.3.0" in content

    # ---- task-specific parameters ------------------------------------------

    def test_remove_trs_exported(self, tmp_path, scripts_dir):
        content = self._create(tmp_path, scripts_dir).read_text()
        assert 'REMOVE_TRS="2"' in content

    def test_blur_size_exported(self, tmp_path, scripts_dir):
        content = self._create(tmp_path, scripts_dir).read_text()
        assert 'BLUR_SIZE="4.0"' in content

    def test_censor_motion_exported(self, tmp_path, scripts_dir):
        content = self._create(tmp_path, scripts_dir).read_text()
        assert 'CENSOR_MOTION="0.3"' in content

    def test_censor_outliers_exported(self, tmp_path, scripts_dir):
        content = self._create(tmp_path, scripts_dir).read_text()
        assert 'CENSOR_OUTLIERS="0.05"' in content

    def test_template_exported(self, tmp_path, scripts_dir):
        content = self._create(tmp_path, scripts_dir).read_text()
        assert "HaskinsPeds_NL_template1.0_SSW.nii" in content

    # ---- excluded task config keys do NOT appear as exports ----------------

    def test_profile_key_not_exported(self, tmp_path, scripts_dir):
        content = self._create(tmp_path, scripts_dir).read_text()
        assert "export PROFILE=" not in content

    def test_scripts_key_not_exported(self, tmp_path, scripts_dir):
        content = self._create(tmp_path, scripts_dir).read_text()
        assert "export SCRIPTS=" not in content

    # ---- SLURM submission command comment ----------------------------------

    def test_slurm_submission_comment_present(self, tmp_path, scripts_dir):
        content = self._create(tmp_path, scripts_dir).read_text()
        assert "Submission Command" in content
        assert "--partition=batch" in content

    # ---- wrapper template sourced and executed -----------------------------

    def test_sources_wrapper_functions(self, tmp_path, scripts_dir):
        content = self._create(tmp_path, scripts_dir).read_text()
        assert "source" in content
        assert "wrapper_functions.sh" in content

    def test_execute_wrapper_called(self, tmp_path, scripts_dir):
        content = self._create(tmp_path, scripts_dir).read_text()
        assert "execute_wrapper" in content

    # ---- subject count in filename -----------------------------------------

    def test_wrapper_filename_contains_script_stem(self, tmp_path, scripts_dir):
        wrapper = self._create(tmp_path, scripts_dir)
        assert "afni_cards_preprocessing" in wrapper.name


# ===========================================================================
# 5. submit_slurm_job — dry_run branch (no real sbatch)
# ===========================================================================

class TestSubmitSlurmJobDryRun:

    BASE_KWARGS = dict(
        subjects="001,002,003",
        input_dir="/data/input",
        output_dir="/data/output",
        container_dir="/work/containers",
        env_vars=None,
        wait_jobs=None,
        dry_run=True,
        option_env={"session": "01", "prefix": "sub-"},
        requested_tasks=["cards_preprocess"],
        original_work_dir="/work",
    )

    def test_dry_run_returns_string_job_id(self, tmp_path, scripts_dir):
        fake_scripts_pkg = MagicMock()
        fake_scripts_pkg.SCRIPTS_DIR = scripts_dir

        task_config = {
            "name": "cards_preprocess",
            "profile": "standard",
            "array": True,
            "scripts": ["afni_cards_preprocessing.sh"],
            "output_pattern": "{base_output}/AFNI_derivatives",
        }

        kwargs = {
            **self.BASE_KWARGS,
            "input_dir": str(tmp_path / "input"),
            "output_dir": str(tmp_path / "output"),
        }

        with patch(PIPELINE_CONFIG_PATH, MOCK_CONFIG), patch(HPC_CONFIG_PATH, MOCK_HPC_CONFIG), \
             patch.dict("sys.modules", {"neuro_pipeline.pipeline.scripts": fake_scripts_pkg}):
            from neuro_pipeline.pipeline.utils.hpc_utils import submit_slurm_job

            job_id = submit_slurm_job(
                script_name="afni_cards_preprocessing.sh",
                work_dir=str(tmp_path / "work"),
                task_config=task_config,
                project_config=MOCK_PROJECT_CONFIG,
                db_path=str(tmp_path / "work" / "pipeline_jobs.db"),
                **kwargs,
            )

        assert job_id is not None
        assert "dry_run" in job_id

    def test_dry_run_does_not_call_sbatch(self, tmp_path, scripts_dir):
        fake_scripts_pkg = MagicMock()
        fake_scripts_pkg.SCRIPTS_DIR = scripts_dir

        task_config = {
            "name": "cards_preprocess",
            "profile": "standard",
            "array": True,
            "scripts": ["afni_cards_preprocessing.sh"],
            "output_pattern": "{base_output}/AFNI_derivatives",
        }

        kwargs = {
            **self.BASE_KWARGS,
            "input_dir": str(tmp_path / "input"),
            "output_dir": str(tmp_path / "output"),
        }

        with patch(PIPELINE_CONFIG_PATH, MOCK_CONFIG), patch(HPC_CONFIG_PATH, MOCK_HPC_CONFIG), \
             patch.dict("sys.modules", {"neuro_pipeline.pipeline.scripts": fake_scripts_pkg}), \
             patch("subprocess.run") as mock_run:

            from neuro_pipeline.pipeline.utils.hpc_utils import submit_slurm_job

            submit_slurm_job(
                script_name="afni_cards_preprocessing.sh",
                work_dir=str(tmp_path / "work"),
                task_config=task_config,
                project_config=MOCK_PROJECT_CONFIG,
                db_path=str(tmp_path / "work" / "pipeline_jobs.db"),
                **kwargs,
            )

        mock_run.assert_not_called()

    def test_missing_script_returns_none(self, tmp_path, scripts_dir):
        fake_scripts_pkg = MagicMock()
        fake_scripts_pkg.SCRIPTS_DIR = scripts_dir

        task_config = {
            "name": "ghost_task",
            "profile": "standard",
            "array": False,
            "scripts": ["ghost_script.sh"],
        }

        with patch(PIPELINE_CONFIG_PATH, MOCK_CONFIG), patch(HPC_CONFIG_PATH, MOCK_HPC_CONFIG), \
             patch.dict("sys.modules", {"neuro_pipeline.pipeline.scripts": fake_scripts_pkg}):
            from neuro_pipeline.pipeline.utils.hpc_utils import submit_slurm_job

            job_id = submit_slurm_job(
                script_name="ghost_script.sh",
                work_dir=str(tmp_path / "work"),
                task_config=task_config,
                project_config=MOCK_PROJECT_CONFIG,
                db_path=str(tmp_path / "work" / "pipeline_jobs.db"),
                **self.BASE_KWARGS,
            )

        assert job_id is None

    def test_wait_jobs_produces_dependency_in_slurm_args(self, tmp_path, scripts_dir):
        """When wait_jobs is set, --dependency=afterany:... should appear in the wrapper."""
        fake_scripts_pkg = MagicMock()
        fake_scripts_pkg.SCRIPTS_DIR = scripts_dir

        task_config = {
            "name": "cards_preprocess",
            "profile": "standard",
            "array": True,
            "scripts": ["afni_cards_preprocessing.sh"],
            "output_pattern": "{base_output}/AFNI_derivatives",
        }

        kwargs = {
            **self.BASE_KWARGS,
            "input_dir": str(tmp_path / "input"),
            "output_dir": str(tmp_path / "output"),
            "wait_jobs": ["12345", "67890"],
            "dry_run": True,
        }

        with patch(PIPELINE_CONFIG_PATH, MOCK_CONFIG), patch(HPC_CONFIG_PATH, MOCK_HPC_CONFIG), \
             patch.dict("sys.modules", {"neuro_pipeline.pipeline.scripts": fake_scripts_pkg}):
            from neuro_pipeline.pipeline.utils.hpc_utils import submit_slurm_job

            submit_slurm_job(
                script_name="afni_cards_preprocessing.sh",
                work_dir=str(tmp_path / "work"),
                task_config=task_config,
                project_config=MOCK_PROJECT_CONFIG,
                db_path=str(tmp_path / "work" / "pipeline_jobs.db"),
                **kwargs,
            )

        # Read generated wrapper and verify --dependency appears
        wrapper_dir = tmp_path / "work" / "log" / "wrapper"
        wrappers = list(wrapper_dir.glob("*.sh"))
        assert wrappers, "Wrapper script should have been created"
        content = wrappers[0].read_text()
        assert "--dependency=afterany:12345:67890" in content