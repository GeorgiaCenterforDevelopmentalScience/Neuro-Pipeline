from enum import Enum
from typing import List, Optional, Dict, Any, Tuple
import typer
import yaml
from pathlib import Path

# Load global config
config_path = Path(__file__).parent.parent / "config" / "config.yaml"
try:
    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
except FileNotFoundError:
    config = {}


class PrepChoice(str, Enum):
    unzip = "unzip"
    recon = "recon"
    unzip_recon = "unzip_recon"


class MRIQCChoice(str, Enum):
    group = "group"
    individual = "individual"
    all = "all"

def get_tasks_from_section(section: str, stage: str = None) -> List[Tuple[str, List[str]]]:
    section_tasks = config.get(section, [])
    result = []
    for task in section_tasks:
        if not isinstance(task, dict):
            continue
        if stage is None or task.get('stage') == stage:
            dep = task.get('input_from')
            deps = [dep] if dep else []
            result.append((task['name'], deps))
    return result


def get_tasks_by_suffix(suffix: str, category: str = 'task') -> List[str]:
    """Get task names by suffix pattern"""
    all_tasks = config.get(category, [])
    return [t['name'] for t in all_tasks if isinstance(t, dict) and suffix in t['name']]

def get_all_task_names(category: str = 'task') -> List[str]:
    """Get all task names in category"""
    all_tasks = config.get(category, [])
    return [t['name'] for t in all_tasks if isinstance(t, dict)]

def validate_task_name(task_name: str, category: str = 'task') -> bool:
    """Check if task exists"""
    return task_name in get_all_task_names(category)

def expand_task_names(task_list: List[str], suffix: str) -> List[str]:
    """Expand short names to full task names"""
    return [f"{task}{suffix}" for task in task_list]

def clean_all_only(argval: List[str], name: str) -> List[str]:
    """Clean up 'all' when mixed with other options"""
    if isinstance(argval, list) and 'all' in argval and len(argval) > 1:
        typer.echo(f"Warning: '{name}' has 'all' + other values. Using 'all' only.")
        return ['all']
    return argval

# TODO: need add to pytest
def find_task_config_by_name(task_name: str) -> Optional[Dict[str, Any]]:
    """Find task configuration by name"""
    for section_name, section_tasks in config.items():
        if isinstance(section_tasks, list):
            for task in section_tasks:
                if isinstance(task, dict) and task.get('name') == task_name:
                    return task
        elif isinstance(section_tasks, dict):
            if section_name == task_name:
                task_config = section_tasks.copy()
                task_config['name'] = task_name
                return task_config
    return None


def find_task_config_by_name_with_project(task_name: str, project_config: dict = None) -> Optional[Dict[str, Any]]:
    """Find task configuration, merging global and project configs"""
    global_task_config = find_task_config_by_name(task_name)

    if not global_task_config:
        typer.echo(f"Warning: No global config for: {task_name}")
        return None

    if project_config and 'setup' in project_config:
        setup_config = project_config['setup']

        for section_name, section_tasks in setup_config.items():
            if isinstance(section_tasks, list):
                for task in section_tasks:
                    if task.get('name') == task_name:
                        merged_config = global_task_config.copy()
                        merged_config.update(task)
                        return merged_config
            elif isinstance(section_tasks, dict) and section_name == task_name:
                merged_config = global_task_config.copy()
                merged_config.update(section_tasks)
                return merged_config

    return global_task_config


def load_project_config(project_name: str, config_dir: str = None):
    """Load project configuration from YAML file"""
    if config_dir is None:
        config_dir = Path(__file__).parent.parent / "config" / "project_config"

    config_file = Path(config_dir) / f"{project_name}_config.yaml"

    if not config_file.exists():
        raise FileNotFoundError(f"Config not found: {config_file}")

    with open(config_file, 'r', encoding='utf-8') as f:
        project_config = yaml.safe_load(f)

    return project_config
