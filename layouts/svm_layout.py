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
                html.H4("Comparative Analysis of APKs", className="mb-3"),
                dbc.Label("API Key"),
                dbc.Input(id="api-key", type="text", value=""),
                dbc.Label("Package Names for Sample 1 (comma-separated)"),
                dbc.Input(id="package-names-1", type="text", value=""),
                dbc.Label("Date Range for Sample 1"),
                dcc.DatePickerRange(
                    id='date-range-1',
                    start_date="2020-01-01",
                    end_date="2022-12-31",
                    display_format='YYYY-MM-DD'
                ),
                dbc.Label("Desired Versions for Sample 1"),
                dbc.Input(id="desired-versions-1", type="number", value=1),
                dbc.Label("Package Names for Sample 2 (comma-separated)"),
                dbc.Input(id="package-names-2", type="text", value=""),
                dbc.Label("Date Range for Sample 2"),
                dcc.DatePickerRange(
                    id='date-range-2',
                    start_date="2022-01-01",
                    end_date="2024-12-31",
                    display_format='YYYY-MM-DD'
                ),
                dbc.Label("Desired Versions for Sample 2"),
                dbc.Input(id="desired-versions-2", type="number", value=1),
                dbc.Button("Start Analysis", id="start-analysis", color="primary", size="md", className="mb-3", style={'width': '55%'}),
                html.H5("Powered by DIGISILK & AndroZoo"),
            ])
        ], width=3),
        dbc.Col([
            html.H4("Results"),
            dcc.Loading(id="loading", children=[html.Div(id="svm-output-container")], type="default"),
            dcc.Interval(id='interval-component', interval=1000, n_intervals=0),
            dcc.Store(id='svm-progress-store'),
            html.Div(id='svm-progress')
        ], width=8)
    ])
], fluid=True)
