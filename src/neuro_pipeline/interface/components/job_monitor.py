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
                            ], width=12)
                        ])
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
                                        {"label": "Pipeline Executions", "value": "pipeline_executions"}
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