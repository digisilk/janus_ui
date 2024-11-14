import base64
import os
import zipfile
import tempfile
from dash import dcc, html
from dash.dependencies import Input, Output, State
from app import app
from utils.dex_parser import DEXParser

def parse_contents(contents, filename):
    if isinstance(contents, list):
        contents = contents[0]
    if isinstance(filename, list):
        filename = filename[0]

    content_type, content_string = contents.split(',')
    decoded = base64.b64decode(content_string)
    temp_dir = tempfile.mkdtemp()

    file_path = os.path.join(temp_dir, filename)
    with open(file_path, 'wb') as f:
        f.write(decoded)

    # Extract all DEX files from the APK
    dex_files = []
    with zipfile.ZipFile(file_path, 'r') as zip_ref:
        for file in zip_ref.namelist():
            if file.startswith('classes') and file.endswith('.dex'):
                zip_ref.extract(file, temp_dir)
                dex_files.append(os.path.join(temp_dir, file))

    # Parse all DEX files
    all_strings = []
    for dex_file_path in dex_files:
        parser = DEXParser(dex_file_path)
        parser.parse()
        strings = parser.get_strings()
        all_strings.extend(strings)

    # Filter strings 'http' or 'https'
    strings_with_http = [s for s in all_strings if 'http:' in s or 'https:' in s or 'https?' in s]

    return strings_with_http

def highlight_matches(list1, list2, list3):
    matches_1_2 = set(list1) & set(list2) - set(list3)
    matches_2_3 = set(list2) & set(list3) - set(list1)
    matches_1_3 = set(list1) & set(list3) - set(list2)
    matches_all = set(list1) & set(list2) & set(list3)

    highlighted_list1 = [html.Span(s, style={'color': 'red'}) if s in matches_1_2 else
                         html.Span(s, style={'color': 'blue'}) if s in matches_1_3 else
                         html.Span(s, style={'color': 'green'}) if s in matches_all else s for s in list1]

    highlighted_list2 = [html.Span(s, style={'color': 'red'}) if s in matches_1_2 else
                         html.Span(s, style={'color': 'orange'}) if s in matches_2_3 else
                         html.Span(s, style={'color': 'green'}) if s in matches_all else s for s in list2]

    highlighted_list3 = [html.Span(s, style={'color': 'orange'}) if s in matches_2_3 else
                         html.Span(s, style={'color': 'blue'}) if s in matches_1_3 else
                         html.Span(s, style={'color': 'green'}) if s in matches_all else s for s in list3]

    return highlighted_list1, highlighted_list2, highlighted_list3

def align_lists(lists):
    max_length = max(len(lst) for lst in lists)
    aligned_lists = []
    for lst in lists:
        aligned_list = lst + [''] * (max_length - len(lst))
        aligned_lists.append(aligned_list)
    return aligned_lists

def create_tooltip_span(s):
    return html.Span(
        s if len(s) <= 50 else s[:50] + '...',
        title=str(s),
        style={'whiteSpace': 'nowrap', 'overflow': 'hidden', 'textOverflow': 'ellipsis', 'display': 'inline-block', 'maxWidth': '50ch'}
    )

@app.callback(
    [Output('output-data-upload-1', 'children'),
     Output('output-data-upload-2', 'children'),
     Output('output-data-upload-3', 'children')],
    [Input('upload-data-1', 'contents'),
     Input('upload-data-2', 'contents'),
     Input('upload-data-3', 'contents')],
    [State('upload-data-1', 'filename'),
     State('upload-data-2', 'filename'),
     State('upload-data-3', 'filename')]
)
def update_output(contents1, contents2, contents3, filename1, filename2, filename3):
    outputs = []
    lists = []
    filenames = [filename1, filename2, filename3]
    for contents, filename in zip([contents1, contents2, contents3], filenames):
        if contents is not None:
            lists.append(parse_contents(contents, filename))
        else:
            lists.append([])

    aligned_lists = align_lists(lists)

    if len(aligned_lists) == 3:
        highlighted_list1, highlighted_list2, highlighted_list3 = highlight_matches(aligned_lists[0], aligned_lists[1], aligned_lists[2])
        outputs.append(html.Div([
            html.H5(filenames[0]),
            html.Pre([html.Span([create_tooltip_span(s), html.Br()]) for s in highlighted_list1], style={'whiteSpace': 'pre-wrap', 'wordBreak': 'break-all'})
        ]))
        outputs.append(html.Div([
            html.H5(filenames[1]),
            html.Pre([html.Span([create_tooltip_span(s), html.Br()]) for s in highlighted_list2], style={'whiteSpace': 'pre-wrap', 'wordBreak': 'break-all'})
        ]))
        outputs.append(html.Div([
            html.H5(filenames[2]),
            html.Pre([html.Span([create_tooltip_span(s), html.Br()]) for s in highlighted_list3], style={'whiteSpace': 'pre-wrap', 'wordBreak': 'break-all'})
        ]))
    else:
        for i, (contents, filename) in enumerate(zip([contents1, contents2, contents3], filenames)):
            if contents is not None:
                outputs.append(html.Div([
                    html.H5(filename),
                    html.Pre([html.Span([create_tooltip_span(s), html.Br()]) for s in aligned_lists[i]], style={'whiteSpace': 'pre-wrap', 'wordBreak': 'break-all'})
                ]))
            else:
                outputs.append('No file uploaded yet.')

    while len(outputs) < 3:
        outputs.append(html.Div('No file uploaded yet.'))

    return outputs
