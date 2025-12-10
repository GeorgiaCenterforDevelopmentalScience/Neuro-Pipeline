import sys
import os
import subprocess
import time
from pathlib import Path
from typing import Dict, Any, List, Optional
import typer
import yaml

# Load global configuration
config_path = Path(__file__).parent.parent / "config" / "config.yaml"

try:
    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
except FileNotFoundError:
    raise FileNotFoundError(
        f"config.yaml not found at {config_path}"
    )

from dataclasses import dataclass

@dataclass
class HPCResources:
    """HPC resource configuration for a job"""
    
    partition: str
    nodes: int
    ntasks: int
    cpus_per_task: int
    memory: str
    time: str
    memory_per_cpu: Optional[str] = None
    array: Optional[str] = None
    additional_args: Optional[List[str]] = None
    
    def __post_init__(self):
        if self.additional_args is None:
            self.additional_args = []

def get_hpc_resources(task_config: Dict[str, Any]) -> HPCResources:
    """Get HPC resource configuration from task config and global settings"""
    
    defaults = config.get('defaults', {})
    profile_name = task_config.get('profile', 'standard')
    profile_config = config.get('resource_profiles', {}).get(profile_name, {})
    
    if not profile_config:
        available = ', '.join(config.get('resource_profiles', {}).keys())
        raise ValueError(f"Profile '{profile_name}' not found. Available: {available}")
    
    merged_config = {**defaults, **profile_config}
    
    array_param = None
    if task_config.get('array', False):
        array_config = config.get('array_config', {})
        array_param = array_config.get('pattern', '1-{num}%15')
    
    return HPCResources(
        partition=merged_config['partition'],
        nodes=merged_config['nodes'],
        ntasks=merged_config['ntasks'],
        cpus_per_task=merged_config['cpus_per_task'],
        memory=merged_config['memory'],
        memory_per_cpu=merged_config.get('memory_per_cpu'),
        time=merged_config['time'],
        array=array_param,
        additional_args=merged_config.get('additional_args', [])
    )

def get_environment_commands(task_config: Dict[str, Any], project_config: Dict[str, Any] = None) -> List[str]:
    """Get environment setup commands from task and project configuration"""
    env_commands = []
    environ_names = task_config.get('environ', [])
    
    if isinstance(environ_names, str):
        environ_names = [environ_names]
    elif not isinstance(environ_names, list):
        environ_names = []
    
    modules = {}
    if project_config and 'modules' in project_config:
        modules = project_config['modules']
    
    for env_name in environ_names:
        if env_name in modules:
            env_commands.extend(modules[env_name])
    
    return env_commands

def submit_slurm_job(
    script_name: str,
    subjects: str,
    input_dir: str,
    output_dir: str,
    work_dir: str,
    container_dir: str,
    env_vars: Optional[Dict[str, str]] = None,
    wait_jobs: Optional[List[str]] = None,
    task_config: Optional[Dict[str, Any]] = None,
    dry_run: bool = False,
    option_env: Optional[Dict[str, str]] = None,
    project_config: Optional[Dict[str, Any]] = None,
    requested_tasks: Optional[List[str]] = None,
    original_work_dir: Optional[str] = None,
    db_path: Optional[str] = None
) -> Optional[str]:
    """Submit a SLURM job for the given script and subjects"""

    # Locate script
    from ..scripts import SCRIPTS_DIR
    script_path = Path(SCRIPTS_DIR) / script_name

    if task_config:
        resources = get_hpc_resources(task_config)
        env_commands = get_environment_commands(task_config, project_config=project_config)
    else:
        default_task_config = {'profile': 'standard', 'array': False}
        resources = get_hpc_resources(default_task_config)
        env_commands = []


    # TODO: MOVE TO DAG?
    # Handle input_from dependencies
    actual_input_dir = input_dir
    if task_config and 'input_from' in task_config:
        input_from = task_config['input_from']
        dependency_mapping = {
            'unzip': 'unzip',
            'recon_bids': 'recon_bids',
            'mriqc': 'mriqc_individual',
            'mriqc_individual': 'mriqc_individual',
            'rest_fmriprep_preprocess': 'rest_fmriprep_preprocess',
            'rest_fmriprep_post_fc': 'rest_fmriprep_post_fc'
        }
        
        dep_task = dependency_mapping.get(input_from)
        if dep_task and requested_tasks and dep_task in requested_tasks:
            if input_from == 'unzip':
                actual_input_dir = f"{output_dir}/raw"
            elif input_from == 'recon_bids':
                actual_input_dir = f"{output_dir}/BIDS"
            elif input_from == 'mriqc':
                actual_input_dir = f"{output_dir}/quality_control/mriqc"
            elif input_from == 'rest_fmriprep_preprocess':
                actual_input_dir = f"{output_dir}/BIDS_derivatives/fmriprep"
            elif input_from == 'rest_fmriprep_post_fc':
                actual_input_dir = f"{output_dir}/BIDS_derivatives/xcpd"

    # Create directories
    Path(work_dir).mkdir(parents=True, exist_ok=True)
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    # Setup database path
    if not db_path:
        db_path = str(Path(work_dir) / "log" / "pipeline_jobs.db")
    
    # Handle output pattern
    if task_config and 'output_pattern' in task_config:
        output_pattern = task_config['output_pattern']
        actual_output_dir = output_pattern.format(base_output=output_dir)
    else:
        actual_output_dir = output_dir
    
    # Create subject directories (only for array jobs)
    subjects_dir = Path(work_dir) / "log" / "subjects"
    subjects_dir.mkdir(parents=True, exist_ok=True)
    
    # Parse subjects
    subjects_list = []
    subjects_path = Path(subjects)
    if subjects_path.is_file():
        with open(subjects_path, 'r') as f:
            subjects_list = [line.strip() for line in f if line.strip()]
    else:
        subjects_list = [s.strip() for s in subjects.split(',') if s.strip()]
    
    if not subjects_list:
        typer.echo("Error: No subjects provided", err=True)
        return None

    # Create subject directories (only for array jobs)
    is_array_job = task_config and 'array' in task_config and task_config['array']
    if is_array_job:
        for subject in subjects_list:
            subject_dir = subjects_dir / f"sub-{subject}"
            subject_dir.mkdir(parents=True, exist_ok=True)

    # Setup array parameter
    if is_array_job:
        array_param = resources.array
        if array_param and '{num}' in array_param:
            array_param = array_param.replace('{num}', str(len(subjects_list)))
    else:
        array_param = None
    
    num_subjects = len(subjects_list)
    subjects_array_str = " ".join(subjects_list)
    
    # Get task name for log directory
    task_name = task_config.get('name', script_path.stem) if task_config else script_path.stem
    
    # Setup log paths - always use task-specific directory
    log_dir = Path(work_dir) / "log"
    task_log_dir = log_dir / task_name
    task_log_dir.mkdir(parents=True, exist_ok=True)
    
    if is_array_job:
        slurm_output = f"{task_log_dir}/{task_name}_%A-%a.out"
        slurm_error = f"{task_log_dir}/{task_name}_%A-%a.err"
    else:
        slurm_output = f"{task_log_dir}/{task_name}_%A.out"
        slurm_error = f"{task_log_dir}/{task_name}_%A.err"
        
    # Build SLURM arguments
    slurm_args = [
        f"--partition={resources.partition}",
        f"--nodes={resources.nodes}",
        f"--ntasks={resources.ntasks}",
        f"--cpus-per-task={resources.cpus_per_task}",
        f"--time={resources.time}",
        f"--job-name={script_path.stem}",
        f"--output={slurm_output}",
        f"--error={slurm_error}"
    ]

    if resources.memory_per_cpu:
        slurm_args.append(f"--mem-per-cpu={resources.memory_per_cpu}")
    else:
        slurm_args.append(f"--mem={resources.memory}")
    if array_param:
        slurm_args.append(f"--array={array_param}")
    if resources.additional_args:
        slurm_args.extend(resources.additional_args)
    if wait_jobs:
        dependency = "afterany:" + ":".join(wait_jobs)
        slurm_args.append(f"--dependency={dependency}")

    # Setup environment exports
    env_exports = []
    if env_vars:
        for k, v in env_vars.items():
            env_exports.append(f"{k}={v}")

    if option_env:
        for k, v in option_env.items():
            if v is not None:
                env_exports.append(f"{k.upper()}={v}")

    env_exports.extend([
        f"SUBJECTS_ARRAY=({subjects_array_str})",
        f"NUM_SUBJECTS={num_subjects}",
        f"INPUT_DIR={actual_input_dir}",
        f"OUTPUT_DIR={actual_output_dir}",
        f"WORK_DIR={work_dir}",
        f"CONTAINER_DIR={container_dir}"
    ])

    # Create wrapper script
    wrapper_script = create_wrapper_script(
        script_path=script_path,
        subjects_list=subjects_list,
        input_dir=actual_input_dir,
        output_dir=actual_output_dir,
        work_dir=work_dir,
        env_vars=env_vars,
        use_array=bool(array_param),
        env_commands=env_commands,
        project_config=project_config,
        task_config=task_config,
        db_path=str(db_path),
        option_env=option_env,
        slurm_args=slurm_args
    )

    cmd = ["sbatch"] + slurm_args + [str(wrapper_script)]

    # Dry run mode
    if dry_run:
        return f"dry_run_{script_path.stem}"

    # Submit actual job
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        job_id = result.stdout.strip().split()[-1]
        typer.echo(f"Job submitted: {job_id}")
        return job_id
    except subprocess.CalledProcessError as e:
        typer.echo(f"Job submission failed: {e}", err=True)
        if e.stdout:
            typer.echo(f"STDOUT: {e.stdout}", err=True)
        if e.stderr:
            typer.echo(f"STDERR: {e.stderr}", err=True)
        return None


def create_wrapper_script( 
    script_path: Path,
    subjects_list: List[str],
    input_dir: str,
    output_dir: str,
    work_dir: str,
    env_vars: Optional[Dict[str, str]] = None,
    use_array: bool = True,
    env_commands: Optional[List[str]] = None,
    project_config: Optional[Dict[str, Any]] = None,
    task_config: Optional[Dict[str, Any]] = None,
    db_path: Optional[str] = None,
    option_env: Optional[Dict[str, str]] = None,
    slurm_args: Optional[List[str]] = None
) -> Path:
    """Generate minimal wrapper script that calls bash template"""

    wrapper_dir = Path(work_dir) / "log" / "wrapper"
    wrapper_dir.mkdir(parents=True, exist_ok=True)
    
    script_name = script_path.stem
    timestamp = int(time.time())
    wrapper_filename = f"{script_name}_{timestamp}_wrapper.sh"
    wrapper_path = wrapper_dir / wrapper_filename
    
    # Prepare environment commands
    env_commands_str = ""
    if env_commands:
        env_commands_str = "\n".join(env_commands)
    
    # Prepare global Python commands
    global_python_str = ""
    if project_config:
        global_python = project_config['project'].get('global_python', [])
        if global_python:
            global_python_str = "\n".join(global_python)
    
    # Prepare global environment variables
    global_env_vars = {}
    envir_dir = project_config['project'].get('envir_dir') if project_config else None
    if envir_dir:
        global_env_vars.update(envir_dir)
    
    if option_env:
        for key, value in option_env.items():
            if value is not None and not key.startswith('envir_dir_'):
                global_env_vars[key] = value
    
    global_env_str = ""
    if global_env_vars:
        global_env_str = "\n".join([f'export {k.upper()}="{v}"' for k, v in global_env_vars.items()])
    
    # Prepare task parameters
    task_params_str = ""
    if task_config:
        excluded_keys = {'name', 'environ', 'input_from', 'scripts', 'profile', 'array', 'output_pattern'}
        task_params = []
        for key, value in task_config.items():
            if key in excluded_keys:
                continue
            if isinstance(value, (str, int, float)):
                task_params.append(f'export {key.upper()}="{value}"')
            elif isinstance(value, list):
                task_params.append(f'export {key.upper()}="{" ".join(map(str, value))}"')
        task_params_str = "\n".join(task_params)
    
    # Get task name
    task_name = task_config.get('name', script_name) if task_config else script_name
    
    # Setup database path
    if not db_path:
        db_path = str(Path(work_dir) / "log" / "pipeline_jobs.db")
    
    # Get the correct script directory
    from ..scripts import SCRIPTS_DIR
    pipeline_root = SCRIPTS_DIR.parent
    
    # Write minimal wrapper script
    with open(wrapper_path, 'w') as f:
        f.write("#!/bin/bash\n\n")
        f.write("# Auto-generated wrapper script\n")
        f.write(f"# Generated at: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"# Original script: {script_path.resolve()}\n")
        f.write(f"# Subjects: {', '.join(subjects_list[:5])}{'...' if len(subjects_list) > 5 else ''}\n")
        f.write(f"# Number of subjects: {len(subjects_list)}\n")
        f.write(f"# Array job: {'Yes' if use_array else 'No'}\n")
        
        # ADD SLURM SUBMISSION COMMAND
        if slurm_args:
            f.write("#\n")
            f.write("# SLURM Submission Command:\n")
            f.write(f"# sbatch {' '.join(slurm_args)} {wrapper_path}\n")
        
        f.write("\n")
        
        # Export all configuration as environment variables
        f.write("# Basic paths and configuration\n")
        f.write(f'export SUBJECTS="{" ".join(subjects_list)}"\n')
        f.write(f'export INPUT_DIR="{input_dir}"\n')
        f.write(f'export OUTPUT_DIR="{output_dir}"\n')
        f.write(f'export WORK_DIR="{work_dir}"\n')
        f.write(f'export LOG_DIR="{work_dir}/log"\n')
        f.write(f'export DB_PATH="{db_path}"\n')
        f.write(f'export TASK_NAME="{task_name}"\n')
        f.write(f'export SCRIPT_DIR="{pipeline_root}"\n')
        f.write("\n")
        
        # Export command strings if present
        if global_python_str:
            f.write("# Global Python environment commands\n")
            f.write(f'export GLOBAL_PYTHON_COMMANDS=$(cat << "PYTHON_EOF"\n')
            f.write(global_python_str + "\n")
            f.write("PYTHON_EOF\n)\n\n")
        
        if env_commands_str:
            f.write("# Environment module commands\n")
            f.write(f'export ENV_COMMANDS=$(cat << "ENV_EOF"\n')
            f.write(env_commands_str + "\n")
            f.write("ENV_EOF\n)\n\n")
        
        if global_env_str:
            f.write("# Global environment variables\n")
            f.write(f'export GLOBAL_ENV_VARS=$(cat << "GENV_EOF"\n')
            f.write(global_env_str + "\n")
            f.write("GENV_EOF\n)\n\n")
        
        if task_params_str:
            f.write("# Task-specific parameters\n")
            f.write(f'export TASK_PARAMS=$(cat << "TASK_EOF"\n')
            f.write(task_params_str + "\n")
            f.write("TASK_EOF\n)\n\n")
        
        # Source the template and execute
        f.write("# Source wrapper template and execute\n")
        f.write(f'source "$SCRIPT_DIR/utils/wrapper_functions.sh"\n')
        f.write(f'execute_wrapper "{script_path.resolve()}"\n')

    os.chmod(wrapper_path, 0o755)
    return wrapper_path

def wait_for_jobs(job_ids: List[str], polling_interval: int = 60):
    """Wait for SLURM jobs to complete"""
    if not job_ids:
        return

    typer.echo(f"Waiting for jobs: {', '.join(job_ids)}")

    while True:
        try:
            result = subprocess.run(
                ["squeue", "--job", ",".join(job_ids), "--noheader", "--format=%i %T"],
                capture_output=True, text=True, check=True
            )

            if not result.stdout.strip():
                typer.echo("All jobs completed")
                break

            running_jobs = []
            for line in result.stdout.strip().split('\n'):
                if line.strip():
                    job_id, status = line.strip().split()
                    if status in ['PENDING', 'RUNNING']:
                        running_jobs.append(f"{job_id}({status})")

            if running_jobs:
                typer.echo(f"Waiting for: {', '.join(running_jobs)}")
                time.sleep(polling_interval)
            else:
                typer.echo("All jobs completed")
                break

        except subprocess.CalledProcessError:
            typer.echo("All jobs completed (not found in queue)")
            break