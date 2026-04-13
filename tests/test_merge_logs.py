import pytest
import os
import json
import sqlite3
import tempfile
import shutil
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

# Add package to path
import sys
test_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(test_root / "src"))

from neuro_pipeline.pipeline.dag import DAGExecutor
from neuro_pipeline.pipeline.utils.merge_logs_create_db import merge_json_to_db, rebuild_db


@pytest.fixture
def temp_workspace():
    """Create temporary workspace for testing"""
    tmpdir = tempfile.mkdtemp()
    workspace = {
        'root': tmpdir,
        'work_dir': os.path.join(tmpdir, 'work'),
        'input_dir': os.path.join(tmpdir, 'input'),
        'output_dir': os.path.join(tmpdir, 'output'),
        'db_path': os.path.join(tmpdir, 'work', 'log', 'pipeline_jobs.db'),
        'json_dir': os.path.join(tmpdir, 'work', 'log', 'json'),
    }
    
    # Create directories
    os.makedirs(workspace['work_dir'], exist_ok=True)
    os.makedirs(workspace['input_dir'], exist_ok=True)
    os.makedirs(workspace['output_dir'], exist_ok=True)
    os.makedirs(os.path.dirname(workspace['db_path']), exist_ok=True)
    os.makedirs(workspace['json_dir'], exist_ok=True)
    
    yield workspace
    
    # Cleanup
    shutil.rmtree(tmpdir)


@pytest.fixture
def mock_db(temp_workspace):
    """Create mock database with schema"""
    db_path = temp_workspace['db_path']
    conn = sqlite3.connect(db_path)
    
    # Create schema — must match job_db.py exactly
    conn.execute('''
        CREATE TABLE IF NOT EXISTS job_status (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            execution_id INTEGER,
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

    conn.execute('''
        CREATE TABLE IF NOT EXISTS command_outputs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            execution_id INTEGER,
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
    conn.close()
    
    return db_path


def create_mock_json_log(json_dir, subject, task_name, job_id, status="SUCCESS"):
    """Create mock JSON log file"""
    task_dir = Path(json_dir) / task_name
    task_dir.mkdir(exist_ok=True)
    
    log_file = task_dir / f"{subject}_{task_name}_{job_id}.jsonl"
    
    # Create complete log with start and end events
    logs = [
        {
            "event": "start",
            "timestamp": datetime.now().isoformat(),
            "subject": subject,
            "task_name": task_name,
            "session": "01",
            "job_id": job_id,
            "log_path": f"/path/to/{subject}_{task_name}.log",
            "node_name": "node001"
        },
        {
            "event": "end",
            "timestamp": datetime.now().isoformat(),
            "subject": subject,
            "task_name": task_name,
            "session": "01",
            "status": status,
            "exit_code": 0 if status == "SUCCESS" else 1,
            "duration_hours": 0.5
        }
    ]
    
    # Write only end event if status is SUCCESS (complete log)
    with open(log_file, 'w') as f:
        for log in logs:
            f.write(json.dumps(log) + '\n')
    
    return str(log_file)


def create_incomplete_json_log(json_dir, subject, task_name, job_id):
    """Create incomplete JSON log (only start event)"""
    task_dir = Path(json_dir) / task_name
    task_dir.mkdir(exist_ok=True)
    
    log_file = task_dir / f"{subject}_{task_name}_{job_id}.jsonl"
    
    # Only start event (incomplete)
    log = {
        "event": "start",
        "timestamp": datetime.now().isoformat(),
        "subject": subject,
        "task_name": task_name,
        "session": "01",
        "job_id": job_id,
        "log_path": f"/path/to/{subject}_{task_name}.log",
        "node_name": "node001"
    }
    
    with open(log_file, 'w') as f:
        f.write(json.dumps(log) + '\n')
    
    return str(log_file)


class TestMergeLogsFunction:
    """Test merge_logs functionality"""
    
    def test_merge_complete_logs_only(self, temp_workspace, mock_db):
        """Test 1: merge_logs only processes complete JSON files"""
        json_dir = temp_workspace['json_dir']
        
        # Create complete and incomplete logs
        create_mock_json_log(json_dir, "sub001", "task1", "12345")
        create_incomplete_json_log(json_dir, "sub002", "task2", "12346")
        
        # Run merge
        count = merge_json_to_db(json_dir, mock_db)
        
        # Verify only complete log was merged
        assert count == 1
        
        # Check database
        conn = sqlite3.connect(mock_db)
        cursor = conn.execute("SELECT COUNT(*) FROM job_status WHERE job_id='12345'")
        assert cursor.fetchone()[0] == 1
        
        cursor = conn.execute("SELECT COUNT(*) FROM job_status WHERE job_id='12346'")
        assert cursor.fetchone()[0] == 0
        conn.close()
        
        # Verify incomplete log still exists
        incomplete_file = Path(json_dir) / "task2" / "sub002_task2_12346.jsonl"
        assert incomplete_file.exists()
    
    def test_merge_specific_job_ids(self, temp_workspace, mock_db):
        """Test 3: merge_logs only processes specified job_ids"""
        json_dir = temp_workspace['json_dir']
        
        # Create multiple complete logs
        create_mock_json_log(json_dir, "sub001", "task1", "12345")
        create_mock_json_log(json_dir, "sub002", "task1", "12346")
        create_mock_json_log(json_dir, "sub003", "task2", "12347")
        
        # Merge only specific job_ids
        target_jobs = ["12345", "12347"]
        count = merge_json_to_db(json_dir, mock_db, job_ids=target_jobs)
        
        # Should merge 2 out of 3
        assert count == 2
        
        # Verify database
        conn = sqlite3.connect(mock_db)
        cursor = conn.execute("SELECT job_id FROM job_status ORDER BY job_id")
        merged_jobs = [row[0] for row in cursor.fetchall()]
        assert set(merged_jobs) == {"12345", "12347"}
        
        # Verify non-target job still exists in JSON
        non_target_file = Path(json_dir) / "task1" / "sub002_task1_12346.jsonl"
        assert non_target_file.exists()
        conn.close()
    
    def test_merge_archives_processed_files(self, temp_workspace, mock_db):
        """Test: merge_logs archives processed files"""
        json_dir = temp_workspace['json_dir']
        
        log_file = create_mock_json_log(json_dir, "sub001", "task1", "12345")
        
        # Run merge
        count = merge_json_to_db(json_dir, mock_db)
        assert count == 1
        
        # Original file should be moved to archived/
        assert not Path(log_file).exists()
        
        archived_file = Path(json_dir) / "task1" / "archived" / Path(log_file).name
        assert archived_file.exists()


class TestDAGMergeLogsIntegration:
    """Test merge_logs integration with DAG executor"""
    
    @pytest.fixture
    def mock_config(self):
        """Mock pipeline config"""
        return {
            'tasks': {
                'utility': [
                    {
                        'name': 'merge_logs',
                        'scripts': ['merge_logs.py'],
                        'profile': 'minimal'
                    }
                ]
            }
        }
    
    @pytest.fixture
    def mock_project_config(self):
        """Mock project config"""
        return {
            'prefix': 'sub-',
            'envir_dir': {
                'container_dir': '/containers'
            }
        }
    
    def test_merge_logs_added_to_execution_order(self, mock_config):
        """Test 2: merge_logs is added after all tasks in execution order"""
        executor = DAGExecutor(mock_config)
        
        # Mock task configs
        with patch('neuro_pipeline.pipeline.utils.config_utils.find_task_config_by_name_with_project') as mock_find:
            mock_find.side_effect = lambda name, proj: {
                'name': name,
                'scripts': [f'{name}.sh'],
                'profile': 'standard'
            }
            
            # Build DAG with tasks
            requested_tasks = ['task1', 'task2', 'task3']
            execution_order = executor.build_dag(requested_tasks)
            
            # Add merge_logs (simulating execute() logic)
            merge_config = mock_config['tasks']['utility'][0]
            executor.add_task('merge_logs', merge_config)
            for task_name in execution_order:
                executor.nodes['merge_logs'].add_dependency(task_name)
            execution_order.append('merge_logs')
            
            # Verify merge_logs is last
            assert execution_order[-1] == 'merge_logs'
            
            # Verify merge_logs depends on all tasks
            merge_node = executor.nodes['merge_logs']
            assert merge_node.dependencies == {'task1', 'task2', 'task3'}
    
    def test_merge_logs_not_added_in_dry_run(self, mock_config, mock_project_config):
        """Test: merge_logs is not added during dry_run"""
        executor = DAGExecutor(mock_config)
        
        with patch('neuro_pipeline.pipeline.utils.hpc_utils.submit_slurm_job') as mock_submit:
            mock_submit.return_value = 'dry_run_job'
            
            with patch('neuro_pipeline.pipeline.utils.config_utils.find_task_config_by_name_with_project') as mock_find:
                mock_find.side_effect = lambda name, proj: {
                    'name': name,
                    'scripts': [f'{name}.sh'],
                    'profile': 'standard'
                }
                
                requested_tasks = ['task1', 'task2']
                context = {'subjects': ['sub001']}
                
                all_job_ids, _ = executor.execute(
                    requested_tasks=requested_tasks,
                    input_dir='/input',
                    output_dir='/output',
                    work_dir='/work',
                    container_dir='/containers',
                    dry_run=True,  # Dry run mode
                    context=context,
                    project_config=mock_project_config
                )
                
                # Verify merge_logs was not executed
                assert 'merge_logs' not in all_job_ids


class TestEndToEndMergeLogsWorkflow:
    """End-to-end integration test"""
    
    def test_complete_workflow(self, temp_workspace, mock_db):
        """Test complete workflow: tasks -> merge_logs -> database"""
        json_dir = temp_workspace['json_dir']
        
        # Simulate 3 tasks completing
        task_jobs = {
            'task1': ['12345', '12346'],
            'task2': ['12347'],
            'task3': ['12348', '12349']
        }
        
        # Create JSON logs for all tasks
        for task_name, job_ids in task_jobs.items():
            for i, job_id in enumerate(job_ids):
                subject = f"sub00{i+1}"
                create_mock_json_log(json_dir, subject, task_name, job_id)
        
        # Also create some unrelated logs (different job_ids)
        create_mock_json_log(json_dir, "sub999", "other_task", "99999")
        
        # Flatten all target job_ids
        all_target_jobs = []
        for jobs in task_jobs.values():
            all_target_jobs.extend(jobs)
        
        # Run merge with job_ids filter
        count = merge_json_to_db(json_dir, mock_db, job_ids=all_target_jobs)
        
        # Should merge only target jobs (5 logs)
        assert count == 5
        
        # Verify database has exactly these jobs
        conn = sqlite3.connect(mock_db)
        cursor = conn.execute("SELECT job_id FROM job_status ORDER BY job_id")
        merged_jobs = sorted([row[0] for row in cursor.fetchall()])
        assert merged_jobs == sorted(all_target_jobs)
        
        # Verify unrelated log was not merged
        cursor = conn.execute("SELECT COUNT(*) FROM job_status WHERE job_id='99999'")
        assert cursor.fetchone()[0] == 0
        
        # Verify unrelated log still exists
        unrelated_file = Path(json_dir) / "other_task" / "sub999_other_task_99999.jsonl"
        assert unrelated_file.exists()
        
        conn.close()


class TestRebuildDb:
    """Tests for force-rebuild: rebuild a fresh db including archived JSONL files."""

    def test_rebuild_includes_archived_files(self, temp_workspace, mock_db):
        """Archived files are included in the rebuilt database."""
        json_dir = temp_workspace['json_dir']

        # Create a log, merge it (moves to archived/), then verify rebuild picks it up
        create_mock_json_log(json_dir, "sub001", "task1", "11111")
        merge_json_to_db(json_dir, mock_db)

        archived = Path(json_dir) / "task1" / "archived" / "sub001_task1_11111.jsonl"
        assert archived.exists()

        new_db_path, count = rebuild_db(temp_workspace['work_dir'], mock_db)
        assert count == 1

        conn = sqlite3.connect(new_db_path)
        row = conn.execute("SELECT job_id FROM job_status WHERE job_id='11111'").fetchone()
        conn.close()
        assert row is not None

    def test_rebuild_includes_active_and_archived(self, temp_workspace, mock_db):
        """Rebuild picks up both active (not yet merged) and archived JSONL files."""
        json_dir = temp_workspace['json_dir']

        # One archived
        create_mock_json_log(json_dir, "sub001", "task1", "11111")
        merge_json_to_db(json_dir, mock_db)

        # One still active
        create_mock_json_log(json_dir, "sub002", "task1", "22222")

        new_db_path, count = rebuild_db(temp_workspace['work_dir'], mock_db)
        assert count == 2

        conn = sqlite3.connect(new_db_path)
        jobs = {r[0] for r in conn.execute("SELECT job_id FROM job_status").fetchall()}
        conn.close()
        assert jobs == {"11111", "22222"}

    def test_rebuild_does_not_modify_original_db(self, temp_workspace, mock_db):
        """The original database is untouched after a rebuild."""
        json_dir = temp_workspace['json_dir']

        create_mock_json_log(json_dir, "sub001", "task1", "11111")
        merge_json_to_db(json_dir, mock_db)

        original_mtime = os.path.getmtime(mock_db)
        rebuild_db(temp_workspace['work_dir'], mock_db)

        assert os.path.getmtime(mock_db) == original_mtime

    def test_rebuild_creates_new_db_with_timestamp(self, temp_workspace, mock_db):
        """Rebuilt database has a timestamped name and is distinct from the original."""
        json_dir = temp_workspace['json_dir']
        create_mock_json_log(json_dir, "sub001", "task1", "11111")
        merge_json_to_db(json_dir, mock_db)

        new_db_path, _ = rebuild_db(temp_workspace['work_dir'], mock_db)

        assert os.path.exists(new_db_path)
        assert new_db_path != mock_db
        assert "pipeline_jobs_rebuild_" in os.path.basename(new_db_path)

    def test_rebuild_does_not_move_archived_files(self, temp_workspace, mock_db):
        """Files already in archived/ remain there after a rebuild."""
        json_dir = temp_workspace['json_dir']

        create_mock_json_log(json_dir, "sub001", "task1", "11111")
        merge_json_to_db(json_dir, mock_db)

        archived = Path(json_dir) / "task1" / "archived" / "sub001_task1_11111.jsonl"
        assert archived.exists()

        rebuild_db(temp_workspace['work_dir'], mock_db)

        assert archived.exists()

    def test_rebuild_raises_if_no_json_dir(self, temp_workspace, mock_db):
        """Raises FileNotFoundError when log/json/ does not exist."""
        import shutil as _shutil
        json_dir = temp_workspace['json_dir']
        _shutil.rmtree(json_dir)

        with pytest.raises(FileNotFoundError):
            rebuild_db(temp_workspace['work_dir'], mock_db)


if __name__ == '__main__':
    pytest.main([__file__, '-v', '-s'])