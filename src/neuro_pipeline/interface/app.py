import dash
from dash import dcc, html, Input, Output
import dash_bootstrap_components as dbc

# Import custom modules
from .components.analysis_control import create_analysis_control_layout
from .components.job_monitor import create_job_monitor_layout

# SQL query functionality integrated into job_db.py
class PipelineDBQuery:
    def __init__(self, db_path):
        self.db_path = db_path
    
    def query_job_status(self, **kwargs):
        return []
    
    def query_command_outputs(self, **kwargs):
        return []
    
    def query_pipeline_executions(self, **kwargs):
        return []

app = dash.Dash(
    __name__,
    external_stylesheets=[
        dbc.themes.COSMO, # BOOTSTRAP COSMO
        "https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css"
    ]
)

app.index_string = '''
<!DOCTYPE html>
<html>
    <head>
        {%metas%}
        <title>{%title%}</title>
        {%favicon%}
        {%css%}
    </head>
    <body>
        {%app_entry%}
        <footer>
            {%config%}
            {%scripts%}
            {%renderer%}
        </footer>
    </body>
</html>
'''

app.title = "GCDS Neuro Pipeline"

# Initialize global state
app.global_state = {
    'subjects': [],
    'current_project': None,
    'pipeline_commands': [],
    'job_status': {},
    'execution_logs': []
}

def create_sidebar():
    """Create the sidebar navigation"""
    return html.Div([
        html.Div([
            html.H2("GCDS Neuro Pipeline", className="text-white mb-4"),
            html.Hr(className="text-white"),
            dbc.Nav([
                dbc.NavLink([
                    html.I(className="fas fa-cogs me-2"),
                    "Analysis Control"
                ], href="/analysis-control", active="exact", className="text-white"),
                dbc.NavLink([
                    html.I(className="fas fa-cog me-2"),
                    "Project Config"
                ], href="/project-config", active="exact", className="text-white"),
                dbc.NavLink([
                    html.I(className="fas fa-chart-line me-2"),
                    "Job Monitor"
                ], href="/job-monitor", active="exact", className="text-white"),
            ], vertical=True, pills=True, className="mb-4"),
        ], className="p-3")
    ], className="bg-dark", style={"height": "100vh", "width": "250px"})

def create_main_layout():
    """Create the main layout with collapsible sidebar"""
    return html.Div([
        dcc.Location(id="url", refresh=False),
        dcc.Store(id="subjects-store"),
        dcc.Store(id="pipeline-commands-store"),
        dcc.Store(id="job-status-store"),
        
        # Sidebar toggle button
        html.Button([
            html.I(className="fas fa-bars")
        ], id="sidebar-toggle", className="sidebar-toggle", n_clicks=0),
        
        # Theme toggle button
        html.Button([
            html.I(className="fas fa-palette")
        ], id="theme-toggle", className="theme-toggle", n_clicks=0),
        
        # Sidebar
        html.Div([
            create_sidebar()
        ], id="sidebar", className="sidebar sidebar-transition", style={"width": "250px"}),
        
        # Main content area
        html.Div([
            html.Div(id="page-content")
        ], id="main-content", className="main-content")
    ], id="app-container", className="theme-dark")


def create_project_config_page():
    """Create the project configuration page with two tabs: project config + results check"""
    return html.Div([
        dbc.Container([
            dbc.Row([
                dbc.Col([
                    html.H2("Project Configuration", className="mb-3"),
                    html.Hr()
                ])
            ]),

            dbc.Tabs([

                # ── Tab 1: Project Config ─────────────────────────────────
                dbc.Tab(label="Project Config", tab_id="tab-project-config", children=[
                    html.Div([

                        # Create New Configuration
                        dbc.Row([
                            dbc.Col([
                                dbc.Card([
                                    dbc.CardHeader("Create New Configuration"),
                                    dbc.CardBody([
                                        dbc.Row([
                                            dbc.Col([
                                                dbc.Label("Project Name:", html_for="new-project-name"),
                                                dbc.Input(
                                                    id="new-project-name",
                                                    type="text",
                                                    placeholder="e.g., branch, study1",
                                                    className="mb-3"
                                                )
                                            ], width=6),
                                            dbc.Col([
                                                dbc.Label("Output Directory:", html_for="new-config-output-dir"),
                                                dbc.Input(
                                                    id="new-config-output-dir",
                                                    type="text",
                                                    value="./config/project_config",
                                                    className="mb-3"
                                                )
                                            ], width=6)
                                        ]),
                                        dbc.Button(
                                            "Generate Configuration Template",
                                            id="generate-new-config-btn",
                                            color="primary",
                                            className="me-2"
                                        ),
                                        html.Div(id="new-config-result", className="mt-3")
                                    ])
                                ])
                            ])
                        ], className="mb-3 mt-3"),

                        # Load / Edit Existing
                        dbc.Row([
                            dbc.Col([
                                dbc.Card([
                                    dbc.CardHeader("Load / Edit Existing Configuration"),
                                    dbc.CardBody([
                                        dbc.Row([
                                            dbc.Col([
                                                dbc.Label("Config File Path:", html_for="config-file-path"),
                                                dbc.Input(
                                                    id="config-file-path",
                                                    type="text",
                                                    placeholder="Path to YAML config file",
                                                    value="config/project_config/branch_config.yaml",
                                                    className="mb-3"
                                                )
                                            ], width=10),
                                            dbc.Col([
                                                dbc.Button("Load", id="load-config-btn",
                                                           color="primary", className="mt-4")
                                            ], width=2)
                                        ])
                                    ])
                                ])
                            ])
                        ], className="mb-3"),

                        # YAML Editor
                        dbc.Row([
                            dbc.Col([
                                dbc.Card([
                                    dbc.CardHeader("YAML Configuration Editor"),
                                    dbc.CardBody([
                                        dcc.Textarea(
                                            id="yaml-editor",
                                            placeholder="Configuration will appear here after loading or generating...",
                                            style={"width": "100%", "height": "400px", "fontFamily": "monospace"},
                                            className="mb-3"
                                        ),
                                        dbc.Button("Save Configuration", id="save-config-btn",
                                                   color="success", className="me-2"),
                                        html.Div(id="yaml-validation-result", className="mt-3")
                                    ])
                                ])
                            ])
                        ], className="mb-3"),

                    ], className="pt-3")
                ]),

                # ── Tab 2: Results Check Config ───────────────────────────
                dbc.Tab(label="Results Check Config", tab_id="tab-results-check", children=[
                    html.Div([

                        dbc.Row([
                            dbc.Col([
                                dbc.Alert([
                                    html.I(className="fas fa-info-circle me-2"),
                                    "Edit the output check rules used by ",
                                    html.Strong("Resume Mode"),
                                    " and the ",
                                    html.Strong("check-outputs"),
                                    " command. Each task key must match a task name in ",
                                    html.Code("config.yaml"),
                                    "."
                                ], color="info", className="mb-3")
                            ])
                        ], className="mt-3"),

                        # Load checks config
                        dbc.Row([
                            dbc.Col([
                                dbc.Card([
                                    dbc.CardHeader("Load / Edit Results Check Configuration"),
                                    dbc.CardBody([
                                        dbc.Row([
                                            dbc.Col([
                                                dbc.Label("Project Name:", html_for="checks-project-name"),
                                                dbc.Input(
                                                    id="checks-project-name",
                                                    type="text",
                                                    placeholder="e.g., test, branch",
                                                    className="mb-3"
                                                )
                                            ], width=4),
                                            dbc.Col([
                                                dbc.Label("Checks File Path:", html_for="checks-file-path"),
                                                dbc.Input(
                                                    id="checks-file-path",
                                                    type="text",
                                                    placeholder="config/results_check/<project>_checks.yaml",
                                                    className="mb-3"
                                                )
                                            ], width=6),
                                            dbc.Col([
                                                dbc.Button("Load", id="load-checks-btn",
                                                           color="primary", className="mt-4 me-2"),
                                                dbc.Button("New", id="new-checks-btn",
                                                           color="outline-secondary", className="mt-4")
                                            ], width=2)
                                        ])
                                    ])
                                ])
                            ])
                        ], className="mb-3"),

                        # Checks YAML Editor
                        dbc.Row([
                            dbc.Col([
                                dbc.Card([
                                    dbc.CardHeader([
                                        "Results Check YAML Editor",
                                        dbc.Badge("output_checks", color="secondary", className="ms-2")
                                    ]),
                                    dbc.CardBody([
                                        dbc.Row([
                                            dbc.Col([
                                                html.Small([
                                                    "Supported check types: ",
                                                    html.Code("required_files"),
                                                    " (file glob + optional min_size_kb)  ·  ",
                                                    html.Code("count_check"),
                                                    " (expected_count ± tolerance)"
                                                ], className="text-muted d-block mb-2")
                                            ])
                                        ]),
                                        dcc.Textarea(
                                            id="checks-yaml-editor",
                                            placeholder=(
                                                "# Example:\n"
                                                "rest_fmriprep_preprocess:\n"
                                                "  output_path: \"{work_dir}/BIDS_derivatives/fmriprep/\"\n"
                                                "  required_files:\n"
                                                "    - pattern: \"sub-{subject}*.html\"\n"
                                                "      min_size_kb: 500\n"
                                            ),
                                            style={"width": "100%", "height": "450px",
                                                   "fontFamily": "monospace"},
                                            className="mb-3"
                                        ),
                                        dbc.Row([
                                            dbc.Col([
                                                dbc.Button("Save Checks Config", id="save-checks-btn",
                                                           color="success", className="me-2"),
                                                dbc.Button("Validate YAML", id="validate-checks-btn",
                                                           color="outline-info", className="me-2"),
                                            ]),
                                        ]),
                                        html.Div(id="checks-validation-result", className="mt-3")
                                    ])
                                ])
                            ])
                        ], className="mb-3"),

                    ], className="pt-3")
                ]),

                # ── Tab 3: Global Pipeline Config ────────────────────────
                dbc.Tab(label="Global Pipeline Config", tab_id="tab-global-config", children=[
                    html.Div([

                        dbc.Row([
                            dbc.Col([
                                dbc.Alert([
                                    html.I(className="fas fa-exclamation-circle me-2"),
                                    html.Strong("Caution: "),
                                    "This file controls task definitions, resource profiles, and "
                                    "SLURM defaults for the entire pipeline. Changes affect all "
                                    "projects. Edit carefully and validate before saving."
                                ], color="warning", className="mb-3")
                            ])
                        ], className="mt-3"),

                        dbc.Row([
                            dbc.Col([
                                dbc.Card([
                                    dbc.CardHeader([
                                        html.I(className="fas fa-cog me-2"),
                                        "Global Config Editor",
                                        dbc.Badge("config.yaml", color="dark", className="ms-2")
                                    ]),
                                    dbc.CardBody([
                                        dbc.Row([
                                            dbc.Col([
                                                html.Small([
                                                    "Editing: ",
                                                    html.Code(
                                                        "src/neuro_pipeline/pipeline/config/config.yaml",
                                                        className="text-muted"
                                                    )
                                                ], className="d-block mb-3")
                                            ])
                                        ]),
                                        dcc.Textarea(
                                            id="global-config-editor",
                                            placeholder="Click 'Load' to open config.yaml...",
                                            style={"width": "100%", "height": "520px",
                                                   "fontFamily": "monospace"},
                                            className="mb-3"
                                        ),
                                        dbc.Row([
                                            dbc.Col([
                                                dbc.Button(
                                                    [html.I(className="fas fa-folder-open me-2"), "Load"],
                                                    id="load-global-config-btn",
                                                    color="primary", className="me-2"
                                                ),
                                                dbc.Button(
                                                    [html.I(className="fas fa-check me-2"), "Validate YAML"],
                                                    id="validate-global-config-btn",
                                                    color="outline-info", className="me-2"
                                                ),
                                                dbc.Button(
                                                    [html.I(className="fas fa-save me-2"), "Save"],
                                                    id="save-global-config-btn",
                                                    color="success"
                                                ),
                                            ])
                                        ]),
                                        html.Div(id="global-config-result", className="mt-3")
                                    ])
                                ])
                            ])
                        ], className="mb-3"),

                    ], className="pt-3")
                ]),

            ], id="config-tabs", active_tab="tab-project-config"),

        ], fluid=True, style={
            "border": "1px solid rgba(255,255,255,0.07)",
            "borderRadius": "14px",
            "boxShadow": "0 2px 8px rgba(0,0,0,0.08)",
            "padding": "10px 0 10px 0",
            "background": "transparent"
        })
    ])


app.layout = create_main_layout()

# Import and register callbacks
from .callbacks import register_callbacks
register_callbacks(app)

# Page routing callback
@app.callback(
    Output("page-content", "children"),
    Input("url", "pathname")
)
def display_page(pathname):
    # Default root goes to Analysis Control page
    if pathname == "/" or pathname == "/home":
        return create_analysis_control_layout()
    elif pathname == "/analysis-control":
        return create_analysis_control_layout()
    elif pathname == "/project-config":
        return create_project_config_page()
    elif pathname == "/job-monitor":
        return create_job_monitor_layout()
    else:
        return create_analysis_control_layout()


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=8050)