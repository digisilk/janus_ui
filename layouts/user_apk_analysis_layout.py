from dash import dcc, html
import dash_bootstrap_components as dbc
import multiprocessing as mp

ascii_logo = """
     ██  █████  ███    ██ ██    ██ ███████ 
     ██ ██   ██ ████   ██ ██    ██ ██      
     ██ ███████ ██ ██  ██ ██    ██ ███████ 
██   ██ ██   ██ ██  ██ ██ ██    ██      ██ 
 █████  ██   ██ ██   ████  ██████  ███████ """

def create_highlight_options(preset_configs):
    options = []
    for category, config in preset_configs.items():
        options.append({"label": category, "value": category})
    options.append({"label": "Custom", "value": "custom"})
    return options


preset_configs = {
    "Chinese Tech Giants": {
        "regex": "baidu|alibaba|tencent|huawei|xiaomi|bytedance|weibo|wechat|qq|douyin|\\.cn$|\\.中国$|\\.中國$",
        "color": "#0000FF"},
    "U.S. Tech Giants": {"regex": "google|facebook|amazon|apple|microsoft|twitter|linkedin|instagram|snapchat",
                         "color": "#0000FF"},
    "Russian Tech Giants": {"regex": "yandex|mail\\.ru|vk\\.com|kaspersky|sberbank|rambler|\\.ru$|\\.рф$",
                            "color": "#0000FF"},

    "U.S. Cloud Services": {
        "regex": "aws\\.amazon|amazonwebservices|azure|microsoft\\.com|googlecloud|cloud\\.google|digitalocean|heroku|cloudflare|akamai|fastly",
        "color": "#0000FF"},
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
                html.H4("User APK Analysis", className="mb-3"),
                dcc.Upload(
                    id='user-apk-upload',
                    children=html.Div([
                        'Drag and Drop or ',
                        html.A('Select APK Files')
                    ]),
                    style={
                        'width': '100%',
                        'height': '60px',
                        'lineHeight': '60px',
                        'borderWidth': '1px',
                        'borderStyle': 'dashed',
                        'borderRadius': '5px',
                        'textAlign': 'center',
                        'margin': '10px 0'
                    },
                    multiple=True
                ),
                html.Div(id='user-apk-upload-list', style={'marginTop': '10px', 'marginBottom': '10px'}),
                
                # Highlight configuration dropdown
                html.Label("Preset Highlight Patterns"),
                dcc.Dropdown(
                    id='user-apk-highlight-dropdown',
                    options=[{'label': k, 'value': k} for k in preset_configs.keys()],
                    multi=True,
                    placeholder="Select preset highlight patterns",
                    style={'marginBottom': '10px'}
                ),
                
                # Custom highlight input section (always visible)
                html.Label("Custom Highlight Pattern"),
                dbc.Input(id="user-apk-highlight-pattern", type="text", placeholder="Enter regex pattern", className="mb-2"),
                dbc.Input(id="user-apk-highlight-color", type="text", placeholder="Enter color (e.g., #FF0000)", className="mb-2"),
                dbc.Button("Add Custom Highlight", id="user-apk-add-highlight", color="secondary", size="sm", className="mb-2"),
                
                # List of selected highlights
                html.Div(id="user-apk-highlight-list", style={'maxHeight': '200px', 'overflowY': 'auto'}),
                
                # Modify the number of cores slider
                html.Label("Number of Cores"),
                dcc.Slider(
                    id='user-apk-num-cores-slider',
                    min=1,
                    max=4,
                    step=1,
                    value=2,  # Default to 2 cores
                    marks={i: str(i) for i in range(1, 5)}
                ),
                
                # Modify the parser selection dropdown
                html.Label("Parser Selection"),
                dcc.Dropdown(
                    id='user-apk-parser-selection',
                    options=[
                        {'label': 'Custom DEX Parser', 'value': 'custom_dex'},
                        {'label': 'Androguard', 'value': 'androguard'}
                    ],
                    value='custom_dex',  # Set default to custom DEX parser
                    clearable=False
                ),
                
                # Add the sort order radio items
                html.Label("Sort Order"),
                dcc.RadioItems(
                    id='user-apk-sort-order',
                    options=[
                        {'label': 'UI Order', 'value': 'ui'},
                        {'label': 'Version Code', 'value': 'vercode'}
                    ],
                    value='vercode',
                    inline=True
                ),
                
                dbc.Button("Analyze APKs", id="user-apk-submit-button", color="primary", size="md", className="mt-3", style={'width': '100%'}),
                html.Div(id="user-apk-error-message", className="text-danger"),
            ])
        ], width=3),
        dbc.Col([
            html.H4("Progress"),
            html.Pre(id='user-apk-progress', style={'whiteSpace': 'pre-wrap', 'wordBreak': 'break-word', 'maxHeight': '200px', 'overflowY': 'scroll'}),
            dcc.Interval(id='user-apk-progress-interval', interval=1000, n_intervals=0),
            html.H4("Results"),
            html.Div([
                dcc.Loading(
                    id="user-apk-loading",
                    type="default",
                    children=html.Div(id="user-apk-loading-output")
                ),
                html.Div(id="user-apk-results")
            ], style={'minHeight': '100px'})
        ], width=9)
    ]),
    dcc.Store(id='user-apk-upload-store'),
    dcc.Store(id='user-apk-highlight-config-store'),
    dcc.Store(id='user-apk-feature-info-store'),
], fluid=True)
