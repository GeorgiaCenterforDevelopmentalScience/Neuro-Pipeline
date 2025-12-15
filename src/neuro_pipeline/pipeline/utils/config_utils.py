from enum import Enum
from typing import List, Optional, Dict, Any
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


# Enum definitions
class PrepChoice(str, Enum):
    unzip = "unzip"
    recon = "recon"
    unzip_recon = "unzip_recon"


class StructuralChoice(str, Enum):
    volume = "volume"


class RestPrepChoice(str, Enum):
    """Rest preprocessing tool"""
    fmriprep = "fmriprep"


class RestPostChoice(str, Enum):
    """Rest postprocessing tool"""
    xcpd = "xcpd"


class TaskChoice(str, Enum):
    """Task types"""
    kidvid = "kidvid"
    cards = "cards"
    all = "all"


class MRIQCChoice(str, Enum):
    group = "group"
    individual = "individual"
    all = "all"


def clean_all_only(argval: List[str], name: str) -> List[str]:
    """Clean up 'all' when mixed with other options"""
    if isinstance(argval, list) and 'all' in argval and len(argval) > 1:
        typer.echo(f"Warning: '{name}' has 'all' + other values. Using 'all' only.")
        return ['all']
    return argval

# TODO: need add to pytest
def find_task_config_by_name(task_name: str) -> Optional[Dict[str, Any]]:
    """Find task configuration by name"""
    tasks = config.get('tasks', {})
    for section_name, section_tasks in tasks.items():
        if isinstance(section_tasks, list):
            for task in section_tasks:
                if task.get('name') == task_name:
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