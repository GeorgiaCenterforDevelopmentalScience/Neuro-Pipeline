#!/usr/bin/env python3

import sqlite3
from datetime import datetime
import os
from typing import Optional
import typer

app = typer.Typer(help="Task database management tool")

def ensure_db_dir(db_path: str):
    """Ensure database directory exists"""
    db_dir = os.path.dirname(db_path)
    if db_dir and not os.path.exists(db_dir):
        os.makedirs(db_dir, exist_ok=True)

# Set up default tables
def ensure_table_exists(conn, table_name: str):
    """Create table if not exists"""
    c = conn.cursor()
    
    if table_name == "job_status":
        c.execute('''
            CREATE TABLE IF NOT EXISTS job_status (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                subject TEXT,
                task_name TEXT,
                session TEXT,
                start_time TEXT,
                end_time TEXT,
                status TEXT,
                exit_code INTEGER,
                error_msg TEXT,
                duration_hours REAL,
                log_path TEXT,
                job_id TEXT,
                node_name TEXT
            )
        ''')
    elif table_name == "pipeline_executions":
        c.execute('''
            CREATE TABLE IF NOT EXISTS pipeline_executions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                execution_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                command_line TEXT,
                project_name TEXT,
                session TEXT,
                input_dir TEXT,
                output_dir TEXT,
                work_dir TEXT,
                subjects TEXT,
                requested_tasks TEXT,
                dry_run BOOLEAN,
                total_jobs INTEGER,
                status TEXT DEFAULT 'RUNNING',
                error_msg TEXT
            )
        ''')
    elif table_name == "command_outputs":
        c.execute('''
            CREATE TABLE IF NOT EXISTS command_outputs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                subject TEXT,
                task_name TEXT,
                session TEXT,
                script_name TEXT,
                command TEXT,
                stdout TEXT,
                stderr TEXT,
                exit_code INTEGER,
                execution_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                log_file_path TEXT,
                job_id TEXT
            )
        ''')
    
    conn.commit()

def get_db_connection(db_path: str):
    """Get database connection and ensure tables exist"""
    ensure_db_dir(db_path)
    conn = sqlite3.connect(db_path)
    
    for table in ["job_status", "pipeline_executions", "command_outputs"]:
        ensure_table_exists(conn, table)
    
    return conn

def calculate_duration_hours(start_time_str: str, end_time_str: str) -> Optional[float]:
    """Calculate task duration in hours"""
    try:
        start_time = datetime.fromisoformat(start_time_str)
        end_time = datetime.fromisoformat(end_time_str)
        duration_seconds = (end_time - start_time).total_seconds()
        return round(duration_seconds / 3600, 3)
    except (ValueError, TypeError):
        return None

@app.command("init_db")
def init_db(db_path: str = "pipeline_jobs.db"):
    """Initialize database"""
    conn = get_db_connection(db_path)
    conn.close()
    typer.echo(f"Database initialized: {db_path}")

@app.command("log_start")
@app.command("log_job_start") 
def log_job_start(
    subject: str,
    task_name: str,
    session: Optional[str] = None,
    log_file_path: Optional[str] = None,
    job_id: Optional[str] = None,
    node_list: Optional[str] = None,
    db_path: str = "pipeline_jobs.db"
):
    """Log job start"""
    try:
        conn = get_db_connection(db_path)
        c = conn.cursor()
        
        c.execute('''
            INSERT INTO job_status (subject, task_name, session, start_time, status, log_path, job_id, node_name)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (subject, task_name, session, datetime.now().isoformat(), "RUNNING", log_file_path, job_id, node_list))
        
        conn.commit()
        conn.close()
        typer.echo(f"Job started: {subject} - {task_name} (session: {session})")
    except Exception as e:
        typer.echo(f"Error logging job start: {e}", err=True)
        raise typer.Exit(1)

@app.command("log_end")
@app.command("log_job_end")
def log_job_end(
    subject: str,
    task_name: str,
    status: str,
    session: Optional[str] = None,
    error_msg: Optional[str] = None,
    duration_seconds: Optional[float] = None,
    exit_code: Optional[int] = None,
    db_path: str = "pipeline_jobs.db"
):
    """Log job end"""
    try:
        conn = get_db_connection(db_path)
        c = conn.cursor()
        
        end_time = datetime.now().isoformat()
        
        # Calculate duration
        duration_hours = None
        if duration_seconds is not None:
            duration_hours = round(duration_seconds / 3600, 3)
        else:
            where_clause = 'subject=? AND task_name=? AND status="RUNNING"'
            params = [subject, task_name]
            if session:
                where_clause += ' AND session=?'
                params.append(session)
            
            c.execute(f'SELECT start_time FROM job_status WHERE {where_clause}', params)
            row = c.fetchone()
            if row and row[0]:
                duration_hours = calculate_duration_hours(row[0], end_time)
        
        # Update job status
        where_clause = 'subject=? AND task_name=? AND status="RUNNING"'
        params = [end_time, status, error_msg, duration_hours, exit_code, subject, task_name]
        if session:
            where_clause += ' AND session=?'
            params.append(session)
        
        c.execute(f'''
            UPDATE job_status
            SET end_time=?, status=?, error_msg=?, duration_hours=?, exit_code=?
            WHERE {where_clause}
        ''', params)
        
        conn.commit()
        conn.close()
        
        duration_str = f" ({duration_hours:.3f}h)" if duration_hours else ""
        typer.echo(f"Job ended: {subject} - {task_name} ({status}){duration_str}")
    except Exception as e:
        typer.echo(f"Error logging job end: {e}", err=True)
        raise typer.Exit(1)

@app.command("log_pipeline_execution")
def log_pipeline_execution(
    command_line: str,
    project_name: str,
    input_dir: str,
    output_dir: str,
    work_dir: str,
    session: Optional[str] = None,
    subjects: Optional[str] = None,
    requested_tasks: Optional[str] = None,
    dry_run: bool = False,
    total_jobs: int = 0,
    db_path: str = "pipeline_jobs.db"
):
    """Log pipeline execution"""
    conn = get_db_connection(db_path)
    c = conn.cursor()
    
    # Convert list to comma-separated string
    if isinstance(subjects, list):
        subjects_str = ','.join(subjects)
    elif isinstance(subjects, str):
        subjects_str = subjects
    else:
        subjects_str = None
    
    if isinstance(requested_tasks, list):
        tasks_str = ','.join(requested_tasks)
    elif isinstance(requested_tasks, str):
        tasks_str = requested_tasks
    else:
        tasks_str = None
    
    c.execute('''
        INSERT INTO pipeline_executions 
        (command_line, project_name, session, input_dir, output_dir, work_dir, 
         subjects, requested_tasks, dry_run, total_jobs)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (command_line, project_name, session, input_dir, output_dir, work_dir,
          subjects_str, tasks_str, dry_run, total_jobs))
    
    execution_id = c.lastrowid
    conn.commit()
    conn.close()
    
    typer.echo(f"Pipeline execution logged, ID: {execution_id}")
    return execution_id

@app.command("update_pipeline_execution")
def update_pipeline_execution(
    execution_id: int,
    status: str = "COMPLETED",
    error_msg: Optional[str] = None,
    total_jobs: Optional[int] = None,
    db_path: str = "pipeline_jobs.db"
):
    """Update pipeline execution status"""
    conn = get_db_connection(db_path)
    c = conn.cursor()
    
    update_fields = ["status=?"]
    params = [status]
    
    if error_msg is not None:
        update_fields.append("error_msg=?")
        params.append(error_msg)
    
    if total_jobs is not None:
        update_fields.append("total_jobs=?")
        params.append(total_jobs)
    
    params.append(execution_id)
    
    c.execute(f'''
        UPDATE pipeline_executions 
        SET {', '.join(update_fields)}
        WHERE id=?
    ''', params)
    
    conn.commit()
    conn.close()
    typer.echo(f"Pipeline execution updated: {execution_id} -> {status}")

@app.command("query_pipeline_executions")
def query_pipeline_executions(
    limit: int = 10,
    project_name: Optional[str] = None,
    session: Optional[str] = None,
    status: Optional[str] = None,
    db_path: str = "pipeline_jobs.db"
):
    """Query pipeline execution records"""
    conn = get_db_connection(db_path)
    c = conn.cursor()
    
    query = "SELECT * FROM pipeline_executions"
    params = []
    
    conditions = []
    if project_name:
        conditions.append("project_name=?")
        params.append(project_name)
    if session:
        conditions.append("session=?")
        params.append(session)
    if status:
        conditions.append("status=?")
        params.append(status)
    
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    
    query += " ORDER BY execution_time DESC LIMIT ?"
    params.append(limit)
    
    c.execute(query, params)
    rows = c.fetchall()
    conn.close()
    
    if not rows:
        typer.echo("No matching records found")
        return rows
    
    for row in rows:
        typer.echo(f"ID: {row[0]}")
        typer.echo(f"Project: {row[3]}")
        typer.echo(f"Session: {row[4] or 'N/A'}")
        typer.echo(f"Status: {row[12]}")
        typer.echo(f"Execution time: {row[1]}")
        typer.echo(f"Subjects: {row[8] or 'N/A'}")
        typer.echo(f"Tasks: {row[9] or 'N/A'}")
        typer.echo(f"Total jobs: {row[11]}")
        if row[13]:
            typer.echo(f"Error: {row[13]}")
        typer.echo("-" * 40)
    
    return rows

@app.command("log_command_output")
def log_command_output(
    subject: str,
    task_name: str,
    script_name: str,
    command: str,
    session: Optional[str] = None,
    stdout: Optional[str] = None,
    stderr: Optional[str] = None,
    exit_code: Optional[int] = None,
    log_file_path: Optional[str] = None,
    job_id: Optional[str] = None,
    db_path: str = "pipeline_jobs.db"
):
    """Log command output (truncated to 50 lines)"""
    conn = get_db_connection(db_path)
    c = conn.cursor()
    
    # Truncate stdout and stderr to last 50 lines
    if stdout:
        lines = stdout.split('\n')
        if len(lines) > 50:
            stdout = '\n'.join(lines[-50:])
    
    if stderr:
        lines = stderr.split('\n')
        if len(lines) > 50:
            stderr = '\n'.join(lines[-50:])
    
    c.execute('''
        INSERT INTO command_outputs 
        (subject, task_name, session, script_name, command, stdout, stderr, exit_code, log_file_path, job_id)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (subject, task_name, session, script_name, command, stdout, stderr, exit_code, log_file_path, job_id))
    
    conn.commit()
    conn.close()
    typer.echo(f"Command output logged: {subject} - {task_name}")

# TODO: Integrate with cli? or remove?

@app.command("query_jobs")
def query_jobs(
    limit: int = 20,
    subject: Optional[str] = None,
    task_name: Optional[str] = None,
    session: Optional[str] = None,
    status: Optional[str] = None,
    db_path: str = "pipeline_jobs.db"
):
    """Query job status records"""
    conn = get_db_connection(db_path)
    c = conn.cursor()
    
    query = "SELECT * FROM job_status"
    params = []
    
    conditions = []
    if subject:
        conditions.append("subject=?")
        params.append(subject)
    if task_name:
        conditions.append("task_name=?")
        params.append(task_name)
    if session:
        conditions.append("session=?")
        params.append(session)
    if status:
        conditions.append("status=?")
        params.append(status)
    
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    
    query += " ORDER BY start_time DESC LIMIT ?"
    params.append(limit)
    
    c.execute(query, params)
    rows = c.fetchall()
    conn.close()
    
    if not rows:
        typer.echo("No matching records found")
        return rows
    
    for row in rows:
        typer.echo(f"Subject: {row[1]} | Task: {row[2]} | Session: {row[3] or 'N/A'}")
        typer.echo(f"Status: {row[6]} | Exit code: {row[7]}")
        typer.echo(f"Start: {row[4]}")
        typer.echo(f"End: {row[5] or 'Running'}")
        if row[9]:
            typer.echo(f"Duration: {row[9]:.3f}h")
        if row[8]:
            typer.echo(f"Error: {row[8]}")
        typer.echo(f"Log: {row[10]}")
        typer.echo(f"Job ID: {row[11]} | Node: {row[12]}")
        typer.echo("-" * 60)
    
    return rows

@app.command("read_log")
def read_log(
    log_file_path: str = typer.Argument(..., help="Log file path"),
    max_lines: int = typer.Option(100, "--max-lines", "-n", help="Maximum lines to read"),
    follow: bool = typer.Option(False, "--follow", "-f", help="Follow log in real-time")
):
    """Read log file content"""
    if not os.path.exists(log_file_path):
        typer.echo(f"Log file not found: {log_file_path}", err=True)
        raise typer.Exit(1)
    
    try:
        if follow:
            typer.echo(f"Following log file: {log_file_path}")
            typer.echo("Press Ctrl+C to exit")
            typer.echo("-" * 60)
            
            import subprocess
            subprocess.run(['tail', '-f', log_file_path])
        else:
            with open(log_file_path, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()
                total_lines = len(lines)
                
                if total_lines > max_lines:
                    lines = lines[-max_lines:]
                    typer.echo(f"Showing last {max_lines} lines (total {total_lines} lines):")
                else:
                    typer.echo(f"Showing all {total_lines} lines:")
                
                typer.echo("-" * 60)
                
                for line in lines:
                    typer.echo(line.rstrip())
                
    except KeyboardInterrupt:
        typer.echo("\n\nStopped following log")
    except Exception as e:
        typer.echo(f"Failed to read log file: {e}", err=True)
        raise typer.Exit(1)

if __name__ == "__main__":
    app()