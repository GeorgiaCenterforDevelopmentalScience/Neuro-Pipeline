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
    """Create the project configuration page"""
    return html.Div([
        dbc.Container([
            dbc.Row([
                dbc.Col([
                    html.H2("Project Configuration", className="mb-3"),
                    html.Hr()
                ])
            ]),
            
            # Create New Configuration Section
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
            ], className="mb-3"),
            
            # Load/Edit Existing Configuration Section
            dbc.Row([
                dbc.Col([
                    dbc.Card([
                        dbc.CardHeader("Load/Edit Existing Configuration"),
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
                                    dbc.Button(
                                        "Load", 
                                        id="load-config-btn", 
                                        color="primary", 
                                        className="mt-4"
                                    )
                                ], width=2)
                            ])
                        ])
                    ])
                ])
            ], className="mb-3"),
            
            # YAML Editor Section
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
                            dbc.Button(
                                "Save Configuration", 
                                id="save-config-btn", 
                                color="success", 
                                className="me-2"
                            ),
                            html.Div(id="yaml-validation-result", className="mt-3")
                        ])
                    ])
                ])
            ], className="mb-3"),
            
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