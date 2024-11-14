from dash import dcc, html
import dash_bootstrap_components as dbc

layout = dbc.Container([
    dcc.Upload(
        id='upload-apk',
        children=html.Div(['Drag and Drop or ', html.A('Select an APK File')]),
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
        multiple=False
    ),
    html.Div(id='apk-upload-output')
], fluid=True)