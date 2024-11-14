# callbacks/apk_historical_analysis_callbacks.py
from dash import dcc, html, callback_context, no_update
import dash
from dash.dependencies import Input, Output, State, ALL
from app import app
from utils.historical_connectivity_logic import process_apks, generate_download_link, ui_logger, current_process
import json
import dash_bootstrap_components as dbc
import re
import datetime
import os
import pathlib
from dash.exceptions import PreventUpdate
import threading
import logging
from functools import lru_cache
from layouts.historical_connectivity_layout import preset_configs

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def is_valid_color(color):
    # Check if a valid hex color code
    if re.match(r'^#(?:[0-9a-fA-F]{3}){1,2}$', color):
        return True
    # Check if a valid color name
    valid_color_names = ['red', 'blue', 'green', 'yellow', 'purple', 'orange', 'black', 'white']
    return color.lower() in valid_color_names

# Load package IDs with their counts
try:
    with open('filtered_package_ids_with_counts10_ver.json', 'r') as f:
        package_data = json.load(f)
    package_dict = {pkg['name']: pkg['count'] for pkg in package_data}
    logger.info(f"Loaded {len(package_dict)} package IDs")
except Exception as e:
    logger.error(f"Error loading package IDs: {str(e)}")
    package_dict = {}

@lru_cache(maxsize=100)
def custom_search(search_value, limit=100):
    search_value = search_value.lower()
    
    def match_score(pkg):
        pkg_lower = pkg.lower()
        pkg_parts = pkg_lower.split('.')
        score = 0
        
        # Exact match
        if search_value == pkg_lower:
            return 1000000 + package_dict[pkg]
        
        # Match beginning of any part
        if any(part.startswith(search_value) for part in pkg_parts):
            score += 10000
        
        # Substring match
        elif search_value in pkg_lower:
            score += 1000
        
        # Add version count to score
        score += package_dict[pkg]
        
        return score
    
    # Filter and sort packages
    matched_packages = [(pkg, match_score(pkg)) for pkg in package_dict.keys() if match_score(pkg) > 0]
    sorted_packages = sorted(matched_packages, key=lambda x: -x[1])
    
    return [pkg for pkg, _ in sorted_packages[:limit]]

@app.callback(
    [Output("highlight-list", "children"),
     Output("highlight-config-store", "data"),
     Output("highlight-dropdown", "value")],
    [Input("highlight-dropdown", "value"),
     Input("add-highlight", "n_clicks"),
     Input({"type": "remove-highlight", "index": ALL}, "n_clicks")],
    [State("highlight-pattern", "value"),
     State("highlight-color", "value"),
     State("highlight-config-store", "data")],
    prevent_initial_call=True
)
def update_highlight_config(selected_presets, add_clicks, remove_clicks, custom_pattern, custom_color, stored_config):
    ctx = dash.callback_context
    triggered_id = ctx.triggered[0]['prop_id'].split('.')[0]

    if stored_config is None:
        stored_config = []

    if triggered_id == "highlight-dropdown":
        # Add newly selected presets
        for preset in selected_presets or []:
            if not any(h['name'] == preset for h in stored_config):
                stored_config.append({
                    "name": preset,
                    "regex": preset_configs[preset]["regex"],
                    "color": preset_configs[preset]["color"]
                })

    elif triggered_id == "add-highlight":
        if custom_pattern and custom_color and is_valid_color(custom_color):
            stored_config.append({
                "name": f"Custom: {custom_pattern}",
                "regex": custom_pattern,
                "color": custom_color
            })

    elif "remove-highlight" in triggered_id:
        remove_index = json.loads(triggered_id)['index']
        if 0 <= remove_index < len(stored_config):
            removed_item = stored_config.pop(remove_index)
            if not removed_item['name'].startswith("Custom:"):
                selected_presets = [preset for preset in (selected_presets or []) if preset != removed_item['name']]

    highlight_list = create_highlight_list(stored_config)
    return highlight_list, stored_config, selected_presets

def create_highlight_list(highlight_config):
    return [
        html.Div([
            html.Span(f"{item['name']}: ", style={"fontWeight": "bold"}),
            html.Span(f"{item['regex'][:30]}..." if len(item['regex']) > 30 else item['regex']),
            html.Span(f" ({item['color']})", style={"color": item['color']}),
            html.Button("×", id={"type": "remove-highlight", "index": i}, n_clicks=0, style={"marginLeft": "10px"}),
        ], style={"marginBottom": "5px"})
        for i, item in enumerate(highlight_config)
    ]

@app.callback(
    [Output("results-historical-connectivity", "children"),
     Output("error-message", "children"),
     Output("submit-button", "disabled"),
     Output("loading-output", "children")],
    [Input("submit-button", "n_clicks")],
    [State("api-key", "value"),
     State("start-date", "value"),
     State("end-date", "value"),
     State("package-list-dropdown", "value"),
     State("desired-versions", "value"),
     State("highlight-config-store", "data"),
     State("num-cores-slider", "value"),
     State("parser-selection", "value")]
)
def process_apks_callback(n_clicks, api_key, start_date, end_date, package_list_input, desired_versions, highlight_config, num_cores, parser_selection):
    global current_process

    if n_clicks is None:
        raise PreventUpdate

    ctx = callback_context
    if not ctx.triggered:
        raise PreventUpdate
    
    try:
        # Cancel the existing process if there is one
        if current_process is not None and current_process != threading.current_thread():
            current_process = None
            ui_logger.logger.info("Cancelling previous process")

        ui_logger.logger.info("Starting new APK processing")
        results = process_apks(n_clicks, api_key, start_date, end_date, package_list_input, desired_versions, highlight_config, num_cores, parser_selection)
        
        if results is None:
            ui_logger.logger.warning("Processing was cancelled or no data to display. Please check your inputs and try again.")
            return [], "Processing was cancelled or no data to display. Please check your inputs and try again.", False, None

        output_results = []
        for data_type, result in results.items():
            if result['too_large_to_display']:
                output_results.extend([
                    html.H4(f"{data_type.capitalize()} Analysis"),
                    html.P(f"The {data_type} dataset is too large to display ({result['feature_count']} features). Please download the figure to view."),
                    generate_download_link(result['figure'], package_list_input, data_type),
                    html.Hr()
                ])
            else:
                dropdown_options = [{'label': info['feature'], 'value': i} for i, info in enumerate(result['feature_info'])]
                
                output_results.extend([
                    html.H4(f"{data_type.capitalize()} Analysis"),
                    dcc.Graph(figure=result['figure'], style={'height': '800px'}),
                    generate_download_link(result['figure'], package_list_input, data_type),
                    html.H5("Feature Information"),
                    dcc.Dropdown(
                        id=f'feature-dropdown-{data_type}',
                        options=dropdown_options,
                        value=0 if dropdown_options else None,
                        placeholder="Select a feature",
                        style={'marginBottom': '10px'}
                    ),
                    html.Div(id=f'feature-info-{data_type}'),
                    dcc.Store(id=f'feature-info-store-{data_type}', data=result['feature_info']),
                    html.Hr()
                ])

        ui_logger.logger.info("APK processing complete")
        return output_results, "", False, None
    except Exception as e:
        error_message = f"An error occurred: {str(e)}"
        ui_logger.logger.error(error_message)
        return [], error_message, False, None

@app.callback(
    Output('progress-historical-connectivity', 'children'),
    [Input('progress-interval', 'n_intervals')]
)
def update_progress(n):
    return ui_logger.get_logs()

for data_type in ['urls', 'domains', 'subdomains']:
    @app.callback(
        Output(f'feature-info-{data_type}', 'children'),
        [Input(f'feature-dropdown-{data_type}', 'value')],
        [State(f'feature-info-store-{data_type}', 'data')]
    )
    def update_feature_info(selected_index, feature_info, data_type=data_type):
        if selected_index is None or not feature_info:
            return html.Div("No feature selected")
        
        info = feature_info[selected_index]
        feature = info['feature']
        
        return html.Div([
            html.P(f"Feature: {feature}"),
            html.Div([
                #html.A("Open URL", href=f"https://{feature}", target="_blank", className="me-2"),
                html.A("AlienVault", href=info['alienvault_link'], target="_blank", className="me-2"),
                html.A("WHOIS", href=info['whois_link'], target="_blank", className="me-2"),
                html.A("VirusTotal", href=f"https://www.virustotal.com/gui/domain/{feature}", target="_blank", className="me-2"),
                html.A("Shodan", href=f"https://www.shodan.io/search?query={feature}", target="_blank", className="me-2"),
                html.A("URLScan", href=f"https://urlscan.io/search/#{feature}", target="_blank", className="me-2"),
            ])
        ])

@app.callback(
    [Output("package-list-dropdown", "options"),
     Output("package-list-dropdown", "value"),
     Output("selected-package-store", "data")],
    [Input("package-list-dropdown", "search_value"),
     Input("package-list-dropdown", "value")],
    [State("selected-package-store", "data")]
)
def update_dropdown_and_store(search_value, dropdown_value, stored_value):
    ctx = callback_context
    triggered_id = ctx.triggered[0]['prop_id'].split('.')[0]

    if triggered_id == "package-list-dropdown" and dropdown_value is not None:
        return no_update, dropdown_value, dropdown_value

    if not search_value:
        return [], no_update, stored_value

    try:
        matches = custom_search(search_value)
        filtered_options = [
            {
                "label": html.Div([
                    f"{pid} (Versions: {package_dict[pid]})",
                    html.A(
                        "🔗",
                        href=f"https://play.google.com/store/apps/details?id={pid}",
                        target="_blank",
                        style={"marginLeft": "10px"},
                        title="View on Google Play"
                    )
                ]),
                "value": pid
            } for pid in matches
        ]

        # The stored value is always in the options
        if stored_value and not any(option["value"] == stored_value for option in filtered_options):
            stored_count = package_dict.get(stored_value, 0)
            filtered_options.insert(0, {
                "label": html.Div([
                    f"{stored_value} (Versions: {stored_count})",
                    html.A(
                        "🔗",
                        href=f"https://play.google.com/store/apps/details?id={stored_value}",
                        target="_blank",
                        style={"marginLeft": "10px"},
                        title="View on Google Play"
                    )
                ]),
                "value": stored_value
            })

        logger.info(f"Found {len(filtered_options)} matches for search value: {search_value}")
        return filtered_options, no_update, stored_value
    except Exception as e:
        logger.error(f"Error in update_dropdown_and_store: {str(e)}")
        return [], no_update, stored_value
