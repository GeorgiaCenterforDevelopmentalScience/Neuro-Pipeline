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

    # TODO: make sure {ID} without prefix can be detected
    global_params = {
        'prefix': project_config.get('prefix', {}),
        'envir_dir': project_config.get('envir_dir', {}),
        'template_name': project_config.get('template', {})  
    }

    return {
        'global': global_params,
        'project': project_config,
        'setup': project_config.get('setup', {}),
        'modules': project_config.get('modules', {})
    }

# TODO: hard coded is too much
def get_task_params(project_config: dict, task_type: str, task_name: str = None):
    """Get parameters for specific task"""
    project_params = project_config['project']
    
    if task_type == 'structural':
        return project_params.get('setup', {}).get('structural', {})
    
    elif task_type == 'rest':
        if task_name == 'fmriprep':
            return project_params.get('rest_fmriprep', {})
        elif task_name == 'afni':
            return project_params.get('rest_afni', {})
        else:
            raise ValueError(f"Unknown rest task: {task_name}")
    
    elif task_type == 'task':
        if task_name == 'kidvid':
            return project_params.get('task_kidvid', {})
        elif task_name == 'cards':
            return project_params.get('task_cards', {})
        elif task_name == 'all':
            return {
                'kidvid': project_params.get('task_kidvid', {}),
                'cards': project_params.get('task_cards', {})
            }
        else:
            raise ValueError(f"Unknown task: {task_name}")
    
    else:
        raise ValueError(f"Unknown task type: {task_type}")


def resolve_template_paths(params: dict, global_config: dict):
    """Resolve template paths by replacing placeholders"""
    resolved_params = params.copy()
    
    template_dir = global_config['envir_dir'].get('template_dir', '')
    template_names = global_config.get('template_name', {})
    
    for key, value in resolved_params.items():
        if isinstance(value, str) and '{template_dir}' in value:
            resolved_params[key] = value.replace('{template_dir}', template_dir)
        
        if isinstance(value, str) and '{' in value and '}' in value:
            for template_key, template_value in template_names.items():
                placeholder = f"{{{template_key}}}"
                if placeholder in value:
                    resolved_params[key] = value.replace(placeholder, template_value)
    
    return resolved_params