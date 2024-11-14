from dash import dcc, html
import dash_bootstrap_components as dbc
from datetime import datetime
from utils.string_presence_utils import DEFAULT_STRING_PATTERNS

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
                html.H4("String Pattern Presence Analysis", className="mb-3"),
                dbc.Label("AndroZoo API Key"),
                dbc.Input(id="string-api-key", type="text", value=""),
                dbc.Label("Start Date"),
                dbc.Input(id="string-start-date", type="date", value="2016-01-01"),
                dbc.Label("End Date"),
                dbc.Input(id="string-end-date", type="date", value=datetime.now().strftime("%Y-%m-%d")),
                dbc.Label("Package Name"),
                dbc.Input(id="string-package-name", type="text", placeholder="Enter package name", value=""),
                dbc.Label("Samples per Year"),
                dbc.Input(id="string-samples-per-year", type="number", value=1),
                dbc.Label("Highlight Configuration"),
                html.Div([
                    dbc.Input(id="string-highlight-pattern", type="text", placeholder="Enter regex pattern", className="mb-2"),
                    dbc.Input(id="string-highlight-color", type="text", placeholder="Enter color (e.g., #FF0000)", className="mb-2"),
                    dbc.Button("Add Highlight", id="string-add-highlight", color="secondary", size="sm", className="mb-2"),
                ]),
                html.Div(id="string-highlight-list", children=[]),
                dbc.Label("Custom String Patterns"),
                dbc.Select(
                    id="string-pattern-default",
                    options=[{"label": k, "value": k} for k in DEFAULT_STRING_PATTERNS.keys()],
                    placeholder="Select a default pattern",
                ),
                html.Div([
                    dbc.Input(id="string-pattern-name", type="text", placeholder="Enter pattern name", className="mb-2"),
                    dbc.Input(id="string-pattern-regex", type="text", placeholder="Enter regex pattern", className="mb-2"),
                    dbc.Button("Add Pattern", id="string-add-pattern", color="secondary", size="sm", className="mb-2"),
                ]),
                html.Div(id="string-pattern-list", children=[]),
                dbc.Button("Submit", id="string-submit-button", color="primary", size="md", className="mt-3", style={'width': '100%'}),
                html.Div(id="string-error-message", className="text-danger"),
            ])
        ], width=3),
        dbc.Col([
            html.H4("Results"),
            dcc.Loading(
                id="string-loading",
                type="default",
                children=[
                    html.Div(id="string-plot-output"),
                    html.Div(id="string-info-output", className="mt-4")
                ]
            ),
        ], width=9)
    ]),
    dcc.Store(id='string-highlight-config-store'),
    dcc.Store(id='string-pattern-store'),
], fluid=True)
