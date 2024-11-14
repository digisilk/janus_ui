from dash import dcc, html
import dash_bootstrap_components as dbc

layout = dbc.Container([
    dbc.Row([
        dbc.Col([
            dcc.Upload(
                id='upload-data-1',
                children=html.Div([
                    'Drag and Drop or ',
                    html.A('Select File 1')
                ]),
                style={
                    'width': '100%',
                    'height': '60px',
                    'lineHeight': '60px',
                    'borderWidth': '1px',
                    'borderStyle': 'dashed',
                    'borderRadius': '5px',
                    'textAlign': 'center',
                    'margin': '10px'
                },
                multiple=True
            ),
            html.Div(id='output-data-upload-1')
        ], width=4),
        dbc.Col([
            dcc.Upload(
                id='upload-data-2',
                children=html.Div([
                    'Drag and Drop or ',
                    html.A('Select File 2')
                ]),
                style={
                    'width': '100%',
                    'height': '60px',
                    'lineHeight': '60px',
                    'borderWidth': '1px',
                    'borderStyle': 'dashed',
                    'borderRadius': '5px',
                    'textAlign': 'center',
                    'margin': '10px'
                },
                multiple=True
            ),
            html.Div(id='output-data-upload-2')
        ], width=4),
        dbc.Col([
            dcc.Upload(
                id='upload-data-3',
                children=html.Div([
                    'Drag and Drop or ',
                    html.A('Select File 3')
                ]),
                style={
                    'width': '100%',
                    'height': '60px',
                    'lineHeight': '60px',
                    'borderWidth': '1px',
                    'borderStyle': 'dashed',
                    'borderRadius': '5px',
                    'textAlign': 'center',
                    'margin': '10px'
                },
                multiple=True
            ),
            html.Div(id='output-data-upload-3')
        ], width=4),
    ]),
])