#!/usr/bin/env python3

import argparse
import yaml
from pathlib import Path

def generate_project_config(project_name: str, output_dir: str = "./config/project_config"):
    config_template = {
        "prefix": "sub-",
        
        "database": {
            "db_path": "$WORK_DIR/log/pipeline_jobs.db",
            "include_project_name": True
        },
        
        "envir_dir": {
            "container_dir": "",
            "virtual_envir": "",
            "template_dir": "",
            "atlas_dir": "",
            "freesurfer_dir": "",
            "config_dir": "",
            "stimulus_dir": ""
        },
        
        "global_python": [
            "",
            ""
        ],
        
        "modules": {
            "afni_25.1.01": [""],
            "fsl_6.0.7.14": [""],
            "freesurfer_7.4.1": [""],
            "data_manage_1": [""]
        },
        
        "tasks": {
            "unzip":             {"environ": ["data_manage_1", "afni_25.1.01"]},
            "recon_bids":        {"container": "dcm2bids_3.2.0.sif", "config": "config.json"},
            "afni_volume":       {"environ": ["afni_25.1.01"], "template": ""},
            "rest_preprocess":   {"remove_TRs": 6, "template": "MNI152NLin2009cAsym", "container": "fmriprep_25.1.3.sif", "license": "license.txt"},
            "rest_post":         {"remove_TRs": 6, "template": "MNI152NLin2009cAsym", "container": "xcp_d-0.11.0rc1.sif", "rest_mode": "abcd", "motion_filter_type": "notch", "band_stop_min": "15", "band_stop_max": "25", "nuisance_regressors": "36P", "license": "license.txt"},
            "cards_preprocess":  {"remove_TRs": 2, "template": "", "blur_size": 4.0, "environ": ["afni_25.1.01"], "censor_motion": "0.3", "censor_outliers": "0.05"},
            "kidvid_preprocess": {"remove_TRs": 22, "template": "", "blur_size": 4.0, "environ": ["afni_25.1.01"], "censor_motion": "0.3", "censor_outliers": "0.05"},
            "mriqc_preprocess":  {"container": "mriqc_24.0.2.sif"},
            "mriqc_post":        {"container": "mriqc_24.0.2.sif"},
        }
    }
    
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    config_file = Path(output_dir) / f"{project_name}_config.yaml"
    
    with open(config_file, 'w', encoding='utf-8') as f:
        yaml.dump(config_template, f, default_flow_style=False, indent=2, sort_keys=False)
    
    print(f"Configuration generated: {config_file}")

def main():
    parser = argparse.ArgumentParser(description="Generate project configuration yaml file")
    parser.add_argument("project_name", type=str, help="Project name (e.g., branch, study1)")
    parser.add_argument("--output-dir", type=str, default="./config/project_config", help="Output directory")
    args = parser.parse_args()

    generate_project_config(args.project_name, args.output_dir)

if __name__ == "__main__":
    main()