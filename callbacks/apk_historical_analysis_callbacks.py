# callbacks/apk_historical_analysis_callbacks.py
from dash import dcc, html
from dash.dependencies import Input, Output, State
from app import app
from utils.apk_historical_analysis_util import process_apks, progress

@app.callback(
    Output("results", "children"),
    #[Output("results", "children")],
    # Output("pie-charts", "children")],
    [Input("submit-button", "n_clicks")],
    [State("api-key", "value"),
     State("start-date", "value"),
     State("end-date", "value"),
     State("package-list", "value"),
     State("desired-versions", "value"),
     State("highlight-config", "value"),
     State("data-type", "value"),
     #State("use-cache", "value"),
     State("use-cache-json", "value"),
     State("core-count", "value")]
)
def process_apks_callback(n_clicks, api_key, start_date, end_date, package_list_input, desired_versions, highlight_config_str, data_type_input, use_cache_json, core_count_input):
    return process_apks(n_clicks, api_key, start_date, end_date, package_list_input, desired_versions, highlight_config_str, data_type_input, use_cache_json, core_count_input)

@app.callback(
    Output('progress', 'children'),
    Input('interval-component', 'n_intervals')
)
def update_progress(n):
    global progress
    return html.Div([
        html.P(f"Current Task: {progress['current_task']}"),
        html.P(f"Completed Tasks: {progress['completed_tasks']} / {progress['total_tasks']}")
    ])
