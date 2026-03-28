"""
conftest.py — Shared fixtures for all test modules

Assumed package layout:
    neuro_pipeline/
        pipeline/
            core.py
            dag.py
            config/
                config.yaml
            utils/
                config_utils.py
                hpc_utils.py
                detect_subjects.py
                job_db.py
        tests/
            conftest.py
            test_config_utils.py
            test_dag.py
            test_hpc_utils.py
"""

import pytest
import yaml
from pathlib import Path
from unittest.mock import MagicMock, patch


# ---------------------------------------------------------------------------
# Minimal in-memory config that mirrors config.yaml structure
# ---------------------------------------------------------------------------

MOCK_CONFIG = {
    "defaults": {
        "partition": "batch",
        "nodes": 1,
        "ntasks": 1,
        "cpus_per_task": 16,
    },
    "resource_profiles": {
        "data_manage":    {"memory": "2gb",  "time": "00:20:00"},
        "light_short":    {"memory": "16gb", "time": "04:00:00"},
        "standard":       {"memory": "32gb", "time": "20:00:00"},
        "standard_short": {"memory": "32gb", "time": "08:00:00"},
        "heavy_long":     {"memory": "64gb", "time": "24:00:00"},
    },
    "tasks": {
        "prep": [
            {
                "name": "unzip",
                "profile": "standard",
                "scripts": ["unzip_rename.sh"],
                "output_pattern": "{base_output}/raw",
            },
            {
                "name": "recon_bids",
                "profile": "light_short",
                "array": True,
                "scripts": ["dcm2bids_convert_BIDS.sh"],
                "input_from": "unzip",
                "output_pattern": "{base_output}/BIDS",
            },
        ],
        "structural": [
            {
                "name": "afni_volume",
                "profile": "standard_short",
                "array": True,
                "input_from": "recon_bids",
                "scripts": ["sswarp_scratch.sh"],
                "output_pattern": "{base_output}/AFNI_derivatives",
            },
        ],
        "rest_fmriprep": [
            {
                "name": "rest_fmriprep_preprocess",
                "profile": "heavy_long",
                "array": True,
                "input_from": "recon_bids",
                "scripts": ["fmriprep_rs.sh"],
                "output_pattern": "{base_output}/BIDS_derivatives/fmriprep",
            },
            {
                "name": "rest_fmriprep_post_fc",
                "profile": "standard_short",
                "array": True,
                "input_from": "rest_fmriprep_preprocess",
                "scripts": ["xcpd_rs.sh"],
                "output_pattern": "{base_output}/BIDS_derivatives/xcpd",
            },
        ],
        "task_afni": [
            {
                "name": "cards_preprocess",
                "profile": "standard",
                "array": True,
                "input_from": "recon_bids",
                "scripts": ["afni_cards_preprocessing.sh"],
                "output_pattern": "{base_output}/AFNI_derivatives",
            },
            {
                "name": "kidvid_preprocess",
                "profile": "standard",
                "array": True,
                "input_from": "recon_bids",
                "scripts": ["afni_kidvid_preprocess.sh"],
                "output_pattern": "{base_output}/AFNI_derivatives",
            },
        ],
        "qc": [
            {
                "name": "mriqc_individual",
                "profile": "heavy_long",
                "array": True,
                "input_from": "recon_bids",
                "scripts": ["mriqc_individual.sh"],
                "output_pattern": "{base_output}/quality_control/mriqc",
            },
            {
                "name": "mriqc_group",
                "profile": "light_short",
                "input_from": "recon_bids",
                "scripts": ["mriqc_group.sh"],
                "output_pattern": "{base_output}/quality_control/mriqc",
            },
        ],
    },
    "array_config": {
        "pattern": "1-{num}%15",
    },
}

# Minimal project config (mirrors test_config.yaml)
MOCK_PROJECT_CONFIG = {
    "prefix": "sub-",
    "scripts_dir": "scripts/test",
    "database": {
        "db_path": "$WORK_DIR/database/pipeline_jobs.db",
    },
    "envir_dir": {
        "container_dir": "/work/cglab/containers",
        "virtual_envir": "/work/cglab/conda_env",
        "template_dir": "/work/cglab/projects/BRANCH/all_data/for_AFNI/",
        "atlas_dir": "/work/cglab/projects/BRANCH/all_data/for_AFNI/",
        "freesurfer_dir": "/work/cglab/containers/.licenses/freesurfer",
        "config_dir": "/work/cglab/conda_env/config_for_BIDS",
        "stimulus_dir": "/work/cglab/projects/BRANCH/all_data/for_AFNI/processing_scripts",
    },
    "global_python": [
        "ml Python/3.11.3-GCCcore-12.3.0",
        ". /home/$USER/virtual_environ/neuro_pipeline/bin/activate",
    ],
    "modules": {
        "afni_25.1.01": [
            "ml Flask/2.3.3-GCCcore-12.3.0",
            "ml netpbm/10.73.43-GCC-12.3.0",
            "ml AFNI/24.3.06-foss-2023a",
        ],
        "fsl_6.0.7.14": [
            "ml FSL/6.0.7.14-foss-2023a",
            '[ -n "$FSLDIR" ] && source ${FSLDIR}/etc/fslconf/fsl.sh',
        ],
        "data_manage_1": [
            "ml p7zip/17.05-GCCcore-13.3.0",
            "ml parallel/20240722-GCCcore-13.3.0",
        ],
    },
    "setup": {
        "prep": [
            {"name": "unzip", "environ": ["data_manage_1", "afni_25.1.01"]},
            {"name": "recon_bids", "container": "dcm2bids_3.2.0.sif", "config": "branch_config.json"},
            {"name": "afni_volume", "environ": ["afni_25.1.01"], "template": "HaskinsPeds_NL_template1.0_SSW.nii"},
        ],
        "rest_fmriprep": [
            {
                "name": "rest_fmriprep_preprocess",
                "remove_TRs": 6,
                "template": "MNI152NLin2009cAsym",
                "container": "fmriprep_25.1.3.sif",
                "license": "license.txt",
            },
            {
                "name": "rest_fmriprep_post_fc",
                "remove_TRs": 6,
                "template": "MNI152NLin2009cAsym",
                "container": "xcp_d-0.11.0rc1.sif",
                "rest_mode": "abcd",
                "nuisance_regressors": "36P",
                "license": "license.txt",
            },
        ],
        "task_afni": [
            {
                "name": "cards_preprocess",
                "remove_TRs": 2,
                "template": "HaskinsPeds_NL_template1.0_SSW.nii",
                "blur_size": 4.0,
                "environ": ["afni_25.1.01"],
                "censor_motion": "0.3",
                "censor_outliers": "0.05",
            },
            {
                "name": "kidvid_preprocess",
                "remove_TRs": 22,
                "template": "HaskinsPeds_NL_template1.0_SSW.nii",
                "blur_size": 4.0,
                "environ": ["afni_25.1.01"],
                "censor_motion": "0.3",
                "censor_outliers": "0.05",
            },
        ],
        "qc": [
            {"name": "mriqc_individual", "container": "mriqc_24.0.2.sif"},
            {"name": "mriqc_group",      "container": "mriqc_24.0.2.sif"},
        ],
    },
}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_config():
    """Return a copy of the in-memory global config."""
    return MOCK_CONFIG.copy()


@pytest.fixture
def mock_project_config():
    """Return a copy of the in-memory project config."""
    return MOCK_PROJECT_CONFIG.copy()


@pytest.fixture
def config_yaml_file(tmp_path):
    """Write MOCK_CONFIG to a real YAML file and return its Path."""
    cfg_file = tmp_path / "config.yaml"
    with open(cfg_file, "w") as f:
        yaml.dump(MOCK_CONFIG, f)
    return cfg_file


@pytest.fixture
def scripts_dir(tmp_path):
    """
    Create a fake scripts directory pre-populated with the shell scripts
    referenced in MOCK_CONFIG so path-resolution tests can pass without
    touching the real filesystem.
    """
    s_dir = tmp_path / "scripts" / "test"
    s_dir.mkdir(parents=True)
    script_names = [
        "unzip_rename.sh",
        "dcm2bids_convert_BIDS.sh",
        "sswarp_scratch.sh",
        "fmriprep_rs.sh",
        "xcpd_rs.sh",
        "afni_cards_preprocessing.sh",
        "afni_kidvid_preprocess.sh",
        "mriqc_individual.sh",
        "mriqc_group.sh",
    ]
    for name in script_names:
        (s_dir / name).write_text("#!/bin/bash\necho mock script\n")
    return s_dir


@pytest.fixture
def work_dir(tmp_path):
    """Return a temporary work directory."""
    d = tmp_path / "work"
    d.mkdir()
    return d


@pytest.fixture
def output_dir(tmp_path):
    """Return a temporary output directory."""
    d = tmp_path / "output"
    d.mkdir()
    return d


@pytest.fixture
def input_dir(tmp_path):
    """Return a temporary input directory with some fake subject folders."""
    d = tmp_path / "input"
    d.mkdir()
    for sub in ["sub-001", "sub-002", "sub-003"]:
        (d / sub).mkdir()
    (d / "not_a_subject.txt").write_text("ignore me")
    return d
