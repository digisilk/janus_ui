# callbacks/user_apk_analysis_callbacks.py
from dash import dcc, html, callback_context, no_update
from dash.dependencies import Input, Output, State, ALL, MATCH
from app import app

from utils.user_apk_analysis_logic import (
    process_uploaded_apks,
    generate_download_link,
    extract_apk_features,
    plot_data,
    save_uploaded_files,
    save_uploaded_file_to_server
)
from dash.exceptions import PreventUpdate

from dash import dcc, html, callback_context, no_update
from dash.dependencies import Input, Output, State, ALL, MATCH
from dash.exceptions import PreventUpdate
import dash
from app import app
from utils.user_apk_analysis_logic import process_uploaded_apks, generate_download_link, extract_apk_features
import logging
import json
import re
from layouts.user_apk_analysis_layout import preset_configs
import dash_bootstrap_components as dbc
from androguard.core.bytecodes.apk import APK
import base64
import io
import tempfile
import os
from multiprocessing import Pool


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@app.callback(
    Output('user-apk-upload-output', 'children'),
    Input('user-apk-upload', 'contents'),
    State('user-apk-upload', 'filename')
)
def update_output(list_of_contents, list_of_names):
    if list_of_contents is not None:
        children = [
            html.Div([
                html.H5(f'Uploaded file: {name}')
            ]) for name in list_of_names
        ]
        return children
    return []

@app.callback(
    [Output("user-apk-results", "children"),
     Output("user-apk-error-message", "children"),
     Output("user-apk-submit-button", "disabled"),
     Output("user-apk-loading-output", "children"),
     Output('user-apk-feature-info-store', 'data')],
    [Input("user-apk-submit-button", "n_clicks")],
    [State("user-apk-upload-store", "data"),
     State("user-apk-highlight-config-store", "data"),
     State("user-apk-num-cores-slider", "value"),
     State("user-apk-parser-selection", "value"),
     State("user-apk-sort-order", "value")]
)
def process_apks_callback(n_clicks, stored_data, highlight_config, num_cores, parser_selection, sort_order):
    if n_clicks is None or not stored_data:
        raise PreventUpdate

    try:
        results = process_uploaded_apks(stored_data, highlight_config, num_cores, parser_selection, sort_order)
        
        output_results = []
        feature_info_store = {}  #  feature info store

        for data_type, result in results.items():
            if result is None:
                output_results.append(html.P(f"No {data_type} found in the uploaded APK(s)."))
            elif result.get('too_large_to_display', False):
                output_results.extend([
                    html.H4(f"{data_type.capitalize()} Analysis"),
                    html.P(f"The {data_type} dataset is too large to display ({result['feature_count']} features). Please download the figure to view."),
                    generate_download_link(result['figure'], "user_uploaded_apks", data_type),
                    html.Hr()
                ])
            else:
                dropdown_options = [{'label': info['feature'], 'value': i} for i, info in enumerate(result['feature_info'])]
                
                output_results.extend([
                    html.H4(f"{data_type.capitalize()} Analysis"),
                    dcc.Graph(figure=result['figure'], style={'height': '800px'}),
                    generate_download_link(result['figure'], "user_uploaded_apks", data_type),
                    html.H5("Feature Information"),
                    dcc.Dropdown(
                        id={'type': 'user-apk-feature-dropdown', 'index': data_type},
                        options=dropdown_options,
                        value=0 if dropdown_options else None,
                        placeholder="Select a feature",
                        style={'marginBottom': '10px'}
                    ),
                    html.Div(id={'type': 'user-apk-feature-info', 'index': data_type}),
                    html.Hr()
                ])
                
                # Store feature info for this data type
                feature_info_store[data_type] = result['feature_info']

        if not output_results:
            output_results.append(html.P("No data found in the uploaded APK(s)."))

        return output_results, "", False, None, feature_info_store
    except Exception as e:
        error_message = f"An error occurred: {str(e)}"
        logger.error(error_message)
        return [], error_message, False, None, {}

@app.callback(
    Output({'type': 'user-apk-feature-info', 'index': MATCH}, 'children'),
    Input({'type': 'user-apk-feature-dropdown', 'index': MATCH}, 'value'),
    State('user-apk-feature-info-store', 'data'),
    State({'type': 'user-apk-feature-dropdown', 'index': MATCH}, 'id')
)
def update_feature_info(selected_index, feature_info_store, dropdown_id):
    if selected_index is None or not feature_info_store:
        return html.Div("No feature selected")
    
    data_type = dropdown_id['index']
    info = feature_info_store[data_type][selected_index]
    feature = info['feature']
    
    return html.Div([
        html.P(f"Feature: {feature}"),
        html.Div([
            html.A("Open URL", href=f"https://{feature}", target="_blank", className="me-2"),
            html.A("AlienVault", href=info['alienvault_link'], target="_blank", className="me-2"),
            html.A("WHOIS", href=info['whois_link'], target="_blank", className="me-2"),
            html.A("VirusTotal", href=f"https://www.virustotal.com/gui/domain/{feature}", target="_blank", className="me-2"),
            html.A("Shodan", href=f"https://www.shodan.io/search?query={feature}", target="_blank", className="me-2"),
            html.A("URLScan", href=f"https://urlscan.io/search/#{feature}", target="_blank", className="me-2"),
        ])
    ])

@app.callback(
    [Output("user-apk-highlight-list", "children"),
     Output("user-apk-highlight-config-store", "data"),
     Output("user-apk-highlight-dropdown", "value")],
    [Input("user-apk-highlight-dropdown", "value"),
     Input("user-apk-add-highlight", "n_clicks"),
     Input({"type": "user-apk-remove-highlight", "index": ALL}, "n_clicks")],
    [State("user-apk-highlight-pattern", "value"),
     State("user-apk-highlight-color", "value"),
     State("user-apk-highlight-config-store", "data")],
    prevent_initial_call=True
)
def update_highlight_config(selected_presets, add_clicks, remove_clicks, custom_pattern, custom_color, stored_config):
    ctx = dash.callback_context
    triggered_id = ctx.triggered[0]['prop_id'].split('.')[0]

    if stored_config is None:
        stored_config = []

    if triggered_id == "user-apk-highlight-dropdown":
        # Add new selected presets
        for preset in selected_presets or []:
            if preset not in [item['name'] for item in stored_config]:
                stored_config.append({
                    "name": preset,
                    "regex": preset_configs[preset]["regex"],
                    "color": preset_configs[preset]["color"]
                })

    elif triggered_id == "user-apk-add-highlight":
        if custom_pattern and custom_color and is_valid_color(custom_color):
            stored_config.append({
                "name": f"Custom: {custom_pattern}",
                "regex": custom_pattern,
                "color": custom_color
            })

    elif "user-apk-remove-highlight" in triggered_id:
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
            html.Button("×", id={"type": "user-apk-remove-highlight", "index": i}, n_clicks=0, style={"marginLeft": "10px"}),
        ], style={"marginBottom": "5px"})
        for i, item in enumerate(highlight_config)
    ]

def is_valid_color(color):
    if re.match(r'^#(?:[0-9a-fA-F]{3}){1,2}$', color):
        return True
    valid_color_names = ['red', 'blue', 'green', 'yellow', 'purple', 'orange', 'black', 'white']
    return color.lower() in valid_color_names

@app.callback(
    Output("user-apk-progress", "children"),
    [Input("user-apk-progress-interval", "n_intervals")]
)
def update_progress(n):
    # Implement progress update logic here
    return "Processing..."

# Add these callbacks for each data type
for data_type in ['urls', 'domains', 'subdomains']:
    @app.callback(
        Output(f'user-apk-feature-info-{data_type}', 'children'),
        [Input(f'user-apk-feature-dropdown-{data_type}', 'value')],
        [State(f'user-apk-feature-info-store-{data_type}', 'data')]
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
    [Output('user-apk-upload-store', 'data'),
     Output('user-apk-upload-list', 'children')],
    [Input('user-apk-upload', 'contents'),
     Input('user-apk-upload', 'filename'),
     Input({'type': 'move-up', 'index': ALL}, 'n_clicks'),
     Input({'type': 'move-down', 'index': ALL}, 'n_clicks'),
     Input({'type': 'remove-apk', 'index': ALL}, 'n_clicks')],
    [State('user-apk-upload-store', 'data')]
)
def manage_uploaded_files(contents, filenames, move_up_clicks, move_down_clicks, remove_clicks, stored_data):
    ctx = callback_context
    if not ctx.triggered:
        raise PreventUpdate
    
    trigger_id = ctx.triggered[0]['prop_id'].split('.')[0]

    if trigger_id == 'user-apk-upload':
        # Handle new file uploads
        stored_data = stored_data or []
        for content, filename in zip(contents or [], filenames or []):
            if content and filename:
                try:
                    # Save the file to the server and get the server-side path
                    server_path = save_uploaded_file_to_server(content, filename)
                    
                    # Extract APK information
                    apk = APK(server_path)
                    stored_data.append({
                        'filename': filename,
                        'package_name': apk.get_package(),
                        'version_code': apk.get_androidversion_code(),
                        'server_path': server_path
                    })
                except Exception as e:
                    logger.error(f"Error processing APK {filename}: {str(e)}")

    else:
        # Handle move up, move down, or remove actions
        action, index = json.loads(trigger_id)['type'], json.loads(trigger_id)['index']

        if action == 'move-up' and index > 0:
            stored_data[index], stored_data[index-1] = stored_data[index-1], stored_data[index]
        elif action == 'move-down' and index < len(stored_data) - 1:
            stored_data[index], stored_data[index+1] = stored_data[index+1], stored_data[index]
        elif action == 'remove-apk':
            # Remove the file from the server when removing from the list
            file_to_remove = stored_data.pop(index)
            try:
                os.remove(file_to_remove['server_path'])
            except Exception as e:
                logger.error(f"Error removing file {file_to_remove['filename']}: {str(e)}")

    upload_list = create_upload_list(stored_data)
    return stored_data, upload_list

def create_upload_list(stored_data):
    return html.Div([
        dbc.ListGroup([
            dbc.ListGroupItem([
                dbc.Row([
                    dbc.Col([
                        html.H5(truncate_string(item['filename'], 30), className='mb-1', title=item['filename']),
                        html.Small(f"Package: {item['package_name']}", className='text-muted d-block'),
                        html.Small(f"Version Code: {item['version_code']}", className='text-muted d-block'),
                    ], width=9),
                    dbc.Col([
                        dbc.ButtonGroup([
                            dbc.Button("↑", id={'type': 'move-up', 'index': i}, size="sm", color="light", className="mr-1"),
                            dbc.Button("↓", id={'type': 'move-down', 'index': i}, size="sm", color="light", className="mr-1"),
                            dbc.Button("×", id={'type': 'remove-apk', 'index': i}, size="sm", color="danger"),
                        ], size="sm")
                    ], width=3, className="d-flex align-items-center justify-content-end")
                ], className="g-0")
            ])
            for i, item in enumerate(stored_data)
        ])
    ])

def truncate_string(string, max_length):
    return string[:max_length] + '...' if len(string) > max_length else string

def process_uploaded_apks(stored_data, highlight_config, num_cores, parser_selection, sort_order):
    results = {
        'urls': [],
        'domains': [],
        'subdomains': []
    }
    
    for i, item in enumerate(stored_data):
        # Use the server-side file path directly
        apk_path = item['server_path']
        features = extract_apk_features(apk_path, parser_selection)
        
        version = item['filename'] if sort_order == 'ui' else item['version_code']
        ui_index = i
        
        for data_type in ['urls', 'domains', 'subdomains']:
            results[data_type].extend([
                {'Data': feature, 'version': version, 'ui_order': ui_index}
                for feature in features[data_type]
            ])
    
    # Generate plots for each data type
    plot_results = {}
    for data_type in ['urls', 'domains', 'subdomains']:
        if results[data_type]:
            plot_result = plot_data(results[data_type], "User Uploaded APKs", highlight_config, data_type, sort_order)
            plot_results[data_type] = plot_result
        else:
            plot_results[data_type] = None
    
    return plot_results

def save_uploaded_file(item, temp_dir):
    content_type, content_string = item['content'].split(',')
    decoded = base64.b64decode(content_string)
    file_path = os.path.join(temp_dir, item['filename'])
    with open(file_path, 'wb') as f:
        f.write(decoded)
    return file_path

