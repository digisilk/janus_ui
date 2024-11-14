import dash
from dash import Input, Output, State, html
from app import app
from utils import svm_utils
from datetime import datetime

# Store progress
svm_progress = {'current_task': ''}

@app.callback(
    Output('svm-progress', 'children'),
    Input('interval-component', 'n_intervals')
)
def update_progress(n):
    global svm_progress
    if 'current_task' in svm_progress:
        return html.P(f"Current Task: {svm_progress['current_task']}")
    return html.P("No progress yet.")

@app.callback(
    Output('svm-output-container', 'children'),
    Output('svm-progress-store', 'data'),
    Input('start-analysis', 'n_clicks'),
    State('api-key', 'value'),
    State('package-names-1', 'value'),
    State('date-range-1', 'start_date'),
    State('date-range-1', 'end_date'),
    State('package-names-2', 'value'),
    State('date-range-2', 'start_date'),
    State('date-range-2', 'end_date'),
    State('desired-versions-1', 'value'),
    State('desired-versions-2', 'value')
)
def update_output(n_clicks, api_key, pkgs1, start_date1, end_date1, pkgs2, start_date2, end_date2, desired_versions1, desired_versions2):
    if n_clicks is None:
        return "Enter details and press 'Start Analysis' to begin.", dash.no_update
    else:
        svm_utils.set_api_key(api_key)

        global svm_progress
        svm_progress['current_task'] = "Currently searching for APKs"

        sample1 = {
            'package_names': pkgs1.split(','),
            'start_date': datetime.strptime(start_date1, "%Y-%m-%d"),
            'end_date': datetime.strptime(start_date1, "%Y-%m-%d"),
            'desired_versions': desired_versions1,
            'folder_name': 'Sample1'
        }
        sample2 = {
            'package_names': pkgs2.split(','),
            'start_date': datetime.strptime(start_date2, "%Y-%m-%d"),
            'end_date': datetime.strptime(start_date2, "%Y-%m-%d"),
            'desired_versions': desired_versions2,
            'folder_name': 'Sample2'
        }

        for sample in [sample1, sample2]:
            for pkg in sample['package_names']:
                svm_progress['current_task'] = f"Currently downloading {pkg}"
                svm_utils.download_apks_for_config([pkg], sample['start_date'], sample['end_date'],
                                                   sample['desired_versions'], sample['folder_name'])

        folder_paths = {
            'downloaded_apks/Sample1': 'Sample1',
            'downloaded_apks/Sample2': 'Sample2'
        }
        features_list, labels_list = svm_utils.extract_features_and_labels(folder_paths, 'features_labels.pkl',
                                                                           [svm_utils.extract_full_urls_from_apk,
                                                                            svm_utils.extract_permissions])
        df = svm_utils.prepare_dataframe(features_list, labels_list)
        sorted_features = svm_utils.perform_svm_analysis(df)
        svm_progress['current_task'] = f"Completed"
        return html.Div([
            html.H3("SVM Analysis Results"),
            html.Ul([html.Li(f"{feature}: {importance}") for feature, importance in sorted_features])
        ]), svm_progress
