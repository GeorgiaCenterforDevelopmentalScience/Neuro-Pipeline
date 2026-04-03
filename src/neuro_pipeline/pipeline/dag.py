"""
The dependency chain is declared via input_from in config.yaml. 
For example, dwi_preprocess has input_from: recon_bids, which means if dwi_preprocess is requested, 
recon_bids will be added as a dependency.
"""

import os
from typing import List, Optional, Dict, Any, Set
from dataclasses import dataclass, field
from collections import deque
import typer
from .utils.output_checker import OutputChecker

@dataclass
class TaskNode:
    """Task node in DAG"""
    name: str
    task_config: Dict[str, Any]
    dependencies: Set[str] = field(default_factory=set)
    job_ids: List[str] = field(default_factory=list)
    completed: bool = False
    
    def add_dependency(self, dep_name: str):
        self.dependencies.add(dep_name)


class DAGExecutor:
    """DAG-based task executor"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.nodes: Dict[str, TaskNode] = {}
        self.execution_order: List[str] = []
        self.project_config = None
    
    def add_task(self, task_name: str, task_config: Dict[str, Any], dependencies: Optional[List[str]] = None):
        if task_name in self.nodes:
            return
        node = TaskNode(
            name=task_name,
            task_config=task_config,
            dependencies=set(dependencies or [])
        )
        self.nodes[task_name] = node
    
    def build_dag(self, requested_tasks: List[str], rest_dependencies: List[tuple] = None,
                  dwi_dependencies: List[tuple] = None) -> List[str]:
        """Build DAG from requested tasks"""
        for task_name in requested_tasks:
            self._add_task_with_dependencies(task_name, requested_tasks)
        
        # Register explicit inter-task dependencies for each pipeline
        self._register_dependencies(rest_dependencies)
        self._register_dependencies(dwi_dependencies)
        
        # Debug output
        if os.environ.get('DEBUG_DEPENDENCIES'):
            self.print_dependency_graph()
        
        return self._topological_sort()

    def _register_dependencies(self, dep_list: List[tuple] = None):
        """Register explicit dependencies from a pipeline dependency list"""
        if not dep_list:
            return
        for dependency_item in dep_list:
            if isinstance(dependency_item, tuple) and len(dependency_item) == 2:
                task_name, deps = dependency_item
                if task_name in self.nodes:
                    for dep in deps:
                        if dep in self.nodes:
                            self.nodes[task_name].add_dependency(dep)
    
    def _add_task_with_dependencies(self, task_name: str, requested_tasks: List[str] = None):
        """Add task and its dependencies to DAG"""
        if task_name in self.nodes:
            return
        
        from .utils.config_utils import find_task_config_by_name_with_project
        task_config = find_task_config_by_name_with_project(task_name, getattr(self, 'project_config', None))
        
        if not task_config:
            typer.echo(f"Warning: No configuration found for {task_name}")
            return
        
        self.add_task(task_name, task_config)
        
        # Handle various dependency types
        self._handle_input_from_dependencies(task_name, task_config, requested_tasks)
        self._handle_task_postprocess_dependencies(task_name, requested_tasks)
        self._handle_task_preprocess_structural_dependencies(task_name, requested_tasks)
        self._handle_mriqc_group_dependencies(task_name, requested_tasks)

    def _handle_mriqc_group_dependencies(self, task_name: str, requested_tasks: List[str] = None):
        """Handle MRIQC group dependencies - post must wait for prep (individual) to complete"""
        if not requested_tasks or task_name != 'mriqc_post':
            return

        if 'mriqc_preprocess' in requested_tasks:
            self.nodes[task_name].add_dependency('mriqc_preprocess')
            self._add_task_with_dependencies('mriqc_preprocess', requested_tasks)

    def _handle_input_from_dependencies(self, task_name: str, task_config: Dict[str, Any], requested_tasks: List[str] = None):
        """Handle input_from dependencies"""
        input_from = task_config.get('input_from')
        if not input_from:
            return
            
        dependency_mapping = {
            'unzip': 'unzip',
            'recon_bids': 'recon_bids',
            'mriqc': 'mriqc_preprocess',
            'mriqc_preprocess': 'mriqc_preprocess',
            'rest_preprocess': 'rest_preprocess',
            'dwi_preprocess': 'dwi_preprocess',
        }
        
        dep_task = dependency_mapping.get(input_from)
        if dep_task and requested_tasks and dep_task in requested_tasks:
            self.nodes[task_name].add_dependency(dep_task)
            self._add_task_with_dependencies(dep_task, requested_tasks)

    # TODO: modify `task` arguments, too much hard coded syntax
    def _handle_task_postprocess_dependencies(self, task_name: str, requested_tasks: List[str] = None):
        """Handle postprocess dependencies"""
        if not requested_tasks or not task_name.endswith('_postprocess'):
            return
            
        task_type = task_name.replace('_postprocess', '')
        prep_task = f'{task_type}_preprocess'
        
        if prep_task in requested_tasks:
            self.nodes[task_name].add_dependency(prep_task)

    def _handle_task_preprocess_structural_dependencies(self, task_name: str, requested_tasks: List[str] = None):
        """Handle preprocess dependencies on structural tasks"""
        if not requested_tasks or not task_name.endswith('_preprocess'):
            return
        
        # Check if it's a task section task
        from .utils.config_utils import get_all_task_names
        if task_name not in get_all_task_names('task'):
            return
        
        structural_tasks = [task for task in requested_tasks if task.startswith('afni_')]
        for structural_task in structural_tasks:
            self.nodes[task_name].add_dependency(structural_task)

    def _topological_sort(self) -> List[str]:
        """Topological sort on DAG"""
        in_degree = {name: len(node.dependencies) for name, node in self.nodes.items()}
        queue = deque([name for name, degree in in_degree.items() if degree == 0])
        result = []
        
        while queue:
            current = queue.popleft()
            result.append(current)
            for name, node in self.nodes.items():
                if current in node.dependencies:
                    in_degree[name] -= 1
                    if in_degree[name] == 0:
                        queue.append(name)
        
        if len(result) != len(self.nodes):
            raise ValueError("Circular dependency detected")
        
        return result
    
    def print_dependency_graph(self):
        """Print dependency graph for debugging"""
        print("\n=== Dependency Graph ===")
        for task_name, node in self.nodes.items():
            if node.dependencies:
                deps_str = ", ".join(sorted(node.dependencies))
                print(f"{task_name} -> [{deps_str}]")
            else:
                print(f"{task_name} -> []")
        print("=======================\n")
    
    def execute(self, requested_tasks, input_dir, output_dir, work_dir, container_dir,
                dry_run, context=None, option_env=None, project_config=None, 
                rest_dependencies: List[tuple] = None, dwi_dependencies: List[tuple] = None,
                original_work_dir=None, db_path: Optional[str] = None,
                resume: bool = False, checks_config_path: Optional[str] = None):
        """Execute tasks in DAG order"""
        if context is None:
            context = {}
        
        self.project_config = project_config
        all_job_ids = {}

        # Resume: initialise OutputChecker once if --resume was requested
        checker = None
        if resume and checks_config_path:
            prefix = (project_config or {}).get('prefix', 'sub-')
            session = (option_env or {}).get('session', '01')
            checker = OutputChecker(
                config_path=checks_config_path,
                work_dir=work_dir,
                prefix=prefix,
                session=session,
            )
            checker.warn_missing_configs(requested_tasks)
        
        # Build DAG for requested tasks
        execution_order = self.build_dag(requested_tasks, rest_dependencies, dwi_dependencies)
        
        # Execute all tasks
        for task_name in execution_order:
            node = self.nodes[task_name]
            wait_jobs = []
            for dep_name in node.dependencies:
                if dep_name in all_job_ids:
                    wait_jobs.extend(all_job_ids[dep_name])
            
            # Prepare execution parameters
            is_merge_task = (task_name == 'merge_logs')
            all_subjects = context.get('subjects', [])

            # Resume: filter already-completed subjects
            if checker and not is_merge_task and not dry_run:
                pending = checker.get_pending_subjects(task_name, all_subjects)
                if len(pending) < len(all_subjects):
                    skipped = sorted(set(all_subjects) - set(pending))
                    typer.echo(
                        f"[resume] {task_name}: skipping {len(skipped)} completed subject(s): "
                        f"{', '.join(skipped)}"
                    )
                if not pending:
                    typer.echo(f"[resume] {task_name}: all subjects complete, skipping task.")
                    all_job_ids[task_name] = []
                    node.completed = True
                    continue
                subjects_str = ','.join(pending)
            else:
                subjects_str = 'dummy' if is_merge_task else ','.join(all_subjects)

            task_env = self._prepare_task_env(option_env, all_job_ids if is_merge_task else None)
            
            # Execute task
            job_ids = self._execute_single_task(
                node, subjects=subjects_str,
                input_dir=input_dir, output_dir=output_dir, work_dir=work_dir,
                container_dir=container_dir, dry_run=(False if is_merge_task else dry_run),
                wait_jobs=wait_jobs, option_env=task_env,
                project_config=project_config, requested_tasks=requested_tasks,
                original_work_dir=original_work_dir, db_path=db_path
            )
            
            # Record results
            all_job_ids[task_name] = job_ids or []
            node.job_ids = job_ids or []
            node.completed = True
        
        return all_job_ids, context

    def _prepare_task_env(self, option_env: Optional[Dict], all_job_ids: Optional[Dict] = None) -> Dict:
        """Prepare environment variables for task execution"""
        task_env = dict(option_env or {})  # Simplify
        
        # Add job_ids for merge_logs task
        if all_job_ids:
            all_jobs = [job for jobs in all_job_ids.values() for job in jobs]
            task_env['JOB_IDS'] = ','.join(all_jobs)
        
        return task_env

    def _get_merge_config(self) -> Optional[Dict[str, Any]]:
        """Get merge_logs config from tasks sections"""
        for section in self.config.get('tasks', {}).values():
            if isinstance(section, list):
                for task in section:
                    if task.get('name') == 'merge_logs':
                        return task
        return None       

    def _execute_single_task(self, node: 'TaskNode', subjects: str, input_dir: str,
                        output_dir: str, work_dir: str, container_dir: str,
                        dry_run: bool, wait_jobs: Optional[list] = None, 
                        option_env=None, project_config=None, 
                        requested_tasks: List[str] = None, 
                        original_work_dir: Optional[str] = None,
                        db_path: Optional[str] = None) -> list:
        """Execute single task"""
        task_config = node.task_config
        scripts = task_config.get('scripts', [])
        
        if not scripts:
            return []
        
        from .utils.hpc_utils import submit_slurm_job
        
        job_ids = []
        for script in scripts:
            job_id = submit_slurm_job(
                script_name=script,
                subjects=subjects,
                input_dir=input_dir,
                output_dir=output_dir,
                work_dir=work_dir,
                container_dir=container_dir,
                env_vars=None,
                wait_jobs=wait_jobs,
                task_config=task_config,
                dry_run=dry_run,
                option_env=option_env,
                project_config=project_config,
                requested_tasks=requested_tasks,
                original_work_dir=original_work_dir,
                db_path=db_path
            )
            if job_id:
                job_ids.append(job_id)
        
        return job_ids


class TaskRegistry:
    """Registry for task expansion"""
    
    def __init__(self):
        from .utils.config_utils import PrepChoice, MRIQCChoice

        self.task_expanders = {
            PrepChoice.unzip_recon: self._expand_unzip_recon,
            MRIQCChoice.all: self._expand_mriqc_all,
        }
    
    def expand_tasks(self, **kwargs) -> List[str]:
        """Expand task choices into concrete task names"""
        tasks = []
        
        # Prep tasks
        if kwargs.get('prep'):
            prep_choice = kwargs['prep']
            if prep_choice in self.task_expanders:
                tasks.extend(self.task_expanders[prep_choice](kwargs))
            else:
                prep_mapping = {
                    'recon': 'recon_bids',
                    'unzip': 'unzip',
                }
                task_name = prep_mapping.get(prep_choice.value, prep_choice.value)
                tasks.append(task_name)
        
        # Structural tasks
        if kwargs.get('structural'):
            from .utils.config_utils import get_tasks_from_section
            tasks.extend([name for name, _ in get_tasks_from_section('structural')])
        
        # MRIQC tasks
        if kwargs.get('mriqc'):
            mriqc_choice = kwargs['mriqc']
            if mriqc_choice in self.task_expanders:
                tasks.extend(self.task_expanders[mriqc_choice](kwargs))
            else:
                mriqc_mapping = {
                    'individual': 'mriqc_preprocess',
                    'group': 'mriqc_post',
                }
                tasks.append(mriqc_mapping.get(mriqc_choice.value, f"mriqc_{mriqc_choice.value}"))
        
        # Rest tasks - simplified
        if kwargs.get('rest_prep') or kwargs.get('rest_post'):
            rest_tasks = self._expand_rest_tasks(kwargs)
            tasks.extend([task_name for task_name, _ in rest_tasks])
        
        # DWI tasks
        if kwargs.get('dwi_prep') or kwargs.get('dwi_post'):
            dwi_tasks = self._expand_dwi_tasks(kwargs)
            tasks.extend([task_name for task_name, _ in dwi_tasks])
        
        # Task prep
        if kwargs.get('task_prep'):
            tasks.extend(kwargs['task_prep'])
        
        # Task post
        if kwargs.get('task_post'):
            tasks.extend(kwargs['task_post'])
        
        return tasks
    
    def _expand_unzip_recon(self, kwargs) -> List[str]:
        return ['unzip', 'recon_bids']
    
    def _expand_mriqc_all(self, kwargs) -> List[str]:
        from .utils.config_utils import get_tasks_from_section
        return [name for name, _ in get_tasks_from_section('qc')]

    def _expand_rest_tasks(self, kwargs) -> List[tuple]:
        """Expand rest tasks from config, driven by stage field."""
        from .utils.config_utils import get_tasks_from_section
        tasks = []
        if kwargs.get('rest_prep'):
            tasks.extend(get_tasks_from_section('rest', 'prep'))
        if kwargs.get('rest_post'):
            tasks.extend(get_tasks_from_section('rest', 'post'))
        return tasks

    def _expand_dwi_tasks(self, kwargs) -> List[tuple]:
        """Expand DWI tasks from config, driven by stage field."""
        from .utils.config_utils import get_tasks_from_section
        tasks = []
        if kwargs.get('dwi_prep'):
            tasks.extend(get_tasks_from_section('task_dwi', 'prep'))
        if kwargs.get('dwi_post'):
            tasks.extend(get_tasks_from_section('task_dwi', 'post'))
        return tasks

    def _expand_task_args(self, kwargs):
        """Expand task arguments"""
        if kwargs.get('task'):
            return kwargs['task']
        
        return []