from dash import dcc, html, callback_context
from dash.dependencies import Input, Output, State, ALL
from dash.exceptions import PreventUpdate
from app import app
from utils.sdk_presence_utils import process_apks_for_sdk_presence, get_sdk_info
import dash_bootstrap_components as dbc
import json
import re

def is_valid_color(color):
    if re.match(r'^#(?:[0-9a-fA-F]{3}){1,2}$', color):
        return True
    valid_color_names = ['red', 'blue', 'green', 'yellow', 'purple', 'orange', 'black', 'white']
    return color.lower() in valid_color_names

def is_valid_regex(pattern):
    try:
        re.compile(pattern)
        return True
    except re.error:
        return False

@app.callback(
    [Output("sdk-highlight-list", "children"),
     Output("sdk-highlight-config-store", "data")],
    [Input("sdk-add-highlight", "n_clicks"),
     Input({"type": "sdk-remove-highlight", "index": ALL}, "n_clicks")],
    [State("sdk-highlight-pattern", "value"),
     State("sdk-highlight-color", "value"),
     State("sdk-highlight-list", "children"),
     State("sdk-highlight-config-store", "data")]
)
def manage_sdk_highlight_config(add_clicks, remove_clicks, pattern, color, current_list, current_config):
    ctx = callback_context
    if not ctx.triggered:
        return current_list, current_config or {}

    triggered_id = ctx.triggered[0]['prop_id'].split('.')[0]

    if triggered_id == "sdk-add-highlight":
        if add_clicks is None or not pattern or not color:
            raise PreventUpdate
        if not is_valid_color(color) or not is_valid_regex(pattern):
            print(f"Invalid color or regex pattern: {color}, {pattern}")
            raise PreventUpdate
        new_item = html.Div([
            html.Span(f"Pattern: {pattern}, Color: {color}"),
            dbc.Button("Remove", id={"type": "sdk-remove-highlight", "index": len(current_list)}, color="danger", size="sm", className="ml-2")
        ], className="d-flex justify-content-between align-items-center mb-2")
        current_list.append(new_item)
        current_config = current_config or {}
        current_config[pattern] = color
        print(f"New highlight added: {pattern}, {color}")
    elif "sdk-remove-highlight" in triggered_id:
        if not current_list:  # Check if the list is already empty
            return [], {}
        remove_index = json.loads(triggered_id)["index"]
        if remove_index < len(current_list):
            removed_item = current_list.pop(remove_index)
            removed_pattern = removed_item['props']['children'][0]['props']['children'].split(',')[0].split(': ')[1]
            current_config.pop(removed_pattern, None)
        else:
            print(f"Warning: Tried to remove index {remove_index} from list of length {len(current_list)}")

    return current_list, current_config

@app.callback(
    [Output("sdk-plot-output", "children"),
     Output("sdk-info-output", "children")],
    Input("sdk-submit-button", "n_clicks"),
    [State("sdk-api-key", "value"),
     State("sdk-package-name", "value"),
     State("sdk-start-date", "value"),
     State("sdk-end-date", "value"),
     State("sdk-samples-per-year", "value"),
     State("sdk-highlight-config-store", "data")]
)
def update_sdk_presence_plot(n_clicks, api_key, package_name, start_date, end_date, samples_per_year, highlight_config):
    if n_clicks is None or not api_key:
        raise PreventUpdate

    fig, present_sdks = process_apks_for_sdk_presence(api_key, package_name, start_date, end_date, samples_per_year, highlight_config)
    sdk_info = get_sdk_info(present_sdks)
    
    return [
        dcc.Graph(figure=fig),
        html.Div([
            html.H5("SDK Information", className="mb-3"),
            html.Div(sdk_info)
        ])
    ]
