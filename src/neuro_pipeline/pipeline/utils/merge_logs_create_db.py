import json
import shutil
import os
from pathlib import Path
import typer

app = typer.Typer()

def merge_json_to_db(json_base_dir: str, db_path: str, job_ids: list = None):
    """Merge JSON logs to database
    
    Args:
        json_base_dir: Base directory containing JSON logs
        db_path: Database file path
        job_ids: Optional list of job IDs to filter (only merge logs for these jobs)
    
    Returns:
        int: Number of files merged
    """
    from .job_db import get_db_connection
    
    conn = get_db_connection(db_path)
    merged_count = 0
    
    for task_dir in Path(json_base_dir).glob("*"):
        if not task_dir.is_dir():
            continue
        
        # Handle pipeline executions
        if task_dir.name == "_pipeline":
            merged_count += _merge_pipeline(task_dir, conn, job_ids)
        else:
            merged_count += _merge_jobs(task_dir, conn, job_ids)
    
    conn.close()
    return merged_count

def _merge_pipeline(task_dir, conn, job_ids=None):
    """Merge pipeline executions
    
    Args:
        task_dir: Pipeline task directory
        conn: Database connection
        job_ids: Optional job IDs filter (not used for pipeline logs)
    
    Returns:
        int: Number of pipeline logs merged
    """
    count = 0
    for json_file in task_dir.glob("*.jsonl"):
        try:
            # Skip if job_ids filter is active (pipeline logs don't have job_ids)
            if job_ids is not None:
                continue
                
            records = {}
            with open(json_file) as f:
                for line in f:
                    if line.strip():
                        r = json.loads(line)
                        records[r.get("event")] = r
            
            if "pipeline_start" in records:
                r = records["pipeline_start"]
                u = records.get("pipeline_update", {})
                
                conn.execute('''
                    INSERT INTO pipeline_executions
                    (execution_time, command_line, project_name, session, input_dir, 
                     output_dir, work_dir, subjects, requested_tasks, dry_run, 
                     total_jobs, status, error_msg)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (r.get("timestamp"), r.get("command_line"), r.get("project_name"),
                      r.get("session"), r.get("input_dir"), r.get("output_dir"),
                      r.get("work_dir"), r.get("subjects"), r.get("requested_tasks"),
                      r.get("dry_run"), u.get("total_jobs", r.get("total_jobs")),
                      u.get("status", r.get("status")), u.get("error_msg")))
                conn.commit()
                
                # Archive the file
                archived = task_dir / "archived"
                archived.mkdir(exist_ok=True)
                shutil.move(str(json_file), str(archived / json_file.name))
                count += 1
        except Exception as e:
            print(f"Error: {json_file}: {e}")
    return count

def _merge_jobs(task_dir, conn, job_ids=None):
    """Merge job status logs
    
    Args:
        task_dir: Task directory containing JSON files
        conn: Database connection
        job_ids: Optional list of job IDs to filter (supports base job_id for array jobs)
    
    Returns:
        int: Number of job logs merged
    """
    count = 0
    for json_file in task_dir.glob("*.jsonl"):
        try:
            records = {}
            with open(json_file) as f:
                for line in f:
                    if line.strip():
                        r = json.loads(line)
                        records[r.get("event")] = r
            
            # Only merge complete logs
            if "start" not in records:
                continue
            
            if "end" not in records:
                continue
            
            job_id = records["start"].get("job_id")
            
            # Filter by job_ids if provided
            if job_ids is not None:
                # Support both exact match and prefix match (for array jobs)
                # e.g., job_id='41693293_1' matches filter='41693293'
                matched = False
                for filter_id in job_ids:
                    if job_id == filter_id or job_id.startswith(filter_id + '_'):
                        matched = True
                        break
                
                if not matched:
                    continue
            
            # Insert job start
            r = records["start"]
            conn.execute('''
                INSERT INTO job_status 
                (subject, task_name, session, start_time, status, log_path, job_id, node_name)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (r.get("subject"), r.get("task_name"), r.get("session"),
                  r.get("timestamp"), "RUNNING", r.get("log_path"),
                  r.get("job_id"), r.get("node_name")))
            
            # Update job end
            r = records["end"]
            conn.execute('''
                UPDATE job_status
                SET end_time=?, status=?, error_msg=?, duration_hours=?, exit_code=?
                WHERE subject=? AND task_name=? AND session=? AND status='RUNNING'
            ''', (r.get("timestamp"), r.get("status"), r.get("error_msg"),
                  r.get("duration_hours"), r.get("exit_code"),
                  r.get("subject"), r.get("task_name"), r.get("session")))
            
            # Insert command output if available
            if "command_output" in records:
                r = records["command_output"]
                conn.execute('''
                    INSERT INTO command_outputs
                    (subject, task_name, session, script_name, command, stdout, stderr, 
                     exit_code, log_file_path, job_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (r.get("subject"), r.get("task_name"), r.get("session"),
                      r.get("script_name"), r.get("command"), r.get("stdout"),
                      r.get("stderr"), r.get("exit_code"), r.get("log_file_path"),
                      r.get("job_id")))
            
            conn.commit()
            
            # Archive the file
            archived = task_dir / "archived"
            archived.mkdir(exist_ok=True)
            shutil.move(str(json_file), str(archived / json_file.name))
            count += 1
        except Exception as e:
            print(f"Error: {json_file}: {e}")
    return count

@app.command("merge")
def merge_once(work_dir: str, db_path: str = None):
    """Merge JSON logs to database"""
    if not db_path:
        db_path = os.path.join(work_dir, "database", "pipeline_jobs.db")
    
    json_dir = os.path.join(os.path.dirname(db_path), "json")
    if not os.path.exists(json_dir):
        typer.echo(f"No JSON logs: {json_dir}")
        return
    
    count = merge_json_to_db(json_dir, db_path)
    typer.echo(f"Merged {count} files")

if __name__ == "__main__":
    app()