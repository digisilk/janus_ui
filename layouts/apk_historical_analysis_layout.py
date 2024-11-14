from dash import dcc, html
import dash_bootstrap_components as dbc
import dash_daq as daq
from datetime import datetime

ascii_logo = """
     ██  █████  ███    ██ ██    ██ ███████ 
     ██ ██   ██ ████   ██ ██    ██ ██      
     ██ ███████ ██ ██  ██ ██    ██ ███████ 
██   ██ ██   ██ ██  ██ ██ ██    ██      ██ 
 █████  ██   ██ ██   ████  ██████  ███████ """

layout = dbc.Container([
    dbc.Row(dbc.Col(html.Pre(ascii_logo, style={'font-family': 'monospace', 'color': 'blue'}))),
    dbc.Row(dbc.Col(html.Img(src="/assets/sponsors.png",
                             style={'height': '71px', 'display': 'inline-block', 'margin-bottom': '0px',
                                    'margin-top': '0px'}))),
    dbc.Row([
        dbc.Col([
            dbc.Form([
                html.H4("See APK endpoints evolution over time", className="mb-3"),
                dbc.Label("AndroZoo API Key"),
                dbc.Input(id="api-key", type="text", value=""),
                dbc.Label("Start Date"),
                dbc.Input(id="start-date", type="date", value="2013-01-01"),
                dbc.Label("End Date"),
                dbc.Input(id="end-date", type="date", value=datetime.now().strftime("%Y-%m-%d")),
                dbc.Label("Package Name"),
                dbc.Input(id="package-list", type="text", placeholder="Enter package name", value=""),
                dbc.Label("Desired Number of Versions"),
                dbc.Input(id="desired-versions", type="number", value=10),
                dbc.Label("Highlight Configuration"),
                dbc.Textarea(id="highlight-config", placeholder="Enter highlight configuration as JSON", value='{"entity1": "#1DB954", "entity2": "#4267B2"}', rows=3),
                dbc.Label("Data Type"),
                dcc.Dropdown(id="data-type", options=[
                    {'label': 'Subdomains', 'value': 'subdomains'},
                    {'label': 'Domains', 'value': 'domains'},
                    {'label': 'Permissions', 'value': 'permissions'},
                    {'label': 'URLs', 'value': 'urls'},
                    {'label': 'Activities', 'value': 'activities'},
                    {'label': 'Services', 'value': 'services'},
                    {'label': 'Providers', 'value': 'providers'},
                    {'label': 'Receivers', 'value': 'receivers'},
                    {'label': 'Java Classes', 'value': 'java_classes'}
                ], multi=True, value=['subdomains', 'permissions']),
                dbc.Label("Use Cache JSON"),
                dcc.Dropdown(id="use-cache-json", options=[
                    {'label': "True", 'value': "true"},
                    {'label': "False", 'value': "false"}
                ], value=True),
                dbc.Label("Core Count"),
                daq.Slider(id="core-count", min=1, max=6, value=3, step=1, className="mb-3"),
                dbc.Button("Submit", id="submit-button", color="primary", size="md", className="mb-3", style={'width': '55%'}),
                dbc.Button("Clear Cache", id="clear-cache-button", color="secondary", size="md", className="mb-3", style={'width': '55%'}),
                html.Div(id="clear-cache-output"),
                html.H5("Powered by DIGISILK & AndroZoo"),
            ])
        ], width=3),
        dbc.Col([
            html.H4("Progress"),
            dcc.Interval(id='interval-component-apk-historical', interval=1000, n_intervals=0),
            html.Div(id='progress-apk-historical'),
        ], width=8)
    ]),
    dbc.Row([
        dbc.Col([
            html.H4("Results"),
            dcc.Loading(id="loading", children=[html.Div(id="results")], type="default"),
        ], width=12)
    ]),
], fluid=True)
