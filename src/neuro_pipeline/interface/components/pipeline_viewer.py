from dash import dcc, html
import dash_bootstrap_components as dbc
import json

def create_pipeline_viewer_layout():
    """Create the pipeline viewer layout to show pipeline commands"""
    
    return dbc.Container([
        dbc.Row([
            dbc.Col([
                html.H3("Pipeline Viewer", className="mb-4"),
                html.Hr()
            ])
        ]),
        
        # Pipeline Overview
        dbc.Row([
            dbc.Col([
                html.H4("Pipeline Overview", className="mb-3"),
                dbc.Card([
                    dbc.CardBody([
                        dbc.Row([
                            dbc.Col([
                                dbc.Button("Refresh Pipeline View", id="refresh-pipeline-btn", 
                                         color="primary", className="mb-3"),
                                dbc.Button("Clear Pipeline", id="clear-pipeline-btn", 
                                         color="secondary", className="mb-3 ms-2")
                            ], width=6),
                            dbc.Col([
                                dbc.Label("Pipeline Status:", html_for="pipeline-status"),
                                html.Div(id="pipeline-status", className="badge bg-info")
                            ], width=6)
                        ]),
                        html.Div(id="pipeline-summary", className="mt-3")
                    ])
                ])
            ])
        ], className="mb-4"),
        
        # Pipeline Commands Display
        dbc.Row([
            dbc.Col([
                html.H4("Pipeline Commands", className="mb-3"),
                dbc.Card([
                    dbc.CardBody([
                        dbc.Row([
                            dbc.Col([
                                dbc.Label("Display Mode:", html_for="display-mode"),
                                dcc.Dropdown(
                                    id="display-mode",
                                    options=[
                                        {"label": "Tree View", "value": "tree"},
                                        {"label": "List View", "value": "list"},
                                        {"label": "JSON View", "value": "json"}
                                    ],
                                    value="tree",
                                    className="mb-3"
                                )
                            ], width=4),
                            dbc.Col([
                                dbc.Label("Filter by Module:", html_for="module-filter"),
                                dcc.Dropdown(
                                    id="module-filter",
                                    options=[
                                        {"label": "All Modules", "value": "all"},
                                        {"label": "Preprocessing", "value": "prep"},
                                        {"label": "Structural", "value": "structural"},
                                        {"label": "Rest fMRI", "value": "rest"},
                                        {"label": "DWI", "value": "dwi"},
                                        {"label": "Task fMRI", "value": "task"},
                                        {"label": "Quality Control", "value": "qc"}
                                    ],
                                    value="all",
                                    className="mb-3"
                                )
                            ], width=4),
                            dbc.Col([
                                dbc.Label("Show Details:", html_for="show-details"),
                                dcc.Checklist(
                                    id="show-details",
                                    options=[{"label": "Show command details", "value": "details"}],
                                    value=["details"],
                                    className="mb-3"
                                )
                            ], width=4)
                        ]),
                        html.Div(id="pipeline-commands-display", className="mt-3")
                    ])
                ])
            ])
        ], className="mb-4"),
        
        # Command Execution Preview
        dbc.Row([
            dbc.Col([
                html.H4("Command Execution Preview", className="mb-3"),
                dbc.Card([
                    dbc.CardBody([
                        dbc.Row([
                            dbc.Col([
                                dbc.Button("Generate Dry Run", id="dry-run-btn", 
                                         color="warning", className="mb-3 me-2"),
                                dbc.Button("Show Wrapper Scripts", id="show-wrappers-btn", 
                                         color="info", className="mb-3")
                            ], width=6),
                            dbc.Col([
                                dbc.Label("Execution Mode:", html_for="execution-mode"),
                                dcc.Dropdown(
                                    id="execution-mode",
                                    options=[
                                        {"label": "Dry Run", "value": "dry_run"},
                                        {"label": "Real Execution", "value": "real"}
                                    ],
                                    value="dry_run",
                                    className="mb-3"
                                )
                            ], width=6)
                        ]),
                        html.Div(id="execution-preview", className="mt-3")
                    ])
                ])
            ])
        ], className="mb-4"),
        
        # Console Output
        dbc.Row([
            dbc.Col([
                html.H4("Console Output", className="mb-3"),
                dbc.Card([
                    dbc.CardBody([
                        dbc.Row([
                            dbc.Col([
                                dbc.Button("Clear Console", id="clear-console-btn", 
                                         color="secondary", className="mb-3"),
                                dbc.Button("Export Log", id="export-log-btn", 
                                         color="info", className="mb-3 ms-2")
                            ], width=6),
                            dbc.Col([
                                dbc.Label("Log Level:", html_for="log-level"),
                                dcc.Dropdown(
                                    id="log-level",
                                    options=[
                                        {"label": "All", "value": "all"},
                                        {"label": "Info", "value": "info"},
                                        {"label": "Warning", "value": "warning"},
                                        {"label": "Error", "value": "error"}
                                    ],
                                    value="all",
                                    className="mb-3"
                                )
                            ], width=6)
                        ]),
                        html.Div(id="console-output", className="mt-3")
                    ])
                ])
            ])
        ])
    ], fluid=True)

def create_tree_view(commands, show_details=True):
    """Create a tree view of pipeline commands"""
    if not commands:
        return html.Div("No pipeline commands available", className="text-muted")
    
    tree_items = []
    
    for module, module_commands in commands.items():
        module_item = html.Details([
            html.Summary(f"{module.upper()} ({len(module_commands)} commands)", 
                        className="fw-bold"),
            html.Ul([
                html.Li([
                    html.Strong(f"Task: {cmd.get('task_name', 'Unknown')}"),
                    html.Br(),
                    html.Span(f"Script: {cmd.get('script', 'Unknown')}"),
                    html.Br(),
                    html.Span(f"Profile: {cmd.get('profile', 'Unknown')}"),
                    html.Br(),
                    html.Span(f"Array: {'Yes' if cmd.get('array', False) else 'No'}"),
                    html.Br(),
                    html.Span(f"Input: {cmd.get('input_from', 'None')}"),
                    html.Br(),
                    html.Span(f"Output: {cmd.get('output_pattern', 'None')}")
                ]) for cmd in module_commands
            ])
        ])
        tree_items.append(module_item)
    
    return html.Div(tree_items)

def create_list_view(commands, show_details=True):
    """Create a list view of pipeline commands"""
    if not commands:
        return html.Div("No pipeline commands available", className="text-muted")
    
    list_items = []
    
    for module, module_commands in commands.items():
        list_items.append(html.H5(f"{module.upper()} Module", className="mt-3"))
        
        for i, cmd in enumerate(module_commands):
            card = dbc.Card([
                dbc.CardBody([
                    dbc.Row([
                        dbc.Col([
                            html.Strong(f"Task {i+1}: {cmd.get('task_name', 'Unknown')}"),
                            html.Br(),
                            html.Span(f"Script: {cmd.get('script', 'Unknown')}")
                        ], width=6),
                        dbc.Col([
                            html.Span(f"Profile: {cmd.get('profile', 'Unknown')}"),
                            html.Br(),
                            html.Span(f"Array: {'Yes' if cmd.get('array', False) else 'No'}")
                        ], width=6)
                    ]),
                    html.Hr(),
                    html.Small([
                        html.Strong("Input: "), cmd.get('input_from', 'None'),
                        html.Br(),
                        html.Strong("Output: "), cmd.get('output_pattern', 'None')
                    ], className="text-muted")
                ])
            ], className="mb-2")
            list_items.append(card)
    
    return html.Div(list_items)

def create_json_view(commands):
    """Create a JSON view of pipeline commands"""
    if not commands:
        return html.Div("No pipeline commands available", className="text-muted")
    
    return html.Pre(
        json.dumps(commands, indent=2, default=str),
        className="bg-light p-3 rounded"
    )