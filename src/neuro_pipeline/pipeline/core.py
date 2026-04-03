import typer
import yaml
import sys
import os
from pathlib import Path
from typing import List, Optional
from dataclasses import dataclass
from .utils.hpc_utils import wait_for_jobs
from .dag import DAGExecutor, TaskRegistry
from .utils.config_utils import (
    PrepChoice,
    MRIQCChoice,
    load_project_config,
)
from .utils.job_db import log_pipeline_execution, update_pipeline_execution
import shutil

app = typer.Typer()

# Load global config
config_path = Path(__file__).parent / "config" / "config.yaml"
with open(config_path, "r", encoding="utf-8") as f:
    config = yaml.safe_load(f)

@dataclass
class TaskOptions:
    # Preprocessing
    prep: Optional[PrepChoice] = typer.Option(None, help="Preprocessing steps")
    
    # Structural
    structural: bool = typer.Option(False, "--structural", help="Structural MRI processing")

    # Quality Control
    mriqc: Optional[MRIQCChoice] = typer.Option(None, help="MRIQC processing")

    # Session
    session: Optional[str] = typer.Option('01', help="Session ID")

    # BIDS pipelines: --bids-prep rest,dwi
    bids_prep: Optional[List[str]] = typer.Option(None, help="BIDS pipeline preprocessing")
    bids_post: Optional[List[str]] = typer.Option(None, help="BIDS pipeline postprocessing")

    # Staged pipelines: --staged-prep cards,kidvid
    staged_prep: Optional[List[str]] = typer.Option(None, help="Staged pipeline preprocessing")
    staged_post: Optional[List[str]] = typer.Option(None, help="Staged pipeline postprocessing")

def collect_and_expand_tasks(registry, options: TaskOptions):
    """Collect and expand tasks"""
    return parse_and_expand_tasks(registry, **options.__dict__)

def parse_and_expand_tasks(registry, **kwargs):
    """Parse options and expand to concrete task names"""
    for key in ('bids_prep', 'bids_post', 'staged_prep', 'staged_post'):
        if kwargs.get(key):
            kwargs[key] = _parse_comma_list(kwargs[key])

    return registry.expand_tasks(**kwargs)

def _parse_comma_list(values):
    """Flatten and split comma-separated CLI values into a clean list"""
    result = []
    for item in values:
        result.extend([v.strip() for v in item.split(',') if v.strip()])
    return result

@app.command()
def run(
    subjects: Optional[str] = typer.Option(..., help="Subject list or txt file path"),

    input_dir: str = typer.Option(..., "--input", help="Input directory"),
    output_dir: str = typer.Option(..., "--output", help="Output directory"),
    work_dir: str = typer.Option(..., "--work", help="Work directory"),

    project: str = typer.Option(..., help="Project name"),

    prep: Optional[PrepChoice] = typer.Option(None, help="Preprocessing steps"),

    structural: bool = typer.Option(False, "--structural", help="Structural MRI processing"),
    mriqc: Optional[MRIQCChoice] = typer.Option(None, help="MRIQC processing"),
    session: Optional[str] = typer.Option(..., help="Session or wave ID"),

    bids_prep: Optional[List[str]] = typer.Option(None, "--bids-prep", help="BIDS pipeline preprocessing (e.g. rest,dwi)"),
    bids_post: Optional[List[str]] = typer.Option(None, "--bids-post", help="BIDS pipeline postprocessing (e.g. rest,dwi)"),

    staged_prep: Optional[List[str]] = typer.Option(None, "--staged-prep", help="Staged pipeline preprocessing (e.g. cards,kidvid)"),
    staged_post: Optional[List[str]] = typer.Option(None, "--staged-post", help="Staged pipeline postprocessing (e.g. cards,kidvid)"),

    dry_run: bool = typer.Option(False, "--dry-run", help="Show execution plan"),
    resume: bool = typer.Option(False, "--resume", help="Skip subjects whose outputs already exist"),

    skip_preflight: bool = typer.Option(False, "--skip-preflight", help="Skip pre-flight config and filesystem checks"),

    wait: bool = typer.Option(False, "--wait", help="Wait for jobs to complete"),
    polling_interval: int = typer.Option(60, "--polling-interval", help="Polling interval (seconds)")
):

    execution_id = None
    db_path = None
    command_line = " ".join(sys.argv)
    
    try:
        options = TaskOptions(
            prep=prep,
            structural=structural,
            mriqc=mriqc,
            session=session,
            bids_prep=bids_prep,
            bids_post=bids_post,
            staged_prep=staged_prep,
            staged_post=staged_post,
        )
                
        # Validate input
        if not Path(input_dir).exists():
            typer.echo(f"Error: Input directory not found: {input_dir}", err=True)
            raise typer.Exit(1)
        
        # Store original work_dir for database
        original_work_dir = work_dir
        
        # Adjust paths for project, input_path/project/
        if project:
            work_dir = os.path.join(work_dir, project)
            output_dir = os.path.join(output_dir, project)
        
        Path(work_dir).mkdir(parents=True, exist_ok=True)
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        
        # Load project config
        try:
            project_config = load_project_config(project)
            typer.echo(f"Loaded project: {project}")
        except FileNotFoundError as e:
            typer.echo(f"Error: {e}", err=True)
            raise typer.Exit(1)
        
        # Extract global parameters (root-level config)
        prefix = project_config.get('prefix', '')
        envir_dir = project_config.get('envir_dir', {})
        container_dir = envir_dir.get('container_dir')
        if not container_dir:
            raise ValueError("container_dir not found in envir_dir config")

        if not prefix:
            typer.echo("Error: 'prefix' not found in project config", err=True)
            raise typer.Exit(1)

        # Pre-flight checks
        if not skip_preflight:
            from .utils.preflight import PreflightChecker, print_preflight_report
            checker = PreflightChecker(
                project_config=project_config,
                global_config=config,
                work_dir=work_dir,
                input_dir=input_dir,
            )
            preflight_result = checker.run_all()
            print_preflight_report(preflight_result)
            if not preflight_result.ok:
                raise typer.Exit(1)
    
        registry = TaskRegistry()

        # Expand tasks
        requested_tasks = collect_and_expand_tasks(registry, options)
        if not requested_tasks:
            typer.echo("Error: No tasks specified", err=True)
            raise typer.Exit(1)
        
        typer.echo(f"Tasks: {requested_tasks}")
        
        dag_executor = DAGExecutor(config)

        # Setup context
        if not subjects:
            typer.echo("Error: subjects parameter is required", err=True)
            raise typer.Exit(1)

        # Parse subjects (from file or string)
        if Path(subjects).is_file():
            with open(subjects, "r") as f:
                subjects = f.read().strip()

        user_subjects = [s.strip() for s in subjects.split(",") if s.strip()]
        context = {'subjects': user_subjects}
        typer.echo(f"Subjects: {user_subjects}")

        # Setup environment
        option_env = {
            "session": options.session,
            "prefix": prefix,
            "project": project,
        }
        
        for key, value in envir_dir.items():
            option_env[f"envir_dir_{key}"] = value
        
        option_env = {k: v for k, v in option_env.items() if v is not None}

        # Setup database
        db_config = project_config.get('database', {})

        # Check if database config exists
        if not db_config or 'db_path' not in db_config:
            typer.echo("Error: 'database.db_path' not found in project config", err=True)
            raise typer.Exit(1)

        db_path = db_config['db_path'].replace('$WORK_DIR', original_work_dir)

        # Create db directory
        db_dir = os.path.dirname(db_path)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)

        # Auto-backup database before execution
        if Path(db_path).exists():
            from .utils.db_backup import backup_database
            try:
                backup_path = backup_database(db_path, backup_dir=None)
                typer.echo(f"Database backed up to: {backup_path}")
            except Exception as e:
                typer.echo(f"Warning: Backup failed: {e}", err=True)

        # Log execution start
        execution_id = log_pipeline_execution(
            command_line=command_line,
            project_name=project,
            session=options.session,
            input_dir=input_dir,
            output_dir=output_dir,
            work_dir=work_dir,
            subjects=context.get('subjects', []),
            requested_tasks=requested_tasks,
            dry_run=dry_run,
            db_path=db_path
        )
        typer.echo(f"Execution ID: {execution_id}")

        # Resume: locate per-project checks config
        checks_config_path = None
        if resume:
            from .utils.output_checker import load_checks_config
            try:
                checks_config_path = load_checks_config(project)
                typer.echo(f"[resume] Loaded output checks: {checks_config_path}")
            except FileNotFoundError as e:
                typer.echo(f"Warning: {e}", err=True)
                typer.echo("Warning: --resume requested but no checks config found. "
                           "Proceeding without skipping.", err=True)

        # Execute DAG
        all_job_ids, context = dag_executor.execute(
            requested_tasks=requested_tasks,
            input_dir=input_dir,
            output_dir=output_dir,
            work_dir=work_dir,
            container_dir=container_dir,
            dry_run=dry_run,
            context=context,
            option_env=option_env,
            project_config=project_config,
            original_work_dir=original_work_dir,
            db_path=db_path,
            resume=resume,
            checks_config_path=checks_config_path,
        )
        # Display summary
        typer.echo(f"\n=== Summary ===")
        total_jobs = sum(len(job_list) for job_list in all_job_ids.values())
        typer.echo(f"Tasks executed: {len(all_job_ids)}")
        typer.echo(f"Jobs submitted: {total_jobs}")
        
        if not dry_run:
            for task_name, job_ids in all_job_ids.items():
                if job_ids:
                    typer.echo(f"  {task_name}: {', '.join(job_ids)}")
        
        # Wait for jobs if requested
        if wait and not dry_run:
            all_jobs = []
            for job_list in all_job_ids.values():
                all_jobs.extend(job_list)
            
            if all_jobs:
                typer.echo(f"\n=== Waiting for jobs ===")
                wait_for_jobs(all_jobs, polling_interval)
            else:
                typer.echo("No jobs to wait for")
        
        # Update execution status
        if execution_id:
            update_pipeline_execution(
                execution_id=execution_id,
                status="COMPLETED",
                total_jobs=total_jobs,
                db_path=db_path
            )
            
        if not dry_run and all_job_ids:
            typer.echo("\n" + "="*60)
            typer.echo(f"\nJSON logs location:")
            typer.echo(f"  {work_dir}/log/database/json/")
            typer.echo(f"\nTo check job status, run:")
            typer.echo(f"  python -m neuro_pipeline.pipeline.utils.job_db query_jobs --db-path {db_path}")
            typer.echo(f"\nOr check recent jobs:")
            typer.echo(f"  python -m neuro_pipeline.pipeline.utils.job_db query_jobs --limit 20 --db-path {db_path}")
            typer.echo(f"\nTo manually merge logs (optional):")
            typer.echo(f"  neuropipe merge-logs {original_work_dir or work_dir}")

        typer.echo("\n=== Completed ===")
    
    # Record error
    except Exception as e:
        # Update execution status on failure
        if execution_id:
            update_pipeline_execution(
                execution_id=execution_id,
                status="FAILED",
                error_msg=str(e),
                db_path=db_path
            )
        raise e

@app.command()
def list_tasks():
    """List available tasks"""
    typer.echo("Available tasks:")
    for section_name, section_tasks in config.items():
        if not isinstance(section_tasks, list):
            continue
        typer.echo(f"\n{section_name.upper()}:")
        for task in section_tasks:
            if not isinstance(task, dict):
                continue
            name = task.get('name', 'Unknown')
            scripts = task.get('scripts', [])
            deps = task.get('input_from', 'None')

            typer.echo(f"  - {name}")
            typer.echo(f"    Scripts: {', '.join(scripts)}")
            typer.echo(f"    Dependencies: {deps}")

@app.command()
def detect_subjects(
    input_dir: str = typer.Argument(..., help="Input directory to scan"),
    output_file: Optional[str] = typer.Option(None, "--output", "-o", help="Output file (optional, prints to stdout if not specified)"),
    prefix: str = typer.Option("sub-", "--prefix", "-p", help="Subject prefix")
):
    """
    Detect subjects in input directory and optionally save to file.
    
    Examples:
      neuro-pipeline detect-subjects /data/BIDS
      neuro-pipeline detect-subjects /data/BIDS --output subjects.txt
      neuro-pipeline detect-subjects /data/BIDS --prefix "sub-" --output subjects.txt
    """
    from .utils.detect_subjects import detect_subjects as sd
    
    if not Path(input_dir).exists():
        typer.echo(f"Error: Directory not found: {input_dir}", err=True)
        raise typer.Exit(1)
    
    # Detect subjects
    subjects = sd(input_dir, prefix)
    
    if not subjects:
        typer.echo(f"No subjects found with prefix: {prefix}")
        raise typer.Exit(0)
    
    # Save or print
    if output_file:
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_file, "w") as f:
            f.write(",".join(subjects))
        
        typer.echo(f"Detected {len(subjects)} subjects")
        typer.echo(f"Saved to: {output_file}")
        typer.echo(f"Subjects: {', '.join(subjects[:5])}{'...' if len(subjects) > 5 else ''}")
    else:
        typer.echo(f"Detected {len(subjects)} subjects:")
        typer.echo(",".join(subjects))

@app.command("merge-logs")
def merge_logs_cmd(
    work_dir: str = typer.Argument(..., help="Work directory"),
    db_path: Optional[str] = typer.Option(None, help="Database path (auto-detect if not provided)")
):
    """Merge JSON logs to database manually"""
    from .utils.merge_logs_create_db import merge_once
    merge_once(work_dir, db_path)


@app.command("generate-report")
def generate_report_cmd(
    db_path: str = typer.Option(..., "--db-path", help="Path to pipeline_jobs.db"),
    project: str = typer.Option(..., "--project", help="Project name"),
    output: Optional[str] = typer.Option(
        None, "--output", "-o",
        help="Output HTML path. Defaults to pipeline_report_<project>_<timestamp>.html next to the database."
    ),
    session: Optional[str] = typer.Option(
        None, "--session",
        help="Filter by session ID (recommended when multiple projects share a database)."
    ),
    check_results: Optional[str] = typer.Option(
        None, "--check-results",
        help="Path to a check_results_*.csv from check-outputs. Auto-detected from work_dir if omitted."
    ),
):
    """
    Generate a standalone HTML pipeline report for a project.
    Example:
      neuropipe generate-report --db-path /scratch/log/database/pipeline_jobs.db \\
          --project GCDS --session 01
    """
    from .utils.report_generator import generate_report
    try:
        out = generate_report(
            db_path=db_path,
            project_name=project,
            output_path=output,
            session=session,
            check_results_path=check_results,
        )
        typer.echo(f"Report: {out}")
    except (FileNotFoundError, ValueError) as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1)


if __name__ == "__main__":
    app()

@app.command("check-outputs")
def check_outputs_cmd(
    project: str = typer.Option(..., help="Project name"),
    work_dir: str = typer.Option(..., "--work", help="Work/output directory"),
    subjects: str = typer.Option(..., help="Subject list or txt file path"),
    session: Optional[str] = typer.Option("01", help="Session ID"),
    tasks: Optional[List[str]] = typer.Option(None, "--task",
        help="Task(s) to check (repeatable). Defaults to all configured tasks."),
    checks_dir: Optional[str] = typer.Option(None,
        help="Override directory for *_checks.yaml files"),
):
    """
    Check whether task outputs exist for each subject.

    Prints a summary of problematic subjects to the terminal and saves
    a full CSV report to <work_dir>/check_results_<timestamp>.csv.

    Example:
      neuropipe check-outputs --project test --work /data/processed \\
          --subjects sub-001,sub-002 --session 01
    """
    from .utils.output_checker import OutputChecker, load_checks_config

    try:
        checks_config_path = load_checks_config(project, checks_dir)
        typer.echo(f"Loaded checks config: {checks_config_path}")
    except FileNotFoundError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1)

    try:
        project_config = load_project_config(project)
        prefix = project_config.get('prefix', 'sub-')
    except FileNotFoundError:
        prefix = 'sub-'

    subjects_path = Path(subjects)
    if subjects_path.is_file():
        with open(subjects_path) as f:
            subject_list = [s.strip() for s in f.read().split(',') if s.strip()]
    else:
        subject_list = [s.strip() for s in subjects.split(',') if s.strip()]

    if not subject_list:
        typer.echo("Error: no subjects provided", err=True)
        raise typer.Exit(1)

    checker = OutputChecker(
        config_path=checks_config_path,
        work_dir=work_dir,
        prefix=prefix,
        session=session,
    )

    all_configured_tasks = list(checker._config.keys())
    task_names = tasks if tasks else all_configured_tasks

    checker.warn_missing_configs(task_names)
    task_names = [t for t in task_names if t in checker._config]

    if not task_names:
        typer.echo("No tasks to check (none have output check configs).")
        raise typer.Exit(0)

    typer.echo(f"Checking {len(task_names)} task(s) × {len(subject_list)} subject(s)...")

    df = checker.check_all(task_names, subject_list)
    checker.print_terminal_summary(df)

    csv_path = checker.save_csv(df, work_dir)
    typer.echo(f"Full report saved to: {csv_path}")