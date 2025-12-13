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
        State("task-prep", "value"),
        State("task-post", "value"),
        State("mriqc-options", "value"),
        State("dry-run-checkbox", "value")]
    )
    def generate_command_callback(n_clicks, subjects, input_dir, output_dir, work_dir,
                                project_name, session, prep_option, structural_option,
                                rest_prep, rest_post, task_prep, task_post,
                                mriqc_option, dry_run):
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
                cmd_parts.append(f'  --dry-run')
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
                "task_prep": task_prep,
                "task_post": task_post,
                "mriqc_option": mriqc_option,
                "dry_run": dry_run
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
        State("dry-run-checkbox", "value")],
        prevent_initial_call=True
    )
    def execute_pipeline_callback(n_clicks, command_data, dry_run):
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