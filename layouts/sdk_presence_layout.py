from dash import dcc, html
import dash_bootstrap_components as dbc
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
                html.H4("SDK Presence Analysis", className="mb-3"),
                dbc.Label("AndroZoo API Key"),
                dbc.Input(id="sdk-api-key", type="text", value=""),
                dbc.Label("Start Date"),
                dbc.Input(id="sdk-start-date", type="date", value="2016-01-01"),
                dbc.Label("End Date"),
                dbc.Input(id="sdk-end-date", type="date", value=datetime.now().strftime("%Y-%m-%d")),
                dbc.Label("Package Name"),
                dbc.Input(id="sdk-package-name", type="text", placeholder="Enter package name", value=""),
                dbc.Label("Samples per Year"),
                dbc.Input(id="sdk-samples-per-year", type="number", value=1),
                dbc.Label("Highlight Configuration"),
                html.Div([
                    dbc.Input(id="sdk-highlight-pattern", type="text", placeholder="Enter regex pattern", className="mb-2"),
                    dbc.Input(id="sdk-highlight-color", type="text", placeholder="Enter color (e.g., #FF0000)", className="mb-2"),
                    dbc.Button("Add Highlight", id="sdk-add-highlight", color="secondary", size="sm", className="mb-2"),
                ]),
                html.Div(id="sdk-highlight-list", children=[]),
                dbc.Button("Submit", id="sdk-submit-button", color="primary", size="md", className="mt-3", style={'width': '100%'}),
                html.Div(id="sdk-error-message", className="text-danger"),
            ])
        ], width=3),
        dbc.Col([
            html.H4("Results"),
            dcc.Loading(
                id="sdk-loading",
                type="default",
                children=[
                    html.Div(id="sdk-plot-output"),
                    html.Div(id="sdk-info-output", className="mt-4")
                ]
            ),
        ], width=9)
    ]),
    dcc.Store(id='sdk-highlight-config-store'),
], fluid=True)
