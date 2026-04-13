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
    _CONFIG_DIR,
)
from .utils.job_db import log_pipeline_execution, update_pipeline_execution
import shutil

app = typer.Typer()


from .utils.detect_subjects import parse_subjects_input as _parse_subjects

# Load global config
with open(_CONFIG_DIR / "config.yaml", "r", encoding="utf-8") as f:
    config = yaml.safe_load(f)

@dataclass
class TaskOptions:
    # Preprocessing
    prep: Optional[PrepChoice] = typer.Option(None, help="Preprocessing steps")
    
    # intermed
    intermed: Optional[List[str]] = typer.Option(None, "--intermed", help="Intermed tasks (e.g. volume,bfc)")

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
    for key in ('intermed', 'bids_prep', 'bids_post', 'staged_prep', 'staged_post'):
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

    intermed: Optional[List[str]] = typer.Option(None, "--intermed", help="Intermed tasks (e.g. volume,bfc)"),
    mriqc: Optional[MRIQCChoice] = typer.Option(None, help="MRIQC processing"),
    session: Optional[str] = typer.Option(..., help="Session or wave ID"),

    bids_prep: Optional[List[str]] = typer.Option(None, "--bids-prep", help="BIDS pipeline preprocessing (e.g. rest,dwi)"),
    bids_post: Optional[List[str]] = typer.Option(None, "--bids-post", help="BIDS pipeline postprocessing (e.g. rest,dwi)"),

    staged_prep: Optional[List[str]] = typer.Option(None, "--staged-prep", help="Staged pipeline preprocessing (e.g. cards,kidvid)"),
    staged_post: Optional[List[str]] = typer.Option(None, "--staged-post", help="Staged pipeline postprocessing (e.g. cards,kidvid)"),

    dry_run: bool = typer.Option(False, "--dry-run", help="Show execution plan"),
    resume: bool = typer.Option(False, "--resume", help="Skip subjects whose outputs already exist"),

    skip_preflight: bool = typer.Option(False, "--skip-preflight", help="Skip pre-flight config and filesystem checks"),
    skip_bids_validation: bool = typer.Option(False, "--skip-bids-validation", help="Skip BIDS format validation"),

    wait: bool = typer.Option(False, "--wait", help="Wait for jobs to complete"),
    polling_interval: int = typer.Option(60, "--polling-interval", help="Polling interval (seconds)")
):

    execution_id = None
    db_path = None
    command_line = " ".join(sys.argv)
    
    try:
        options = TaskOptions(
            prep=prep,
            intermed=intermed,
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

        if not skip_bids_validation:
            if bids_prep or mriqc in (MRIQCChoice.individual, MRIQCChoice.all):
                from .utils.bids_validation import run_bids_validation
                run_bids_validation(input_dir, work_dir)

        dag_executor = DAGExecutor(config)

        # Setup context
        if not subjects:
            typer.echo("Error: subjects parameter is required", err=True)
            raise typer.Exit(1)

        # Parse subjects (from file or string)
        user_subjects = _parse_subjects(subjects)
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
        if '$WORK_DIR' in db_path:
            typer.echo("Error: 'database.db_path' contains unresolved '$WORK_DIR' — check your project config", err=True)
            raise typer.Exit(1)

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
            execution_id=execution_id,
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
            typer.echo(f"  {os.path.dirname(db_path)}/json/")
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
    from .utils.detect_subjects import detect_subjects as sd, save_subjects_to_file

    if not Path(input_dir).exists():
        typer.echo(f"Error: Directory not found: {input_dir}", err=True)
        raise typer.Exit(1)

    subjects = sd(input_dir, prefix)

    if not subjects:
        typer.echo(f"No subjects found with prefix: {prefix}")
        raise typer.Exit(0)

    if output_file:
        save_subjects_to_file(subjects, output_file)
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


@app.command("force-rebuild")
def force_rebuild_cmd(
    work_dir: str = typer.Argument(..., help="Work directory"),
    db_path: Optional[str] = typer.Option(None, help="Original database path (auto-detect if not provided)"),
):
    """Rebuild a fresh database from all JSONL logs, including archived files.

    Creates pipeline_jobs_rebuild_{timestamp}.db next to the original database.
    The original database is never modified.

    Example:
      neuropipe force-rebuild /data/work/my_study
    """
    from .utils.merge_logs_create_db import rebuild_db
    try:
        new_db_path, count = rebuild_db(work_dir, db_path)
        typer.echo(f"Rebuilt {count} record(s) from all JSONL logs (including archived).")
        typer.echo(f"New database: {new_db_path}")
    except FileNotFoundError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1)


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


@app.command("check-outputs")
def check_outputs_cmd(
    project: str = typer.Option(..., help="Project name"),
    work_dir: str = typer.Option(..., "--work", help="Work/output directory"),
    subjects: Optional[str] = typer.Option(None, help="Subject list or file path (auto-detected from work_dir if omitted)"),
    session: Optional[str] = typer.Option(None, help="Session ID (checks all sessions if omitted)"),
    tasks: Optional[List[str]] = typer.Option(None, "--task",
        help="Task(s) to check (repeatable). Defaults to all configured tasks."),
    checks_dir: Optional[str] = typer.Option(None,
        help="Override directory for *_checks.yaml files"),
):
    """
    Check whether task outputs exist for each subject.

    Prints a summary of problematic subjects to the terminal and saves
    a full CSV report to <work_dir>/check_results_<timestamp>.csv.

    Without --subjects or --session, scans all subjects in work_dir across
    all sessions and saves a single CSV.

    Examples:
      neuropipe check-outputs --project test --work /data/processed
      neuropipe check-outputs --project test --work /data/processed \\
          --subjects 001,002 --session 01
    """
    from .utils.output_checker import OutputChecker, load_checks_config
    from .utils.detect_subjects import detect_subjects

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

    if subjects:
        subject_list = _parse_subjects(subjects)
        if not subject_list:
            typer.echo("Error: no subjects provided", err=True)
            raise typer.Exit(1)
    else:
        subject_list = detect_subjects(work_dir, prefix)
        if not subject_list:
            typer.echo(f"Error: no subjects found in {work_dir}", err=True)
            raise typer.Exit(1)
        typer.echo(f"Auto-detected {len(subject_list)} subjects from {work_dir}")

    effective_session = session if session else "*"
    if not session:
        typer.echo("No --session specified: checking all sessions")

    checker = OutputChecker(
        config_path=checks_config_path,
        work_dir=work_dir,
        prefix=prefix,
        session=effective_session,
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


@app.command("generate-config")
def generate_config_cmd(
    project_name: str = typer.Argument(..., help="Project name (e.g., branch, study1)"),
    output_dir: Optional[str] = typer.Option(None, "--output-dir", "-o",
        help="Output directory (default: config/project_config/)"),
):
    """Generate a blank project config template.

    Example:
      neuropipe generate-config branch
      neuropipe generate-config branch --output-dir /scratch/my_project/config/project_config
    """
    from .utils.generate_project_config import generate_project_config
    generate_project_config(project_name, output_dir)


@app.command("generate-checks")
def generate_checks_cmd(
    project_name: str = typer.Argument(..., help="Project name (e.g., branch, study1)"),
    output_dir: Optional[str] = typer.Option(None, "--output-dir", "-o",
        help="Output directory (default: config/results_check/)"),
):
    """Generate a blank results-check config template.

    Example:
      neuropipe generate-checks branch
      neuropipe generate-checks branch --output-dir /scratch/my_project/config/results_check
    """
    from .utils.generate_results_check import generate_results_check
    generate_results_check(project_name, output_dir)