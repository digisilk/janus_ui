from dash import dcc, html
import dash_bootstrap_components as dbc
from datetime import datetime

ascii_logo = """
     ██  █████  ███    ██ ██    ██ ███████ 
     ██ ██   ██ ████   ██ ██    ██ ██      
     ██ ███████ ██ ██  ██ ██    ██ ███████ 
██   ██ ██   ██ ██  ██ ██ ██    ██      ██ 
 █████  ██   ██ ██   ████  ██████  ███████ """

def create_highlight_options(preset_configs):
    options = []
    for category, patterns in preset_configs.items():
        category_options = []
        for pattern, color in patterns.items():
            label = html.Span([
                html.Span(f"{category}: ", style={"fontWeight": "bold"}),
                html.Span(pattern, style={"color": color})
            ])
            category_options.append({"label": label, "value": f"{category}:{pattern}"})
        options.extend(category_options)
    options.append({"label": "Custom", "value": "custom"})
    return options

preset_configs = {
    "Chinese Tech Giants": {"regex": "baidu|alibaba|tencent|huawei|xiaomi|bytedance|weibo|wechat|qq|douyin|\\.cn$|\\.中国$|\\.中國$", "color": "#0000FF"},
    "U.S. Tech Giants": {"regex": "google|facebook|amazon|apple|microsoft|twitter|linkedin|instagram|snapchat", "color": "#0000FF"},
    "Russian Tech Giants": {"regex": "yandex|mail\\.ru|vk\\.com|kaspersky|sberbank|rambler|\\.ru$|\\.рф$", "color": "#0000FF"},
    
    "U.S. Cloud Services": {"regex": "aws\\.amazon|amazonwebservices|azure|microsoft\\.com|googlecloud|cloud\\.google|digitalocean|heroku|cloudflare|akamai|fastly", "color": "#0000FF"},
    "Chinese Cloud Services": {"regex": "aliyun|alicloud|tencentcloud|huaweicloud|baiduyun|qcloud", "color": "#0000FF"},
    "Russian Cloud Services": {"regex": "selectel|cloudmts|sbercloud|mail\\.ru", "color": "#0000FF"},

    "Education": {"regex": "edu|\\.edu$|university|school|college", "color": "#4B0082"},
}

layout = dbc.Container([
    dbc.Row(dbc.Col(html.Pre(ascii_logo, style={'font-family': 'monospace', 'color': 'blue'}))),
    dbc.Row(dbc.Col(html.Img(src="/assets/sponsors.png",
                             style={'height': '71px', 'display': 'inline-block', 'margin-bottom': '0px',
                                    'margin-top': '0px'}))),
    dbc.Row([
        dbc.Col([
            dbc.Form([
                html.H4("Historical Connectivity Analysis", className="mb-3"),
                dbc.Label("AndroZoo API Key"),
                dbc.Input(id="api-key", type="text", value=""),
                dbc.Label("Start Date"),
                dbc.Input(id="start-date", type="date", value="2013-01-01"),
                dbc.Label("End Date"),
                dbc.Input(id="end-date", type="date", value=datetime.now().strftime("%Y-%m-%d")),
                dbc.Label("Package Name"),
                dcc.Dropdown(
                    id="package-list-dropdown",
                    options=[],
                    value=None,
                    placeholder="Enter package name",
                    searchable=True,
                    clearable=True,
                ),
                dcc.Store(id="selected-package-store"),
                dbc.Label("Desired Number of Versions"),
                dbc.Input(id="desired-versions", type="number", value=3),
                dbc.Label("Highlight Configuration"),
                dcc.Dropdown(
                    id='highlight-dropdown',
                    options=[{'label': k, 'value': k} for k in preset_configs.keys()],
                    multi=True,
                    placeholder="Select preset highlight patterns",
                    style={'marginBottom': '10px'}
                ),
                html.Div([
                    dbc.Input(id="highlight-pattern", type="text", placeholder="Enter regex pattern", className="mb-2"),
                    dbc.Input(id="highlight-color", type="text", placeholder="Enter color (e.g., #FF0000)", className="mb-2"),
                    dbc.Button("Add Custom Highlight", id="add-highlight", color="secondary", size="sm", className="mb-2"),
                ], id="custom-highlight-inputs"),
                html.Div(id="highlight-list", style={'maxHeight': '200px', 'overflowY': 'auto'}),
                dbc.Label("Number of Cores"),
                dcc.Slider(
                    id="num-cores-slider",
                    min=1,
                    max=4,
                    step=1,
                    value=2,
                    marks={i: str(i) for i in range(1, 5)},
                ),
                dbc.Label("Parser Selection"),
                dcc.Dropdown(
                    id="parser-selection",
                    options=[
                        {"label": "DigiSilk Custom Parser", "value": "digisilk"},
                        {"label": "Androguard Parser", "value": "androguard"}
                    ],
                    value="digisilk",  # Default to DigiSilk parser
                    clearable=False
                ),
                dbc.Button("Submit", id="submit-button", color="primary", size="md", className="mt-3", style={'width': '100%'}),
                html.Div(id="error-message", className="text-danger"),
            ])
        ], width=3),
        dbc.Col([
            html.H4("Progress"),
            html.Pre(id='progress-historical-connectivity', style={'whiteSpace': 'pre-wrap', 'wordBreak': 'break-word', 'maxHeight': '300px', 'overflowY': 'scroll'}),
            dcc.Interval(id='progress-interval', interval=1000, n_intervals=0),
            html.H4("Results"),
            html.Div([  # New container for loading and results
                dcc.Loading(
                    id="loading-1",
                    type="default",
                    children=html.Div(id="loading-output")
                ),
                html.Div(id="results-historical-connectivity")
            ], style={'minHeight': '100px'})  # minimum height for loading indicator
        ], width=9)
    ]),
    dcc.Store(id='historical-connectivity-progress'),
    dcc.Store(id='highlight-config-store'),
], fluid=True)
