import os
from pathlib import Path

import yaml as _yaml
from neuro_pipeline.pipeline.utils.config_utils import _CONFIG_DIR
from dash import html, Input, Output, State, callback_context
import dash_bootstrap_components as dbc

def _alert_ok(message, extra=None):
    children = [html.I(className="fas fa-check-circle me-2"), message]
    if extra:
        children.append(extra)
    return dbc.Alert(children, color="success", className="mt-2")

def _alert_warn(message):
    return dbc.Alert(message, color="warning")

def _alert_err(message):
    return dbc.Alert(
        [html.I(className="fas fa-exclamation-triangle me-2"), message],
        color="danger"
    )

def _parse_yaml(content):
    """Returns (parsed, None) on success, (None, error_alert) on failure."""
    try:
        return _yaml.safe_load(content), None
    except _yaml.YAMLError as e:
        return None, _alert_err(f"Invalid YAML: {e}")

def _load_file(path):
    """Returns (content, None) on success, (None, error_message) on failure."""
    if not path:
        return None, "Please provide a file path."
    if not os.path.exists(path):
        return None, f"File not found: {path}"
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read(), None
    except Exception as e:
        return None, f"Error loading file: {e}"

def _save_file(path, content, restart_note=False):
    """Saves content to path. Returns success or error alert."""
    if not path:
        return _alert_warn("Please provide a file path before saving.")
    try:
        dir_part = os.path.dirname(path)
        if dir_part:
            os.makedirs(dir_part, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        if restart_note:
            return dbc.Alert([
                html.I(className="fas fa-check-circle me-2"),
                f"Saved to {path}",
                html.Br(),
                html.Small("Restart the pipeline process for changes to take effect.",
                           className="text-muted")
            ], color="success")
        return _alert_ok(f"Saved to {path}")
    except Exception as e:
        return _alert_err(f"Error saving: {e}")

def _trigger_id():
    ctx = callback_context
    if not ctx.triggered:
        return None
    return ctx.triggered[0]["prop_id"].split(".")[0]

def _resolve_path(raw_path):
    """Resolve a relative config path against the project root."""
    if raw_path and not Path(raw_path).is_absolute():
        return str(_CONFIG_DIR.parent / raw_path)
    return raw_path


# ── Tab 1: Project Config ─────────────────────────────────────────────────────

def autofill_project_config_path(project_name):
    if not project_name:
        return ""
    return f"config/project_config/{project_name}_config.yaml"


def generate_new_config_callback(_n_clicks, project_name, config_path):
    if not project_name:
        return dbc.Alert([
            html.I(className="fas fa-exclamation-triangle me-2"),
            "Please provide a project name"
        ], color="warning")

    try:
        from neuro_pipeline.pipeline.utils.generate_project_config import generate_project_config

        if config_path and not Path(config_path).is_absolute():
            resolved_dir = str(_CONFIG_DIR.parent / os.path.dirname(config_path))
        elif config_path:
            resolved_dir = os.path.dirname(config_path)
        else:
            resolved_dir = str(_CONFIG_DIR / "project_config")

        generate_project_config(project_name, resolved_dir)
        config_file = os.path.join(resolved_dir, f"{project_name}_config.yaml")

        return dbc.Alert([
            html.I(className="fas fa-check-circle me-2"),
            html.Div([
                f"Configuration template generated: {config_file}",
                html.Br(),
                "Click 'Load' to open it in the editor."
            ])
        ], color="success")

    except Exception as e:
        return dbc.Alert([
            html.I(className="fas fa-exclamation-triangle me-2"),
            f"Error generating configuration: {str(e)}"
        ], color="danger")


def load_config_callback(n_clicks, config_path):
    if n_clicks is None:
        return ""
    content, err = _load_file(_resolve_path(config_path))
    if err:
        return f"# {err}"
    return content


def save_config_callback(_save_clicks, _validate_clicks, config_path, yaml_content):
    try:
        if not yaml_content:
            return _alert_warn("Editor is empty.")
        _, err = _parse_yaml(yaml_content)
        if err:
            return err
        if _trigger_id() == "validate-config-btn":
            return _alert_ok("Valid YAML")
        return _save_file(_resolve_path(config_path), yaml_content)
    except Exception as e:
        return _alert_err(f"Unexpected error: {e}")


# ── Tab 2: Results Check ──────────────────────────────────────────────────────

def autofill_checks_path(project_name):
    if not project_name:
        return ""
    return f"config/results_check/{project_name}_checks.yaml"


def load_checks_callback(load_clicks, new_clicks, checks_path):
    ctx = callback_context
    if not ctx.triggered:
        return "", ""

    trigger_id = ctx.triggered[0]["prop_id"].split(".")[0]

    if trigger_id == "new-checks-btn":
        template = (
            "# Results check configuration\n"
            "# Keys must match task names defined in config.yaml\n\n"
            "# Example — required_files check:\n"
            "# rest_preprocess:\n"
            "#   output_path: \"{work_dir}/BIDS_derivatives/fmriprep/\"\n"
            "#   required_files:\n"
            "#     - pattern: \"sub-{subject}*.html\"\n"
            "#       min_size_kb: 500\n\n"
            "# Example — count_check:\n"
            "# recon:\n"
            "#   output_path: \"{work_dir}/BIDS/sub-{subject}/ses-{session}/\"\n"
            "#   count_check:\n"
            "#     anat:\n"
            "#       pattern: \"anat/*.nii.gz\"\n"
            "#       expected_count: 1\n"
            "#       tolerance: 0\n"
        )
        return template, dbc.Alert(
            "New template loaded. Fill in your task checks and save.",
            color="info", className="mt-2"
        )

    if not checks_path:
        return "", dbc.Alert("Please provide a file path.", color="warning")

    resolved = Path(checks_path)
    if not resolved.is_absolute():
        resolved = _CONFIG_DIR.parent / checks_path

    if not resolved.exists():
        return "", dbc.Alert(
            f"File not found: {resolved}. Click 'New' to start from a template.",
            color="warning"
        )

    try:
        content = resolved.read_text(encoding="utf-8")
        return content, dbc.Alert(
            [html.I(className="fas fa-check-circle me-2"), f"Loaded: {resolved}"],
            color="success", className="mt-2"
        )
    except Exception as e:
        return "", dbc.Alert(f"Error loading file: {e}", color="danger")


def save_checks_callback(save_clicks, validate_clicks, checks_path, yaml_content):
    try:
        if not yaml_content:
            return _alert_warn("Editor is empty.")
        parsed, err = _parse_yaml(yaml_content)
        if err:
            return err
        if _trigger_id() == "validate-checks-btn":
            if not isinstance(parsed, dict):
                return _alert_warn("Top-level must be a YAML mapping (task_name: ...).")
            return _alert_ok(f"Valid YAML · {len(parsed)} task(s) defined: {', '.join(parsed.keys())}")
        resolved = Path(checks_path)
        if not resolved.is_absolute():
            resolved = _CONFIG_DIR.parent / checks_path
        return _save_file(str(resolved), yaml_content)
    except Exception as e:
        return _alert_err(f"Unexpected error: {e}")


# ── Tab 3: Global Pipeline Config ─────────────────────────────────────────────

def load_global_config_callback(n_clicks):
    if not n_clicks:
        return "", ""
    config_path = _CONFIG_DIR / "config.yaml"
    content, err = _load_file(str(config_path))
    if err:
        return "", _alert_err(err)
    return content, _alert_ok(f"Loaded: {config_path}")


def save_global_config_callback(save_clicks, validate_clicks, yaml_content):
    try:
        if not yaml_content:
            return _alert_warn("Editor is empty.")
        parsed, err = _parse_yaml(yaml_content)
        if err:
            return err
        if _trigger_id() == "validate-global-config-btn":
            expected = {"prep", "intermed", "qc", "array_config"}
            missing = expected - (set(parsed.keys()) if isinstance(parsed, dict) else set())
            if missing:
                return _alert_warn(f"Valid YAML but missing expected top-level keys: {', '.join(sorted(missing))}")
            task_count = sum(len(v) for v in parsed.values() if isinstance(v, list))
            section_count = sum(1 for v in parsed.values() if isinstance(v, list))
            return _alert_ok(f"Valid YAML · {task_count} task(s) across {section_count} section(s)")
        config_path = _CONFIG_DIR / "config.yaml"
        return _save_file(str(config_path), yaml_content, restart_note=True)
    except Exception as e:
        return _alert_err(f"Unexpected error: {e}")


# ── Tab 4: HPC Config ────────────────────────────────────────────────────────

def load_hpc_config_callback(n_clicks):
    if not n_clicks:
        return "", ""
    config_path = _CONFIG_DIR / "hpc_config.yaml"
    content, err = _load_file(str(config_path))
    if err:
        return "", _alert_err(err)
    return content, _alert_ok(f"Loaded: {config_path}")


def save_hpc_config_callback(_save_clicks, _validate_clicks, yaml_content):
    try:
        if not yaml_content:
            return _alert_warn("Editor is empty.")
        parsed, err = _parse_yaml(yaml_content)
        if err:
            return err
        if _trigger_id() == "validate-hpc-config-btn":
            expected = {"resource_profiles", "defaults"}
            missing = expected - (set(parsed.keys()) if isinstance(parsed, dict) else set())
            if missing:
                return _alert_warn(f"Valid YAML but missing expected keys: {', '.join(sorted(missing))}")
            profile_count = len(parsed.get("resource_profiles", {}))
            return _alert_ok(f"Valid YAML · {profile_count} resource profile(s)")
        config_path = _CONFIG_DIR / "hpc_config.yaml"
        return _save_file(str(config_path), yaml_content, restart_note=True)
    except Exception as e:
        return _alert_err(f"Unexpected error: {e}")


# ── Registration ──────────────────────────────────────────────────────────────

def register_config_callbacks(app):

    app.callback(
        Output("config-file-path", "value"),
        Input("new-project-name", "value"),
        prevent_initial_call=True
    )(autofill_project_config_path)

    app.callback(
        Output("new-config-result", "children"),
        [Input("generate-new-config-btn", "n_clicks")],
        [State("new-project-name", "value"),
         State("config-file-path", "value")],
        prevent_initial_call=True
    )(generate_new_config_callback)

    app.callback(
        Output("yaml-editor", "value"),
        [Input("load-config-btn", "n_clicks")],
        [State("config-file-path", "value")]
    )(load_config_callback)

    app.callback(
        Output("yaml-validation-result", "children"),
        [Input("save-config-btn", "n_clicks"),
         Input("validate-config-btn", "n_clicks")],
        [State("config-file-path", "value"),
         State("yaml-editor", "value")],
        prevent_initial_call=True
    )(save_config_callback)

    app.callback(
        Output("checks-file-path", "value"),
        Input("checks-project-name", "value"),
        prevent_initial_call=True
    )(autofill_checks_path)

    app.callback(
        [Output("checks-yaml-editor", "value"),
         Output("checks-validation-result", "children")],
        [Input("load-checks-btn", "n_clicks"),
         Input("new-checks-btn", "n_clicks")],
        State("checks-file-path", "value"),
        prevent_initial_call=True
    )(load_checks_callback)

    app.callback(
        Output("checks-validation-result", "children", allow_duplicate=True),
        [Input("save-checks-btn", "n_clicks"),
         Input("validate-checks-btn", "n_clicks")],
        [State("checks-file-path", "value"),
         State("checks-yaml-editor", "value")],
        prevent_initial_call=True
    )(save_checks_callback)

    app.callback(
        [Output("global-config-editor", "value"),
         Output("global-config-result", "children")],
        Input("load-global-config-btn", "n_clicks"),
        prevent_initial_call=True
    )(load_global_config_callback)

    app.callback(
        Output("global-config-result", "children", allow_duplicate=True),
        [Input("save-global-config-btn", "n_clicks"),
         Input("validate-global-config-btn", "n_clicks")],
        State("global-config-editor", "value"),
        prevent_initial_call=True
    )(save_global_config_callback)

    app.callback(
        [Output("hpc-config-editor", "value"),
         Output("hpc-config-result", "children")],
        Input("load-hpc-config-btn", "n_clicks"),
        prevent_initial_call=True
    )(load_hpc_config_callback)

    app.callback(
        Output("hpc-config-result", "children", allow_duplicate=True),
        [Input("save-hpc-config-btn", "n_clicks"),
         Input("validate-hpc-config-btn", "n_clicks")],
        State("hpc-config-editor", "value"),
        prevent_initial_call=True
    )(save_hpc_config_callback)
