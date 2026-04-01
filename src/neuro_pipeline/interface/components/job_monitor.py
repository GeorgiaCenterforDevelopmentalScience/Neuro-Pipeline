from dash import dcc, html
import dash_bootstrap_components as dbc
import os

def create_job_monitor_layout():
    """Create the job monitor layout for querying and visualizing pipeline jobs"""

    return dbc.Container([
        dbc.Row([
            dbc.Col([
                html.H3("Job Monitor", className="mb-4"),
                html.Hr()
            ])
        ]),

        # Database Configuration
        dbc.Row([
            dbc.Col([
                html.H4("Database Configuration", className="mb-3"),
                dbc.Card([
                    dbc.CardBody([
                        dbc.Row([
                            dbc.Col([
                                dbc.Label("Database Path:", html_for="db-path"),
                                dbc.Input(
                                    id="db-path",
                                    type="text",
                                    placeholder="/path/to/database/pipeline_jobs.db",
                                    value=os.path.join(os.getcwd(), "database", "pipeline_jobs.db"),
                                    className="mb-3"
                                )
                            ], width=8),
                            dbc.Col([
                                dbc.Label("Work Directory:", html_for="work-dir-input"),
                                dbc.Input(
                                    id="work-dir-input",
                                    type="text",
                                    placeholder="/data/work/my_study",
                                    value=os.getcwd(),
                                    className="mb-3"
                                )
                            ], width=4)
                        ]),
                        dbc.Row([
                            dbc.Col([
                                dbc.Button(
                                    "Sync Database from JSONL Logs",
                                    id="merge-logs-btn",
                                    color="outline-secondary",
                                    className="me-2"
                                ),
                                html.Small(
                                    "Re-processes raw JSONL event logs and fills any missing records in the database. "
                                    "Use this after a cluster crash or if the database looks incomplete.",
                                    className="text-muted ms-2"
                                ),
                                html.Div(id="merge-logs-result", className="mt-3")
                            ], width=12)
                        ])
                    ])
                ])
            ])
        ], className="mb-4"),

        # Output File Check
        dbc.Row([
            dbc.Col([
                html.H4("Output File Check", className="mb-3"),
                dbc.Card([
                    dbc.CardBody([
                        dbc.Row([
                            dbc.Col([
                                dbc.Label("Project Name:", html_for="check-project-name"),
                                dbc.Input(
                                    id="check-project-name",
                                    type="text",
                                    placeholder="e.g., branch",
                                    className="mb-3"
                                )
                            ], width=3),
                            dbc.Col([
                                dbc.Label("Subjects (comma-separated):", html_for="check-subjects"),
                                dbc.Input(
                                    id="check-subjects",
                                    type="text",
                                    placeholder="001,002,003",
                                    className="mb-3"
                                )
                            ], width=4),
                            dbc.Col([
                                dbc.Label("Task Filter (optional):", html_for="check-task-filter"),
                                dbc.Input(
                                    id="check-task-filter",
                                    type="text",
                                    placeholder="e.g., rest_fmriprep_preprocess",
                                    className="mb-3"
                                )
                            ], width=3),
                            dbc.Col([
                                dbc.Label("Session:", html_for="check-session"),
                                dbc.Input(
                                    id="check-session",
                                    type="text",
                                    placeholder="01",
                                    value="01",
                                    className="mb-3"
                                )
                            ], width=1),
                            dbc.Col([
                                dbc.Label("Prefix:", html_for="check-prefix"),
                                dbc.Input(
                                    id="check-prefix",
                                    type="text",
                                    placeholder="sub-",
                                    value="sub-",
                                    className="mb-3"
                                )
                            ], width=1),
                        ]),
                        dbc.Row([
                            dbc.Col([
                                dbc.Button(
                                    "Run Output Check",
                                    id="run-output-check-btn",
                                    color="primary",
                                    className="me-2"
                                ),
                                dbc.Button(
                                    "Export Check CSV",
                                    id="export-check-csv-btn",
                                    color="outline-secondary"
                                ),
                                html.Div(id="output-check-result", className="mt-3")
                            ], width=12)
                        ])
                    ])
                ])
            ])
        ], className="mb-4"),
        
        # Wrapper Script Inspector
        dbc.Row([
            dbc.Col([
                html.H4("Wrapper Script Inspector", className="mb-3"),
                dbc.Card([
                    dbc.CardBody([
                        dbc.Row([
                            dbc.Col([
                                dbc.Label("Task Name:", html_for="wrapper-task-filter"),
                                dbc.Input(
                                    id="wrapper-task-filter",
                                    type="text",
                                    placeholder="e.g., rest_fmriprep_preprocess (leave empty for latest)",
                                    className="mb-3"
                                )
                            ], width=6),
                            dbc.Col([
                                dbc.Label("Job ID:", html_for="wrapper-job-id"),
                                dbc.Input(
                                    id="wrapper-job-id",
                                    type="text",
                                    placeholder="e.g., 12345 (leave empty for latest)",
                                    className="mb-3"
                                )
                            ], width=4),
                            dbc.Col([
                                dbc.Button(
                                    "Load Wrapper",
                                    id="load-wrapper-btn",
                                    color="primary",
                                    className="mt-4"
                                )
                            ], width=2)
                        ]),
                        html.Div(id="wrapper-inspect-result", className="mt-2")
                    ])
                ])
            ])
        ], className="mb-4"),

        # Query Configuration
        dbc.Row([
            dbc.Col([
                html.H4("Query Configuration", className="mb-3"),
                dbc.Card([
                    dbc.CardBody([
                        dbc.Row([
                            dbc.Col([
                                dbc.Label("Query Type:", html_for="query-type"),
                                dcc.Dropdown(
                                    id="query-type",
                                    options=[
                                        {"label": "Job Status", "value": "job_status"},
                                        {"label": "Command Outputs", "value": "command_outputs"},
                                        {"label": "Pipeline Executions", "value": "pipeline_executions"},
                                        {"label": "Wrapper Scripts", "value": "wrapper_scripts"},
                                    ],
                                    value="job_status",
                                    className="mb-3"
                                )
                            ], width=4),
                            dbc.Col([
                                dbc.Label("Date Range:", html_for="date-range"),
                                dcc.DatePickerRange(
                                    id="date-range",
                                    start_date_placeholder_text="Start Date",
                                    end_date_placeholder_text="End Date",
                                    className="mb-3"
                                )
                            ], width=8)
                        ]),
                        
                        # Filters
                        dbc.Row([
                            dbc.Col([
                                dbc.Label("Subject Filter:", html_for="subject-filter"),
                                dbc.Input(
                                    id="subject-filter",
                                    type="text",
                                    placeholder="e.g., 001 or leave empty for all",
                                    className="mb-3"
                                )
                            ], width=3),
                            dbc.Col([
                                dbc.Label("Session Filter:", html_for="session-filter"),
                                dbc.Input(
                                    id="session-filter",
                                    type="text",
                                    placeholder="e.g., 01 or leave empty for all",
                                    className="mb-3"
                                )
                            ], width=3),
                            dbc.Col([
                                dbc.Label("Task Filter:", html_for="task-filter"),
                                dbc.Input(
                                    id="task-filter",
                                    type="text",
                                    placeholder="e.g., unzip or leave empty for all",
                                    className="mb-3"
                                )
                            ], width=3),
                            dbc.Col([
                                dbc.Label("Status Filter:", html_for="status-filter"),
                                dcc.Dropdown(
                                    id="status-filter",
                                    options=[
                                        {"label": "All", "value": "all"},
                                        {"label": "Running", "value": "RUNNING"},
                                        {"label": "Success", "value": "SUCCESS"},
                                        {"label": "Failed", "value": "FAILED"},
                                        {"label": "Pending", "value": "PENDING"},
                                        {"label": "Completed", "value": "COMPLETED"}
                                    ],
                                    value="all",
                                    className="mb-3"
                                )
                            ], width=3)
                        ]),
                        
                        # Action Buttons
                        dbc.Row([
                            dbc.Col([
                                dbc.Button(
                                    "Execute Query", 
                                    id="execute-sql-query-btn", 
                                    color="primary", 
                                    className="me-2"
                                ),
                                dbc.Button(
                                    "Export CSV", 
                                    id="export-csv-btn", 
                                    color="secondary"
                                ),
                                html.Div(id="export-status", className="mt-3")
                            ], width=12)
                        ])
                    ])
                ])
            ])
        ], className="mb-4"),
        
        # Query Results - Visualizations
        dbc.Row([
            dbc.Col([
                html.H4("Visualizations", className="mb-3"),
                dbc.Card([
                    dbc.CardBody([
                        html.Div(id="sql-query-charts")
                    ])
                ])
            ])
        ], className="mb-4"),
        
        # Query Results - Table
        dbc.Row([
            dbc.Col([
                html.H4("Query Results", className="mb-3"),
                dbc.Card([
                    dbc.CardBody([
                        html.Div(id="sql-query-results")
                    ])
                ])
            ])
        ], className="mb-4")
    ], fluid=True)