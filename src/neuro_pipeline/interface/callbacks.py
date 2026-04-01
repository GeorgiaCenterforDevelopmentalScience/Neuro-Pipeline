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
        State("structural-options", "value"),
        State("rest-prep", "value"),
        State("rest-post", "value"),
        State("dwi-prep", "value"),
        State("dwi-post", "value"),
        State("task-prep", "value"),
        State("task-post", "value"),
        State("mriqc-options", "value"),
        State("dry-run-checkbox", "value"),
        State("resume-checkbox", "value")]
    )
    def generate_command_callback(n_clicks, subjects, input_dir, output_dir, work_dir,
                                project_name, session, prep_option, structural_option,
                                rest_prep, rest_post, dwi_prep, dwi_post,
                                task_prep, task_post,
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
            
            # Add session
            cmd_parts.append(f'  --session {session} \\')
            
            # Add project
            cmd_parts.append(f'  --project {project_name} \\')
            
            # Add prep options
            if prep_option and prep_option != "none":
                cmd_parts.append(f'  --prep {prep_option} \\')
            
            # Add structural options
            if structural_option and structural_option != "none":
                cmd_parts.append(f'  --structural {structural_option} \\')
            
            # Add MRIQC options
            if mriqc_option and mriqc_option != "none":
                cmd_parts.append(f'  --mriqc {mriqc_option} \\')
            
            # Add rest options
            if rest_prep and rest_prep != "none":
                cmd_parts.append(f'  --rest-prep {rest_prep} \\')
            
            if rest_post and rest_post != "none":
                cmd_parts.append(f'  --rest-post {rest_post} \\')
            
            # Add DWI options
            if dwi_prep and dwi_prep != "none":
                cmd_parts.append(f'  --dwi-prep {dwi_prep} \\')
            
            if dwi_post and dwi_post != "none":
                cmd_parts.append(f'  --dwi-post {dwi_post} \\')
            
            # Add task options - now support comma-separated format
            if task_prep:
                # Convert list to comma-separated string
                task_prep_str = ",".join(task_prep)
                cmd_parts.append(f'  --task-prep {task_prep_str} \\')
            
            if task_post:
                # Convert list to comma-separated string
                task_post_str = ",".join(task_post)
                cmd_parts.append(f'  --task-post {task_post_str} \\')
            
            # Add dry run flag if enabled
            if dry_run and "dry_run" in dry_run:
                cmd_parts.append(f'  --dry-run \\')
            
            # Add resume flag if enabled
            if resume and "resume" in resume:
                cmd_parts.append(f'  --resume')
            else:
                # Remove trailing backslash from last option
                if cmd_parts[-1].endswith(' \\'):
                    cmd_parts[-1] = cmd_parts[-1][:-2]
            
            # Join command parts
            command_str = "\n".join(cmd_parts)
            
            # Store command data for execution
            command_data = {
                "subjects": subjects,
                "input_dir": input_dir,
                "output_dir": output_dir,
                "work_dir": work_dir,
                "project_name": project_name,
                "session": session,
                "prep_option": prep_option,
                "structural_option": structural_option,
                "rest_prep": rest_prep,
                "rest_post": rest_post,
                "dwi_prep": dwi_prep,
                "dwi_post": dwi_post,
                "task_prep": task_prep,
                "task_post": task_post,
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
            
            # Add structural
            if command_data.get("structural_option") and command_data["structural_option"] != "none":
                cmd.extend(["--structural", command_data["structural_option"]])
            
            # Add MRIQC
            if command_data.get("mriqc_option") and command_data["mriqc_option"] != "none":
                cmd.extend(["--mriqc", command_data["mriqc_option"]])
            
            # Add rest
            if command_data.get("rest_prep") and command_data["rest_prep"] != "none":
                cmd.extend(["--rest-prep", command_data["rest_prep"]])
            
            if command_data.get("rest_post") and command_data["rest_post"] != "none":
                cmd.extend(["--rest-post", command_data["rest_post"]])
            
            # Add DWI
            if command_data.get("dwi_prep") and command_data["dwi_prep"] != "none":
                cmd.extend(["--dwi-prep", command_data["dwi_prep"]])
            
            if command_data.get("dwi_post") and command_data["dwi_post"] != "none":
                cmd.extend(["--dwi-post", command_data["dwi_post"]])
            
            # Add task - now pass as comma-separated string
            if command_data.get("task_prep"):
                task_prep_str = ",".join(command_data["task_prep"])
                cmd.extend(["--task-prep", task_prep_str])
            
            if command_data.get("task_post"):
                task_post_str = ",".join(command_data["task_post"])
                cmd.extend(["--task-post", task_post_str])
            
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
    
    # Generate new config callback
    @app.callback(
        Output("new-config-result", "children"),
        [Input("generate-new-config-btn", "n_clicks")],
        [State("new-project-name", "value"),
         State("new-config-output-dir", "value")]
    )
    def generate_new_config_callback(n_clicks, project_name, output_dir):
        if n_clicks is None:
            return ""
        
        if not project_name:
            return dbc.Alert([
                html.I(className="fas fa-exclamation-triangle me-2"),
                "Please provide a project name"
            ], color="warning")
        
        try:
            # Import and call function directly
            from neuro_pipeline.pipeline.utils.generate_project_config import generate_project_config
            
            # Call function directly instead of running script
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
    
    # Save config callback
    @app.callback(
        Output("yaml-validation-result", "children"),
        [Input("save-config-btn", "n_clicks")],
        [State("config-file-path", "value"),
         State("yaml-editor", "value")]
    )
    def save_config_callback(n_clicks, config_path, yaml_content):
        if n_clicks is None:
            return ""
        
        if not config_path or not yaml_content:
            return dbc.Alert([
                html.I(className="fas fa-exclamation-triangle me-2"),
                "Please provide both file path and YAML content"
            ], color="warning")
        
        try:
            import yaml
            yaml.safe_load(yaml_content)
            
            os.makedirs(os.path.dirname(config_path), exist_ok=True)
            with open(config_path, 'w', encoding='utf-8') as f:
                f.write(yaml_content)
            
            return dbc.Alert([
                html.I(className="fas fa-check-circle me-2"),
                f"Configuration saved successfully to {config_path}"
            ], color="success")
            
        except yaml.YAMLError as e:
            return dbc.Alert([
                html.I(className="fas fa-exclamation-triangle me-2"),
                f"Invalid YAML format: {str(e)}"
            ], color="danger")
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
        expected_keys = {"defaults", "resource_profiles", "tasks", "array_config"}
        present = set(parsed.keys()) if isinstance(parsed, dict) else set()
        missing = expected_keys - present

        if trigger_id == "validate-global-config-btn":
            if missing:
                return dbc.Alert([
                    html.I(className="fas fa-exclamation-triangle me-2"),
                    f"Valid YAML but missing expected top-level keys: {', '.join(sorted(missing))}"
                ], color="warning")
            task_count = sum(
                len(v) for v in parsed.get("tasks", {}).values()
                if isinstance(v, list)
            )
            return dbc.Alert([
                html.I(className="fas fa-check-circle me-2"),
                f"Valid YAML · {task_count} task(s) across "
                f"{len(parsed.get('tasks', {}))} section(s) · "
                f"{len(parsed.get('resource_profiles', {}))} resource profile(s)"
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