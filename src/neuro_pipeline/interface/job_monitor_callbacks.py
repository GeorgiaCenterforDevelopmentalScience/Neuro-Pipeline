import os
import sqlite3
from datetime import datetime
from dash import html, dcc, Input, Output, State
import dash_bootstrap_components as dbc
import pandas as pd
from .utils.plot_utils import (
    create_timeline_chart,
    create_status_donut,
    create_duration_radar,
    create_exit_code_bar
)

def register_job_monitor_callbacks(app):
    
    @app.callback(
        [Output("sql-query-results", "children"),
         Output("sql-query-charts", "children")],
        [Input("execute-sql-query-btn", "n_clicks")],
        [State("db-path", "value"),
         State("query-type", "value"),
         State("subject-filter", "value"),
         State("session-filter", "value"),
         State("task-filter", "value"),
         State("status-filter", "value"),
         State("date-range", "start_date"),
         State("date-range", "end_date")]
    )
    def execute_sql_query_callback(n_clicks, db_path, query_type, subject, session, task, status, start_date, end_date):
        if n_clicks is None:
            return "Click 'Execute Query' to see results", ""
        
        if not db_path or not os.path.exists(db_path):
            return dbc.Alert(f"Database file not found: {db_path}", color="danger"), ""
        
        try:
            conn = sqlite3.connect(db_path)
            
            if query_type == "job_status":
                query = "SELECT * FROM job_status WHERE 1=1"
                params = []
                
                if subject:
                    query += " AND subject LIKE ?"
                    params.append(f"%{subject}%")
                
                if session:
                    query += " AND session LIKE ?"
                    params.append(f"%{session}%")
                
                if task:
                    query += " AND task_name LIKE ?"
                    params.append(f"%{task}%")
                
                if status and status != "all":
                    query += " AND status = ?"
                    params.append(status)
                
                if start_date:
                    query += " AND start_time >= ?"
                    params.append(start_date)
                
                if end_date:
                    query += " AND start_time <= ?"
                    params.append(end_date)
                
                query += " ORDER BY start_time DESC LIMIT 100"
                
            elif query_type == "command_outputs":
                query = "SELECT * FROM command_outputs WHERE 1=1"
                params = []
                
                if subject:
                    query += " AND subject LIKE ?"
                    params.append(f"%{subject}%")
                
                if task:
                    query += " AND task_name LIKE ?"
                    params.append(f"%{task}%")
                
                if start_date:
                    query += " AND execution_time >= ?"
                    params.append(start_date)
                
                if end_date:
                    query += " AND execution_time <= ?"
                    params.append(end_date)
                
                query += " ORDER BY execution_time DESC LIMIT 100"
                
            elif query_type == "pipeline_executions":
                query = "SELECT * FROM pipeline_executions WHERE 1=1"
                params = []
                
                if session:
                    query += " AND session LIKE ?"
                    params.append(f"%{session}%")
                
                if start_date:
                    query += " AND execution_time >= ?"
                    params.append(start_date)
                
                if end_date:
                    query += " AND execution_time <= ?"
                    params.append(end_date)
                
                if status and status != "all":
                    query += " AND status = ?"
                    params.append(status)
                
                query += " ORDER BY execution_time DESC LIMIT 50"
            
            else:
                return dbc.Alert("Invalid query type", color="warning"), ""
            
            df = pd.read_sql_query(query, conn, params=params)
            conn.close()
            
            if df.empty:
                return dbc.Alert("No data found matching the criteria", color="info"), ""
            
            table = dbc.Table.from_dataframe(
                df.head(50), 
                striped=True, 
                bordered=True, 
                hover=True,
                size='sm',
                style={'fontSize': '12px'}
            )
            
            results = html.Div([
                html.H6(f"Query Results ({len(df)} records found, showing first 50)"),
                html.Div(table, style={'overflowX': 'auto', 'maxHeight': '400px', 'overflowY': 'auto'})
            ])
            
            charts = create_query_charts(df, query_type)
            
            return results, charts
            
        except sqlite3.Error as e:
            return dbc.Alert(f"Database error: {str(e)}", color="danger"), ""
        except Exception as e:
            return dbc.Alert(f"Error executing query: {str(e)}", color="danger"), ""
    
    @app.callback(
        Output("export-status", "children"),
        [Input("export-csv-btn", "n_clicks")],
        [State("db-path", "value"),
         State("query-type", "value"),
         State("subject-filter", "value"),
         State("session-filter", "value"),
         State("task-filter", "value"),
         State("status-filter", "value")]
    )
    def export_csv_callback(n_clicks, db_path, query_type, subject, session, task, status):
        if n_clicks is None:
            return ""
        
        if not db_path or not os.path.exists(db_path):
            return dbc.Alert("Database file not found", color="danger")
        
        try:
            conn = sqlite3.connect(db_path)
            
            if query_type == "job_status":
                query = "SELECT * FROM job_status WHERE 1=1"
                params = []
                
                if subject:
                    query += " AND subject LIKE ?"
                    params.append(f"%{subject}%")
                
                if session:
                    query += " AND session LIKE ?"
                    params.append(f"%{session}%")
                
                if task:
                    query += " AND task_name LIKE ?"
                    params.append(f"%{task}%")
                
                if status and status != "all":
                    query += " AND status = ?"
                    params.append(status)
                
            elif query_type == "command_outputs":
                query = "SELECT * FROM command_outputs WHERE 1=1"
                params = []
                
                if subject:
                    query += " AND subject LIKE ?"
                    params.append(f"%{subject}%")
                
                if task:
                    query += " AND task_name LIKE ?"
                    params.append(f"%{task}%")
                
            else:
                query = "SELECT * FROM pipeline_executions WHERE 1=1"
                params = []
                
                if session:
                    query += " AND session LIKE ?"
                    params.append(f"%{session}%")
            
            df = pd.read_sql_query(query, conn, params=params)
            conn.close()
            
            output_dir = os.path.dirname(db_path)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            csv_path = os.path.join(output_dir, f"{query_type}_{timestamp}.csv")
            df.to_csv(csv_path, index=False)
            
            return dbc.Alert(f"Exported {len(df)} records to {csv_path}", color="success")
            
        except Exception as e:
            return dbc.Alert(f"Export failed: {str(e)}", color="danger")


def create_query_charts(df, query_type):
    """Create visualization charts based on query results"""
    charts = []
    
    try:
        if query_type == "job_status":
            layout_parts = []
            
            # Timeline chart
            if 'start_time' in df.columns:
                timeline_fig = create_timeline_chart(df)
                layout_parts.append(
                    dbc.Row([
                        dbc.Col(dcc.Graph(figure=timeline_fig), width=12)
                    ], className="mb-4")
                )
            
            # Duration Radar + Status Donut
            second_row_charts = []
            
            if 'duration_hours' in df.columns and 'task_name' in df.columns:
                radar_fig = create_duration_radar(df)
                second_row_charts.append(
                    dbc.Col(dcc.Graph(figure=radar_fig), width=6)
                )
            
            if 'status' in df.columns:
                donut_fig = create_status_donut(df)
                second_row_charts.append(
                    dbc.Col(dcc.Graph(figure=donut_fig), width=6)
                )
            
            if second_row_charts:
                layout_parts.append(
                    dbc.Row(second_row_charts, className="mb-4")
                )
            
            return html.Div(layout_parts)
        
        elif query_type == "pipeline_executions":
            if 'status' in df.columns:
                donut_fig = create_status_donut(df)
                charts.append(dcc.Graph(figure=donut_fig))
            
            if 'execution_time' in df.columns:
                df_renamed = df.rename(columns={'execution_time': 'start_time'})
                timeline_fig = create_timeline_chart(df_renamed)
                charts.append(dcc.Graph(figure=timeline_fig))
        
        elif query_type == "command_outputs":
            if 'exit_code' in df.columns:
                exit_fig = create_exit_code_bar(df)
                charts.append(dcc.Graph(figure=exit_fig))
    
    except Exception as e:
        charts.append(html.Div(f"Error creating charts: {str(e)}", className="text-danger"))
    
    if len(charts) == 0:
        return ""
    elif len(charts) == 1:
        return html.Div(charts)
    else:
        return dbc.Row([
            dbc.Col(charts[0], width=6),
            dbc.Col(charts[1], width=6)
        ])