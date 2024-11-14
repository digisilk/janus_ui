from dash import dcc, html, callback_context
from dash.dependencies import Input, Output, State, ALL
from dash.exceptions import PreventUpdate
from app import app
from utils.string_presence_utils import process_apks_for_string_presence, get_string_info, DEFAULT_STRING_PATTERNS
import dash_bootstrap_components as dbc
import json
import re

def is_valid_regex(pattern):
    try:
        re.compile(pattern)
        return True
    except re.error:
        return False

def is_valid_color(color):
    if re.match(r'^#(?:[0-9a-fA-F]{3}){1,2}$', color):
        return True
    valid_color_names = ['red', 'blue', 'green', 'yellow', 'purple', 'orange', 'black', 'white', 'gray', 'pink', 'brown', 'cyan', 'magenta']
    return color.lower() in valid_color_names

@app.callback(
    [Output("string-highlight-list", "children"),
     Output("string-highlight-config-store", "data")],
    [Input("string-add-highlight", "n_clicks"),
     Input({"type": "string-remove-highlight", "index": ALL}, "n_clicks")],
    [State("string-highlight-pattern", "value"),
     State("string-highlight-color", "value"),
     State("string-highlight-list", "children"),
     State("string-highlight-config-store", "data")]
)
def manage_string_highlight_config(add_clicks, remove_clicks, pattern, color, current_list, current_config):
    ctx = callback_context
    if not ctx.triggered:
        return current_list, current_config or {}

    triggered_id = ctx.triggered[0]['prop_id'].split('.')[0]

    if triggered_id == "string-add-highlight":
        if add_clicks is None or not pattern or not color:
            raise PreventUpdate
        if not is_valid_color(color) or not is_valid_regex(pattern):
            print(f"Invalid color or regex pattern: {color}, {pattern}")
            raise PreventUpdate
        new_item = html.Div([
            html.Span(f"Pattern: {pattern}, Color: {color}"),
            dbc.Button("Remove", id={"type": "string-remove-highlight", "index": len(current_list)}, color="danger", size="sm", className="ml-2")
        ], className="d-flex justify-content-between align-items-center mb-2")
        current_list.append(new_item)
        current_config = current_config or {}
        current_config[pattern] = color
        print(f"New highlight added: {pattern}, {color}")
    elif "string-remove-highlight" in triggered_id:
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
    [Output("string-pattern-name", "value"),
     Output("string-pattern-regex", "value")],
    Input("string-pattern-default", "value")
)
def set_default_pattern(selected_default):
    if selected_default:
        return selected_default, DEFAULT_STRING_PATTERNS[selected_default]
    return "", ""

@app.callback(
    [Output("string-pattern-list", "children"),
     Output("string-pattern-store", "data")],
    [Input("string-add-pattern", "n_clicks"),
     Input({"type": "string-remove-pattern", "index": ALL}, "n_clicks")],
    [State("string-pattern-name", "value"),
     State("string-pattern-regex", "value"),
     State("string-pattern-list", "children"),
     State("string-pattern-store", "data")]
)
def manage_string_patterns(add_clicks, remove_clicks, pattern_name, pattern_regex, current_list, current_patterns):
    ctx = callback_context
    if not ctx.triggered:
        return current_list, current_patterns or {}

    triggered_id = ctx.triggered[0]['prop_id'].split('.')[0]

    if triggered_id == "string-add-pattern":
        if add_clicks is None or not pattern_name or not pattern_regex:
            raise PreventUpdate
        if not is_valid_regex(pattern_regex):
            print(f"Invalid regex pattern: {pattern_regex}")
            raise PreventUpdate
        new_item = html.Div([
            html.Span(f"Name: {pattern_name}, Pattern: {pattern_regex}"),
            dbc.Button("Remove", id={"type": "string-remove-pattern", "index": len(current_list)}, color="danger", size="sm", className="ml-2")
        ], className="d-flex justify-content-between align-items-center mb-2")
        current_list.append(new_item)
        current_patterns = current_patterns or {}
        current_patterns[pattern_name] = pattern_regex
        print(f"New pattern added: {pattern_name}, {pattern_regex}")
    elif "string-remove-pattern" in triggered_id:
        remove_index = json.loads(triggered_id)["index"]
        removed_item = current_list.pop(remove_index)
        removed_pattern_name = removed_item['props']['children'][0]['props']['children'].split(',')[0].split(': ')[1]
        current_patterns.pop(removed_pattern_name, None)

    return current_list, current_patterns

@app.callback(
    [Output("string-plot-output", "children"),
     Output("string-info-output", "children")],
    Input("string-submit-button", "n_clicks"),
    [State("string-api-key", "value"),
     State("string-package-name", "value"),
     State("string-start-date", "value"),
     State("string-end-date", "value"),
     State("string-samples-per-year", "value"),
     State("string-highlight-config-store", "data"),
     State("string-pattern-store", "data")]
)
def update_string_presence_plot(n_clicks, api_key, package_name, start_date, end_date, samples_per_year, highlight_config, string_patterns):
    if n_clicks is None or not api_key:
        raise PreventUpdate

    fig, present_patterns, string_matches = process_apks_for_string_presence(api_key, package_name, start_date, end_date, samples_per_year, highlight_config, string_patterns)
    string_info = get_string_info(present_patterns, string_matches)
    
    return [
        dcc.Graph(figure=fig),
        html.Div([
            html.H5("String Pattern Information", className="mb-3"),
            html.Div(string_info)
        ])
    ]
