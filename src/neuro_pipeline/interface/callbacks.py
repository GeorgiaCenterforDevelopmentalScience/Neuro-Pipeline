import os
import json
import subprocess
import sys
from datetime import datetime

from dash import html, dcc, Input, Output, State, callback_context
import dash_bootstrap_components as dbc

def register_callbacks(app):
    """Register all callbacks for the application"""
    
    # Import and register job monitor callbacks
    from .job_monitor_callbacks import register_job_monitor_callbacks
    register_job_monitor_callbacks(app)

    # Subject detection and manual input callback
    @app.callback(
        [Output("subjects-detection-result", "children"),
         Output("subjects-list-container", "children"),
         Output("subjects-store", "data"),
         Output("manual-subjects", "value")],
        [Input("detect-subjects-btn", "n_clicks"),
         Input("manual-subjects", "value"),
         Input("clear-subjects-btn", "n_clicks")],
        [State("subject-prefix", "value"),
         State("current-dir", "value")]
    )
    def detect_subjects_callback(detect_clicks, manual_input, clear_clicks, prefix, directory):
        ctx = callback_context
        if not ctx.triggered:
            return "", "", [], ""
        
        trigger_id = ctx.triggered[0]['prop_id'].split('.')[0]
        
        # Handle clear button
        if trigger_id == "clear-subjects-btn":
            return "", "", [], ""
        
        # Handle manual subject input
        if trigger_id == "manual-subjects" and manual_input:
            try:
                # Remove prefix from each subject if present
                subjects = []
                for s in manual_input.split(","):
                    s = s.strip()
                    if s:
                        if s.startswith(prefix):
                            s = s[len(prefix):]
                        subjects.append(s)
                
                if not subjects:
                    return "", "", [], manual_input
                
                result = dbc.Alert([
                    html.I(className="fas fa-check-circle me-2"),
                    html.Div([
                        f"Manually entered {len(subjects)} subjects",
                        html.Br(),
                        html.Small(f"Subjects: {', '.join(subjects)}", className="text-muted")
                    ])
                ], color="info")
                
                return result, "", subjects, manual_input
                
            except Exception as e:
                return dbc.Alert(f"Error parsing subjects: {str(e)}", color="danger"), "", [], manual_input
        
        # Handle automatic detection
        if trigger_id == "detect-subjects-btn":
            if detect_clicks is None:
                return "", "", [], ""
            
            if not directory:
                return dbc.Alert("Please provide a directory", color="warning"), "", [], ""

            try:
                from ..pipeline.utils.detect_subjects import detect_subjects
                
                subjects = detect_subjects(directory, prefix)
                
                if not subjects:
                    result = dbc.Alert(f"No subjects found with prefix '{prefix}' in {directory}", color="warning")
                    return result, "", [], ""
                
                result = dbc.Alert([
                    html.I(className="fas fa-check-circle me-2"),
                    html.Div([
                        f"Found {len(subjects)} subjects",
                        html.Br(),
                        html.Small(f"Subjects: {', '.join(subjects)}", className="text-muted")
                    ])
                ], color="success")
                
                return result, "", subjects, ""
                
            except Exception as e:
                error_msg = f"Error detecting subjects: {str(e)}"
                return dbc.Alert([
                    html.I(className="fas fa-exclamation-triangle me-2"),
                    error_msg
                ], color="danger"), "", [], ""
        
        return "", "", [], ""
    
    # Generate command preview callback
    @app.callback(
        [Output("command-preview", "children"),
        Output("pipeline-commands-store", "data")],
        [Input("generate-commands-btn", "n_clicks")],
        [State("subjects-store", "data"),
        State("input-dir", "value"),
        State("output-dir", "value"),
        State("work-dir", "value"),
        State("project-name", "value"),
        State("session-id", "value"),
        State("prep-options", "value"),
        State("structural-radio", "value"),
        State("bids-prep-checklist", "value"),
        State("bids-post-checklist", "value"),
        State("staged-prep-checklist", "value"),
        State("staged-post-checklist", "value"),
        State("mriqc-options", "value"),
        State("dry-run-checkbox", "value"),
        State("resume-checkbox", "value")]
    )
    def generate_command_callback(n_clicks, subjects, input_dir, output_dir, work_dir,
                                project_name, session, prep_option, structural_value,
                                bids_prep, bids_post, staged_prep, staged_post,
                                mriqc_option, dry_run, resume):
        if n_clicks is None:
            return "Click 'Generate Command' to preview the pipeline command", {}

        if not subjects:
            return "Error: No subjects selected. Please detect subjects first.", {}

        if not all([input_dir, output_dir, work_dir, project_name]):
            return "Error: Please fill in all required fields (input, output, work directories, project name)", {}

        try:
            # Build command parts
            cmd_parts = []

            # Add directory variables
            cmd_parts.append(f'input_dir="{input_dir}"')
            cmd_parts.append(f'output_dir="{output_dir}"')
            cmd_parts.append(f'work_dir="{work_dir}"')
            cmd_parts.append('')

            # Start neuropipe command
            cmd_parts.append('neuropipe run \\')

            # Add subjects
            subjects_str = ",".join(subjects)
            cmd_parts.append(f'  --subjects {subjects_str} \\')

            # Add directories
            cmd_parts.append(f'  --input "$input_dir" \\')
            cmd_parts.append(f'  --output "$output_dir" \\')
            cmd_parts.append(f'  --work "$work_dir" \\')

            # Add session and project
            cmd_parts.append(f'  --session {session} \\')
            cmd_parts.append(f'  --project {project_name} \\')

            if prep_option and prep_option != "none":
                cmd_parts.append(f'  --prep {prep_option} \\')

            if structural_value and structural_value != "none":
                cmd_parts.append(f'  --structural \\')

            if bids_prep:
                cmd_parts.append(f'  --bids-prep {",".join(bids_prep)} \\')
            if bids_post:
                cmd_parts.append(f'  --bids-post {",".join(bids_post)} \\')

            if staged_prep:
                cmd_parts.append(f'  --staged-prep {",".join(staged_prep)} \\')
            if staged_post:
                cmd_parts.append(f'  --staged-post {",".join(staged_post)} \\')

            if mriqc_option and mriqc_option != "none":
                cmd_parts.append(f'  --mriqc {mriqc_option} \\')

            if dry_run and "dry_run" in dry_run:
                cmd_parts.append(f'  --dry-run \\')

            if resume and "resume" in resume:
                cmd_parts.append(f'  --resume')
            else:
                if cmd_parts[-1].endswith(' \\'):
                    cmd_parts[-1] = cmd_parts[-1][:-2]

            command_str = "\n".join(cmd_parts)

            command_data = {
                "subjects": subjects,
                "input_dir": input_dir,
                "output_dir": output_dir,
                "work_dir": work_dir,
                "project_name": project_name,
                "session": session,
                "prep_option": prep_option,
                "structural_value": structural_value,
                "bids_prep": bids_prep,
                "bids_post": bids_post,
                "staged_prep": staged_prep,
                "staged_post": staged_post,
                "mriqc_option": mriqc_option,
                "dry_run": dry_run,
                "resume": resume
            }

            return command_str, command_data

        except Exception as e:
            error_msg = f"Error generating command: {str(e)}"
            return error_msg, {}
    
    # Execute pipeline callback
    @app.callback(
        Output("execution-status", "children"),
        [Input("execute-pipeline-btn", "n_clicks")],
        [State("pipeline-commands-store", "data"),
        State("dry-run-checkbox", "value"),
        State("resume-checkbox", "value")],
        prevent_initial_call=True
    )
    def execute_pipeline_callback(n_clicks, command_data, dry_run, resume):
        if n_clicks is None:
            return ""
        
        if not command_data:
            return dbc.Alert([
                html.I(className="fas fa-exclamation-triangle me-2"),
                "No command available. Please generate command first."
            ], color="warning")
        
        try:
            # Convert checkbox to boolean
            is_dry_run = "dry_run" in (dry_run or [])
            
            # Build command
            cmd = ["neuropipe", "run"]
            
            # Add subjects
            subjects_str = ",".join(command_data["subjects"])
            cmd.extend(["--subjects", subjects_str])
            
            # Add directories
            cmd.extend(["--input", command_data["input_dir"]])
            cmd.extend(["--output", command_data["output_dir"]])
            cmd.extend(["--work", command_data["work_dir"]])
            
            # Add session and project
            cmd.extend(["--session", command_data["session"]])
            cmd.extend(["--project", command_data["project_name"]])
            
            # Add prep
            if command_data.get("prep_option") and command_data["prep_option"] != "none":
                cmd.extend(["--prep", command_data["prep_option"]])

            # Add structural flag
            if command_data.get("structural_value") and command_data["structural_value"] != "none":
                cmd.append("--structural")

            # Add BIDS pipelines
            if command_data.get("bids_prep"):
                cmd.extend(["--bids-prep", ",".join(command_data["bids_prep"])])
            if command_data.get("bids_post"):
                cmd.extend(["--bids-post", ",".join(command_data["bids_post"])])

            # Add staged pipelines
            if command_data.get("staged_prep"):
                cmd.extend(["--staged-prep", ",".join(command_data["staged_prep"])])
            if command_data.get("staged_post"):
                cmd.extend(["--staged-post", ",".join(command_data["staged_post"])])

            # Add MRIQC
            if command_data.get("mriqc_option") and command_data["mriqc_option"] != "none":
                cmd.extend(["--mriqc", command_data["mriqc_option"]])
            
            # Add dry run
            if is_dry_run:
                cmd.append("--dry-run")
            
            # Add resume flag
            is_resume = "resume" in (resume or []) or "resume" in (command_data.get("resume") or [])
            if is_resume:
                cmd.append("--resume")
            
            # Execute command
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                status_msg = dbc.Alert([
                    html.I(className="fas fa-check-circle me-2"),
                    "Pipeline execution initiated. Check Job Monitor for status.",
                    html.Br(),
                    html.Small(result.stdout)
                ], color="success")
            else:
                status_msg = dbc.Alert([
                    html.I(className="fas fa-exclamation-triangle me-2"),
                    f"Pipeline execution failed: {result.stderr}"
                ], color="danger")
            
            return status_msg
            
        except Exception as e:
            error_msg = f"Error executing pipeline: {str(e)}"
            return dbc.Alert([
                html.I(className="fas fa-exclamation-triangle me-2"),
                error_msg
            ], color="danger")
    
    # Dynamic DAG visualization
    @app.callback(
        Output("dag-overview", "elements"),
        [Input("page-rendered-store", "data"),
         Input("prep-options", "value"),
         Input("structural-radio", "value"),
         Input("bids-prep-checklist", "value"),
         Input("bids-post-checklist", "value"),
         Input("staged-prep-checklist", "value"),
         Input("staged-post-checklist", "value"),
         Input("mriqc-options", "value")]
    )
    def update_dag_elements(_page, prep_option, structural_value, bids_prep, bids_post,
                            staged_prep, staged_post, mriqc_option):
        from .components.analysis_control import build_dag_elements
        return build_dag_elements(
            prep_option or 'none',
            structural_value or 'none',
            bids_prep or [],
            bids_post or [],
            staged_prep or [],
            staged_post or [],
            mriqc_option or 'none',
        )

    @app.callback(
        Output("dag-overview", "layout"),
        Input("dag-reset-btn", "n_clicks"),
        prevent_initial_call=True
    )
    def reset_dag_view(_):
        return {'name': 'dagre', 'rankDir': 'LR', 'nodeSep': 40, 'rankSep': 90, 'spacingFactor': 1.0}

    # Sidebar toggle callback
    @app.callback(
        [Output("sidebar", "className"),
         Output("main-content", "className")],
        [Input("sidebar-toggle", "n_clicks")],
        [State("sidebar", "className")]
    )
    def toggle_sidebar(n_clicks, sidebar_class):
        if n_clicks is None:
            return sidebar_class, "main-content"
        
        if "collapsed" in sidebar_class:
            new_class = sidebar_class.replace("collapsed", "").strip()
            main_class = "main-content"
        else:
            new_class = sidebar_class + " collapsed"
            main_class = "main-content expanded"
        
        return new_class, main_class
    
    # Auto-fill project config path from project name
    @app.callback(
        Output("config-file-path", "value"),
        Input("new-project-name", "value"),
        prevent_initial_call=True
    )
    def autofill_project_config_path(project_name):
        if not project_name:
            return ""
        return f"config/project_config/{project_name}_config.yaml"

    # Generate new config callback
    @app.callback(
        Output("new-config-result", "children"),
        [Input("generate-new-config-btn", "n_clicks")],
        [State("new-project-name", "value"),
         State("config-file-path", "value")]
    )
    def generate_new_config_callback(n_clicks, project_name, config_path):
        if n_clicks is None:
            return ""
        
        if not project_name:
            return dbc.Alert([
                html.I(className="fas fa-exclamation-triangle me-2"),
                "Please provide a project name"
            ], color="warning")
        
        try:
            from neuro_pipeline.pipeline.utils.generate_project_config import generate_project_config

            output_dir = os.path.dirname(config_path) if config_path else "config/project_config"
            generate_project_config(project_name, output_dir)

            config_file = os.path.join(output_dir, f"{project_name}_config.yaml")
            
            return dbc.Alert([
                html.I(className="fas fa-check-circle me-2"),
                html.Div([
                    f"Configuration template generated successfully: {config_file}",
                    html.Br(),
                    "Load the file to edit it in the editor below."
                ])
            ], color="success")
            
        except Exception as e:
            return dbc.Alert([
                html.I(className="fas fa-exclamation-triangle me-2"),
                f"Error generating configuration: {str(e)}"
            ], color="danger")
    
    # Load config callback
    @app.callback(
        Output("yaml-editor", "value"),
        [Input("load-config-btn", "n_clicks")],
        [State("config-file-path", "value")]
    )
    def load_config_callback(n_clicks, config_path):
        if n_clicks is None:
            return ""
        
        if not config_path:
            return "# Please provide a config file path"
        
        try:
            if os.path.exists(config_path):
                with open(config_path, 'r', encoding='utf-8') as f:
                    return f.read()
            else:
                return f"# Config file not found: {config_path}"
            
        except Exception as e:
            return f"# Error loading configuration: {str(e)}"
    
    # Save / Validate config callback (Tab 1)
    @app.callback(
        Output("yaml-validation-result", "children"),
        [Input("save-config-btn", "n_clicks"),
         Input("validate-config-btn", "n_clicks")],
        [State("config-file-path", "value"),
         State("yaml-editor", "value")],
        prevent_initial_call=True
    )
    def save_config_callback(_save_clicks, _validate_clicks, config_path, yaml_content):
        ctx = callback_context
        if not ctx.triggered:
            return ""
        trigger_id = ctx.triggered[0]["prop_id"].split(".")[0]

        if not yaml_content:
            return dbc.Alert("Editor is empty.", color="warning")

        try:
            import yaml as _yaml
            _yaml.safe_load(yaml_content)
        except Exception as e:
            return dbc.Alert([
                html.I(className="fas fa-exclamation-triangle me-2"),
                f"Invalid YAML: {e}"
            ], color="danger")

        if trigger_id == "validate-config-btn":
            return dbc.Alert([
                html.I(className="fas fa-check-circle me-2"),
                "Valid YAML"
            ], color="success")

        # Save
        if not config_path:
            return dbc.Alert("Please provide a file path before saving.", color="warning")

        try:
            dir_part = os.path.dirname(config_path)
            if dir_part:
                os.makedirs(dir_part, exist_ok=True)
            with open(config_path, 'w', encoding='utf-8') as f:
                f.write(yaml_content)
            return dbc.Alert([
                html.I(className="fas fa-check-circle me-2"),
                f"Saved to {config_path}"
            ], color="success")

        except Exception as e:
            return dbc.Alert([
                html.I(className="fas fa-exclamation-triangle me-2"),
                f"Error saving configuration: {str(e)}"
            ], color="danger")

    # ── Results Check: auto-fill path when project name is typed ─────────────
    @app.callback(
        Output("checks-file-path", "value"),
        Input("checks-project-name", "value"),
        prevent_initial_call=True
    )
    def autofill_checks_path(project_name):
        if not project_name:
            return ""
        return f"config/results_check/{project_name}_checks.yaml"

    # ── Results Check: load existing checks YAML ──────────────────────────────
    @app.callback(
        [Output("checks-yaml-editor", "value"),
         Output("checks-validation-result", "children", allow_duplicate=True)],
        [Input("load-checks-btn", "n_clicks"),
         Input("new-checks-btn", "n_clicks")],
        State("checks-file-path", "value"),
        prevent_initial_call=True
    )
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
                "# recon_bids:\n"
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

        # Load button
        if not checks_path:
            return "", dbc.Alert("Please provide a file path.", color="warning")

        if not os.path.exists(checks_path):
            return "", dbc.Alert(
                f"File not found: {checks_path}. "
                "Click 'New' to start from a template.",
                color="warning"
            )

        try:
            with open(checks_path, "r", encoding="utf-8") as f:
                content = f.read()
            return content, dbc.Alert(
                [html.I(className="fas fa-check-circle me-2"),
                 f"Loaded: {checks_path}"],
                color="success", className="mt-2"
            )
        except Exception as e:
            return "", dbc.Alert(f"Error loading file: {e}", color="danger")

    # ── Results Check: save + validate checks YAML ────────────────────────────
    @app.callback(
        Output("checks-validation-result", "children"),
        [Input("save-checks-btn", "n_clicks"),
         Input("validate-checks-btn", "n_clicks")],
        [State("checks-file-path", "value"),
         State("checks-yaml-editor", "value")],
        prevent_initial_call=True
    )
    def save_checks_callback(save_clicks, validate_clicks, checks_path, yaml_content):
        ctx = callback_context
        if not ctx.triggered:
            return ""

        trigger_id = ctx.triggered[0]["prop_id"].split(".")[0]

        if not yaml_content:
            return dbc.Alert("Editor is empty.", color="warning")

        # Validate YAML first
        try:
            import yaml as _yaml
            parsed = _yaml.safe_load(yaml_content)
        except _yaml.YAMLError as e:
            return dbc.Alert([
                html.I(className="fas fa-exclamation-triangle me-2"),
                f"Invalid YAML: {e}"
            ], color="danger")

        if trigger_id == "validate-checks-btn":
            # Just validate — check keys look like task names
            if not isinstance(parsed, dict):
                return dbc.Alert("Top-level must be a YAML mapping (task_name: ...).", color="warning")
            return dbc.Alert([
                html.I(className="fas fa-check-circle me-2"),
                f"Valid YAML · {len(parsed)} task(s) defined: {', '.join(parsed.keys())}"
            ], color="success")

        # Save
        if not checks_path:
            return dbc.Alert("Please provide a file path before saving.", color="warning")

        try:
            os.makedirs(os.path.dirname(checks_path), exist_ok=True)
            with open(checks_path, "w", encoding="utf-8") as f:
                f.write(yaml_content)
            return dbc.Alert([
                html.I(className="fas fa-check-circle me-2"),
                f"Saved to {checks_path}"
            ], color="success")
        except Exception as e:
            return dbc.Alert(f"Error saving: {e}", color="danger")

    # ── Global config.yaml: load ──────────────────────────────────────────────
    @app.callback(
        [Output("global-config-editor", "value"),
         Output("global-config-result", "children", allow_duplicate=True)],
        Input("load-global-config-btn", "n_clicks"),
        prevent_initial_call=True
    )
    def load_global_config_callback(n_clicks):
        if not n_clicks:
            return "", ""

        # Resolve path relative to this file (callbacks.py lives in dashboard/)
        from pathlib import Path
        config_path = (
            Path(__file__).parent.parent  # neuro_pipeline/
            / "pipeline" / "config" / "config.yaml"
        )

        if not config_path.exists():
            return "", dbc.Alert(
                f"config.yaml not found at: {config_path}",
                color="danger"
            )

        try:
            with open(config_path, "r", encoding="utf-8") as f:
                content = f.read()
            return content, dbc.Alert(
                [html.I(className="fas fa-check-circle me-2"),
                 f"Loaded: {config_path}"],
                color="success", className="mt-2"
            )
        except Exception as e:
            return "", dbc.Alert(f"Error loading config.yaml: {e}", color="danger")

    # ── Global config.yaml: validate + save ───────────────────────────────────
    @app.callback(
        Output("global-config-result", "children"),
        [Input("save-global-config-btn", "n_clicks"),
         Input("validate-global-config-btn", "n_clicks")],
        State("global-config-editor", "value"),
        prevent_initial_call=True
    )
    def save_global_config_callback(save_clicks, validate_clicks, yaml_content):
        ctx = callback_context
        if not ctx.triggered:
            return ""

        trigger_id = ctx.triggered[0]["prop_id"].split(".")[0]

        if not yaml_content:
            return dbc.Alert("Editor is empty.", color="warning")

        # Validate
        try:
            import yaml as _yaml
            parsed = _yaml.safe_load(yaml_content)
        except _yaml.YAMLError as e:
            return dbc.Alert([
                html.I(className="fas fa-exclamation-triangle me-2"),
                f"Invalid YAML: {e}"
            ], color="danger")

        # Check expected top-level keys
        expected_keys = {"prep", "structural", "qc", "array_config"}
        present = set(parsed.keys()) if isinstance(parsed, dict) else set()
        missing = expected_keys - present

        if trigger_id == "validate-global-config-btn":
            if missing:
                return dbc.Alert([
                    html.I(className="fas fa-exclamation-triangle me-2"),
                    f"Valid YAML but missing expected top-level keys: {', '.join(sorted(missing))}"
                ], color="warning")
            task_count = sum(
                len(v) for v in parsed.values()
                if isinstance(v, list)
            )
            section_count = sum(1 for v in parsed.values() if isinstance(v, list))
            return dbc.Alert([
                html.I(className="fas fa-check-circle me-2"),
                f"Valid YAML · {task_count} task(s) across {section_count} section(s)"
            ], color="success")

        # Save
        from pathlib import Path
        config_path = (
            Path(__file__).parent.parent
            / "pipeline" / "config" / "config.yaml"
        )

        try:
            with open(config_path, "w", encoding="utf-8") as f:
                f.write(yaml_content)
            return dbc.Alert([
                html.I(className="fas fa-check-circle me-2"),
                f"Saved to {config_path}",
                html.Br(),
                html.Small("Restart the pipeline process for changes to take effect.",
                           className="text-muted")
            ], color="success")
        except Exception as e:
            return dbc.Alert(f"Error saving config.yaml: {e}", color="danger")

    # ── HPC Config: load ──────────────────────────────────────────────────────
    @app.callback(
        [Output("hpc-config-editor", "value"),
         Output("hpc-config-result", "children", allow_duplicate=True)],
        Input("load-hpc-config-btn", "n_clicks"),
        prevent_initial_call=True
    )
    def load_hpc_config_callback(n_clicks):
        if not n_clicks:
            return "", ""

        from pathlib import Path
        config_path = (
            Path(__file__).parent.parent
            / "pipeline" / "config" / "hpc_config.yaml"
        )

        if not config_path.exists():
            return "", dbc.Alert(
                f"hpc_config.yaml not found at: {config_path}", color="danger"
            )

        try:
            with open(config_path, "r", encoding="utf-8") as f:
                content = f.read()
            return content, dbc.Alert(
                [html.I(className="fas fa-check-circle me-2"), f"Loaded: {config_path}"],
                color="success", className="mt-2"
            )
        except Exception as e:
            return "", dbc.Alert(f"Error loading hpc_config.yaml: {e}", color="danger")

    # ── HPC Config: validate + save ───────────────────────────────────────────
    @app.callback(
        Output("hpc-config-result", "children"),
        [Input("save-hpc-config-btn", "n_clicks"),
         Input("validate-hpc-config-btn", "n_clicks")],
        State("hpc-config-editor", "value"),
        prevent_initial_call=True
    )
    def save_hpc_config_callback(_save_clicks, _validate_clicks, yaml_content):
        ctx = callback_context
        if not ctx.triggered:
            return ""
        trigger_id = ctx.triggered[0]["prop_id"].split(".")[0]

        if not yaml_content:
            return dbc.Alert("Editor is empty.", color="warning")

        try:
            import yaml as _yaml
            parsed = _yaml.safe_load(yaml_content)
        except Exception as e:
            return dbc.Alert([
                html.I(className="fas fa-exclamation-triangle me-2"),
                f"Invalid YAML: {e}"
            ], color="danger")

        expected_keys = {"resource_profiles", "defaults"}
        present = set(parsed.keys()) if isinstance(parsed, dict) else set()
        missing = expected_keys - present

        if trigger_id == "validate-hpc-config-btn":
            if missing:
                return dbc.Alert([
                    html.I(className="fas fa-exclamation-triangle me-2"),
                    f"Valid YAML but missing expected keys: {', '.join(sorted(missing))}"
                ], color="warning")
            profile_count = len(parsed.get("resource_profiles", {}))
            return dbc.Alert([
                html.I(className="fas fa-check-circle me-2"),
                f"Valid YAML · {profile_count} resource profile(s)"
            ], color="success")

        # Save
        from pathlib import Path
        config_path = (
            Path(__file__).parent.parent
            / "pipeline" / "config" / "hpc_config.yaml"
        )
        try:
            with open(config_path, "w", encoding="utf-8") as f:
                f.write(yaml_content)
            return dbc.Alert([
                html.I(className="fas fa-check-circle me-2"),
                f"Saved to {config_path}",
                html.Br(),
                html.Small("Restart the pipeline process for changes to take effect.",
                           className="text-muted")
            ], color="success")
        except Exception as e:
            return dbc.Alert(f"Error saving hpc_config.yaml: {e}", color="danger")