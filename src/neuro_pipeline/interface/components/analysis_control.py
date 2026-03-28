from dash import dcc, html
import dash_bootstrap_components as dbc
import os
from ...pipeline.utils.config_utils import get_task_options

def create_analysis_control_layout():
    """Create the analysis control layout with subject selection and pipeline options"""
    
    return dbc.Container([
        dbc.Row([
            dbc.Col([
                html.H3("Analysis Control", className="mb-4"),
                html.Hr()
            ])
        ]),
        
        # Subject Selection Section
        dbc.Row([
            dbc.Col([
                html.H4("Subject Selection", className="mb-3"),
                dbc.Card([
                    dbc.CardBody([
                        dbc.Row([
                            dbc.Col([
                                dbc.Label("Subject Prefix:", html_for="subject-prefix"),
                                dbc.Input(
                                    id="subject-prefix",
                                    type="text",
                                    placeholder="e.g., sub-",
                                    value="sub-",
                                    className="mb-3"
                                )
                            ], width=2),
                            dbc.Col([
                                dbc.Label("Current Directory:", html_for="current-dir"),
                                dbc.Input(
                                    id="current-dir",
                                    type="text",
                                    value=os.getcwd(),
                                    className="mb-3"
                                )
                            ], width=7),
                            dbc.Col([
                                dbc.Button("Detect Subjects", id="detect-subjects-btn", 
                                         color="primary", className="mt-4 me-2"),
                                dbc.Button("Clear", id="clear-subjects-btn", 
                                         color="secondary", className="mt-4")
                            ], width=3)
                        ]),
                        dbc.Row([
                            dbc.Col([
                                dbc.Label("Or Enter Subject IDs (comma-separated):", html_for="manual-subjects"),
                                dbc.Input(
                                    id="manual-subjects",
                                    type="text",
                                    placeholder="e.g., 001,002,003 or sub-001,sub-002",
                                    className="mb-3"
                                )
                            ], width=12)
                        ]),
                        html.Div(id="subjects-detection-result", className="mb-3"),
                        html.Div(id="subjects-list-container")
                    ])
                ])
            ])
        ], className="mb-4"),
        
        # Pipeline Configuration Section
        dbc.Row([
            dbc.Col([
                html.H4("Pipeline Configuration", className="mb-3"),
                dbc.Card([
                    dbc.CardBody([
                        # Directory Settings
                        dbc.Row([
                            dbc.Col([
                                dbc.Label("Input Directory:", html_for="input-dir"),
                                dbc.Input(
                                    id="input-dir",
                                    type="text",
                                    placeholder="/path/to/input",
                                    className="mb-3"
                                )
                            ], width=4),
                            dbc.Col([
                                dbc.Label("Output Directory:", html_for="output-dir"),
                                dbc.Input(
                                    id="output-dir",
                                    type="text",
                                    placeholder="/path/to/output",
                                    className="mb-3"
                                )
                            ], width=4),
                            dbc.Col([
                                dbc.Label("Work Directory:", html_for="work-dir"),
                                dbc.Input(
                                    id="work-dir",
                                    type="text",
                                    placeholder="/path/to/work",
                                    className="mb-3"
                                )
                            ], width=4)
                        ]),
                        
                        # Project Settings
                        dbc.Row([
                            dbc.Col([
                                dbc.Label("Project Name:", html_for="project-name"),
                                dbc.Input(
                                    id="project-name",
                                    type="text",
                                    placeholder="e.g., branch, study1",
                                    className="mb-3"
                                )
                            ], width=6),
                            dbc.Col([
                                dbc.Label("Session ID:", html_for="session-id"),
                                dbc.Input(
                                    id="session-id",
                                    type="text",
                                    value="01",
                                    className="mb-3"
                                )
                            ], width=6)
                        ]),
                        
                        html.Hr(),
                        
                        # Pipeline Modules
                        create_pipeline_modules_section()
                        
                    ])
                ])
            ])
        ], className="mb-4"),
        
        # Execution Control
        dbc.Row([
            dbc.Col([
                html.H4("Execution Control", className="mb-3"),
                dbc.Card([
                    dbc.CardBody([
                        dbc.Row([
                            dbc.Col([
                                dbc.Checklist(
                                    id="dry-run-checkbox",
                                    options=[{"label": "Dry Run (Show commands without execution)", "value": "dry_run"}],
                                    value=["dry_run"],
                                    className="mb-3"
                                )
                            ], width=4),
                            dbc.Col([
                                dbc.Button("Generate Command", id="generate-commands-btn", 
                                         color="info", className="mb-3 me-2"),
                                dbc.Button("Execute Pipeline", id="execute-pipeline-btn", 
                                         color="success", className="mb-3")
                            ], width=8)
                        ]),
                        dbc.Row([
                            dbc.Col([
                                html.Div(id="execution-status", className="mt-3")
                            ], width=12)
                        ])
                    ])
                ])
            ])
        ]),
        
        # Command Preview Section
        dbc.Row([
            dbc.Col([
                html.H4("Command Preview", className="mb-3 mt-4"),
                dbc.Card([
                    dbc.CardBody([
                        html.Pre(
                            id="command-preview",
                            style={
                                "backgroundColor": "#f5f5f5",
                                "padding": "15px",
                                "borderRadius": "5px",
                                "fontSize": "14px",
                                "fontFamily": "monospace",
                                "whiteSpace": "pre-wrap",
                                "wordWrap": "break-word"
                            }
                        )
                    ])
                ])
            ])
        ], className="mb-4")
    ], fluid=True)

def create_pipeline_modules_section():
    """Create the pipeline modules configuration section"""
    
    return dbc.Row([
        dbc.Col([
            # Preprocessing
            dbc.Card([
                dbc.CardHeader("Preprocessing"),
                dbc.CardBody([
                    dbc.RadioItems(
                        id="prep-options",
                        options=[
                            {"label": "None", "value": "none"},
                            {"label": "Unzip", "value": "unzip"},
                            {"label": "Recon (BIDS conversion)", "value": "recon"},
                            {"label": "Unzip + Recon", "value": "unzip_recon"}
                        ],
                        value="none",
                        inline=True
                    )
                ])
            ], className="mb-3"),
            
            # Structural
            dbc.Card([
                dbc.CardHeader("Structural Processing"),
                dbc.CardBody([
                    dbc.RadioItems(
                        id="structural-options",
                        options=[
                            {"label": "None", "value": "none"},
                            {"label": "Volume", "value": "volume"}
                        ],
                        value="none",
                        inline=True
                    )
                ])
            ], className="mb-3"),
            
            # Resting State fMRI
            dbc.Card([
                dbc.CardHeader("Resting State fMRI"),
                dbc.CardBody([
                    dbc.Row([
                        dbc.Col([
                            dbc.Label("Preprocessing:"),
                            dbc.RadioItems(
                                id="rest-prep",
                                options=[
                                    {"label": "None", "value": "none"},
                                    {"label": "fMRIPrep", "value": "fmriprep"}
                                ],
                                value="none",
                                inline=True
                            )
                        ], width=6),
                        dbc.Col([
                            dbc.Label("Postprocessing:"),
                            dbc.RadioItems(
                                id="rest-post",
                                options=[
                                    {"label": "None", "value": "none"},
                                    {"label": "XCP-D", "value": "xcpd"}
                                ],
                                value="none",
                                inline=True
                            )
                        ], width=6)
                    ])
                ])
            ], className="mb-3"),
            
            # DWI
            dbc.Card([
                dbc.CardHeader("DWI (Diffusion Weighted Imaging)"),
                dbc.CardBody([
                    dbc.Row([
                        dbc.Col([
                            dbc.Label("Preprocessing:"),
                            dbc.RadioItems(
                                id="dwi-prep",
                                options=[
                                    {"label": "None", "value": "none"},
                                    {"label": "QSIPrep", "value": "qsiprep"}
                                ],
                                value="none",
                                inline=True
                            )
                        ], width=6),
                        dbc.Col([
                            dbc.Label("Postprocessing:"),
                            dbc.RadioItems(
                                id="dwi-post",
                                options=[
                                    {"label": "None", "value": "none"},
                                    {"label": "QSIRecon", "value": "qsirecon"}
                                ],
                                value="none",
                                inline=True
                            )
                        ], width=6)
                    ])
                ])
            ], className="mb-3"),
            
            # Task fMRI
            dbc.Card([
                dbc.CardHeader("Task fMRI"),
                dbc.CardBody([
                    dbc.Row([
                        dbc.Col([
                            dbc.Label("Preprocessing:", html_for="task-prep"),
                            dbc.Checklist(
                                id="task-prep",
                                options=get_task_options('_preprocess'),
                                value=[],
                                inline=True
                            )
                        ], width=6),
                        dbc.Col([
                            dbc.Label("Postprocessing:", html_for="task-post"),
                            dbc.Checklist(
                                id="task-post",
                                options=get_task_options('_postprocess'),
                                value=[],
                                inline=True
                            )
                        ], width=6)
                    ])
                ])
            ], className="mb-3"),
            
            # Quality Control
            dbc.Card([
                dbc.CardHeader("Quality Control (MRIQC)"),
                dbc.CardBody([
                    dbc.RadioItems(
                        id="mriqc-options",
                        options=[
                            {"label": "None", "value": "none"},
                            {"label": "Individual", "value": "individual"},
                            {"label": "Group", "value": "group"},
                            {"label": "All", "value": "all"}
                        ],
                        value="none",
                        inline=True
                    )
                ])
            ])
        ])
    ])