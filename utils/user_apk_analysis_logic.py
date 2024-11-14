# utils/apk_historical_analysis_util.py
import base64
import csv
import gc
import json
import logging
import multiprocessing as mp
import os
import re
import shutil
import struct
import time
import zipfile
from collections import defaultdict, OrderedDict
from datetime import datetime
from pathlib import Path

import pandas as pd
import requests
import tldextract
from androguard.core.bytecodes import dvm
from androguard.misc import AnalyzeAPK
from dash import dcc, html
from tqdm import tqdm

import threading

import logging
from io import StringIO
import os
import base64
import tempfile
import base64
import tempfile
import os
from multiprocessing import Pool

from .dex_parser import DEXParser
from utils.string_presence_utils import DEXParser, extract_apk_dex_files

#variable to track progress
progress = {
    'current_task': '',
    'total_tasks': 0,
    'completed_tasks': 0
}

import sqlite3
import plotly.io as pio
from dash.exceptions import PreventUpdate


logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# variable to keep track of the current process
current_process = None


def initialize_database(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS apks (
        sha256 TEXT PRIMARY KEY,
        pkg_name TEXT,
        vercode TEXT,
        vt_scan_date TEXT
    )
    ''')
    conn.commit()
    conn.close()


def process_apks(n_clicks, api_key, start_date, end_date, package_list_input, desired_versions, highlight_config, num_cores, parser_selection):
    global current_process
    current_process = threading.current_thread()

    if n_clicks is None:
        raise PreventUpdate

    package_list = [package_list_input.strip()]  # Only accept one package
    
    ui_logger.logger.info("Starting APK processing")

    start_date_str = datetime.strptime(start_date, '%Y-%m-%d').strftime('%Y-%m-%d ') + "23:59:59.999999"
    end_date_str = datetime.strptime(end_date, '%Y-%m-%d').strftime('%Y-%m-%d ') + "23:59:59.999999"

    # Validate and clean APKs
    base_dir = Path(__file__).parent.parent.absolute()
    universal_cache_dir = os.path.join(base_dir, "apk_cache")
    trash_dir = os.path.join(base_dir, "trash")
    validate_and_clean_apks(universal_cache_dir, trash_dir)
    ui_logger.logger.info("APK cache validated and cleaned")

    results = {}

    for package_name in package_list:
        ui_logger.logger.info(f"Processing package: {package_name}")

        if package_name:
            try:
                ui_logger.logger.info(f"Downloading APKs for {package_name}")
                figs = process_package(
                    package_name.strip(),
                    os.getcwd(),
                    api_key,
                    'androzoo.db',
                    start_date_str,
                    end_date_str,
                    int(desired_versions),
                    highlight_config,
                    num_cores,
                    parser_selection
                )

                # Check for cancellation after each major step
                if current_process != threading.current_thread():
                    ui_logger.logger.info("Process cancelled")
                    return None

                if figs:
                    results.update(figs)
                    ui_logger.logger.info(f"Figures generated for {package_name}")
                else:
                    ui_logger.logger.warning(f"No figures generated for package {package_name}")
            except Exception as e:
                ui_logger.logger.error(f"Error processing package {package_name}: {str(e)}")

    ui_logger.logger.info("APK processing complete")
    return results


def validate_and_clean_apks(universal_cache_dir, trash_dir):
    os.makedirs(trash_dir, exist_ok=True)
    for filename in os.listdir(universal_cache_dir):
        if filename.endswith('.apk'):
            apk_path = os.path.join(universal_cache_dir, filename)
            #todo, reimplement
            '''try:
                with zipfile.ZipFile(apk_path, 'r') as zip_ref:
                    zip_ref.testzip()
            except zipfile.BadZipFile:
                print(f"Corrupted APK detected: {apk_path}")
                trash_path = os.path.join(trash_dir, filename)
                shutil.move(apk_path, trash_path)
                print(f"Moved corrupted APK to trash: {trash_path}")'''


def download_file_with_progress(url, filename):
    response = requests.get(url, stream=True)
    total = int(response.headers.get('content-length', 0))
    with tqdm(total=total, unit='iB', unit_scale=True) as progress_bar:
        with open(filename, 'wb') as file:
            for data in response.iter_content(chunk_size=1024):
                progress_bar.update(len(data))
                file.write(data)


def check_and_print_csv(filename):
    try:
        data = pd.read_csv(filename, nrows=5)
        if data.empty:
            print("csv file is empty.")
        else:
            print("First few rows of the CSV file:")
            print(data)
    except pd.errors.EmptyDataError:
        print("csv file is empty.")
    except Exception as e:
        print(f"error reading CSV file: {e}")


def find_sha256_vercode_vtscandate(package_name, db_path, start_date, end_date):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    query = """
    SELECT sha256, vercode, vt_scan_date
    FROM apks
    WHERE pkg_name = ? AND vt_scan_date BETWEEN ? AND ?
    ORDER BY vt_scan_date
    """

    cursor.execute(query, (package_name, start_date, end_date))
    results = cursor.fetchall()

    conn.close()

    return [(sha256, vercode, vt_scan_date) for sha256, vercode, vt_scan_date in results]


def check_apk_in_cache(sha256, universal_cache_dir):
    apk_path = os.path.join(universal_cache_dir, f"{sha256}.apk")
    return os.path.exists(apk_path)


def calculate_sampling_frequency(total_versions, desired_versions):
    frequency = max(1, total_versions // desired_versions)
    return frequency


def download_apk(sha256, vercode, vtscandate, package_name, apikey, universal_cache_dir, max_retries=20,
                  retry_cycles=4):
    apk_path = os.path.join(universal_cache_dir, f"{sha256}.apk")
    if check_apk_in_cache(sha256, universal_cache_dir):
        print(f"APK {sha256} found in cache.")
        return apk_path

    os.makedirs(universal_cache_dir, exist_ok=True)
    url = f"https://androzoo.uni.lu/api/download?apikey={apikey}&sha256={sha256}"
    for cycle in range(retry_cycles):
        attempts = 0
        while attempts < max_retries:
            response = requests.get(url, stream=True)
            if response.status_code == 200:
                with open(apk_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=1024):
                        if chunk:
                            f.write(chunk)
                if os.path.getsize(apk_path) > 1000:
                    return apk_path
                else:
                    attempts += 1
            else:
                attempts += 1
            if attempts >= max_retries:
                time.sleep(200)
    return None


def download_apk_worker(sha256, vercode, vtscandate, package_name, apikey, universal_cache_dir):
    try:
        return download_apk(sha256, vercode, vtscandate, package_name, apikey, universal_cache_dir)
    except Exception as e:
        print(f"Error in downloading APK with SHA256: {sha256}. Error: {str(e)}")
        return None


def download_apks(package_names, apikey, universal_cache_dir, db_path, start_date, end_date, desired_versions):
    pool = mp.Pool(min(mp.cpu_count() - 1, mp.cpu_count()))
    download_tasks = []
    apk_log = {}
    for package_name in package_names:
        sha256_vercode_vtscandate_list = find_sha256_vercode_vtscandate(package_name, db_path, start_date, end_date)
        if not sha256_vercode_vtscandate_list:
            continue
        latest_app = sha256_vercode_vtscandate_list[-1]
        download_tasks.append((*latest_app, package_name, apikey, universal_cache_dir))
        sampling_frequency = calculate_sampling_frequency(len(sha256_vercode_vtscandate_list) - 1, desired_versions - 1)
        sampled_apps = sha256_vercode_vtscandate_list[:-1][::sampling_frequency]
        for sha256, vercode, vtscandate in sampled_apps:
            download_tasks.append((sha256, vercode, vtscandate, package_name, apikey, universal_cache_dir))

        apk_log[package_name] = [
            {"sha256": sha256, "vercode": vercode, "vtscandate": vtscandate}
            for sha256, vercode, vtscandate in [latest_app] + sampled_apps
        ]

    results = pool.starmap(download_apk_worker, download_tasks)
    pool.close()
    pool.join()

    # Save the APK log as JSON
    with open(os.path.join(universal_cache_dir, 'apk_log.json'), 'w') as f:
        json.dump(apk_log, f, indent=2)

    return [result for result in results if result is not None]


def extract_apk_dex_files(apk_path):
    dex_files = []
    with zipfile.ZipFile(apk_path, 'r') as z:
        for filename in z.namelist():
            if filename.endswith('.dex'):
                dex_data = z.read(filename)
                dex_files.append(dex_data)
    return dex_files


def sanitize_string(input_string):
    return input_string.replace('\u0000', '')


def extract_apk_features(file_path, parser_selection):
    data = {'urls': [], 'domains': set(), 'subdomains': set()}
    try:
        if parser_selection == 'custom_dex':
            with zipfile.ZipFile(file_path, 'r') as zip_ref:
                dex_files = [f for f in zip_ref.namelist() if f.endswith('.dex')]
                for dex_file in dex_files:
                    with zip_ref.open(dex_file) as dex:
                        parser = DEXParser(dex.read())
                        parser.parse()
                        for string in parser.strings:
                            urls = re.findall(r'https?://\S+', string)
                            data['urls'].extend(urls)
        else:  # Androguard parser
            logging.info(f"Using Androguard parser for {file_path}")
            a, d, dx = AnalyzeAPK(file_path)
            logging.info(f"Androguard analysis complete for {file_path}")
            logging.info(f"APK Package name: {a.get_package()}")
            logging.info(f"APK Version name: {a.get_androidversion_name()}")
            logging.info(f"APK Version code: {a.get_androidversion_code()}")
            
            for dex in a.get_all_dex():
                dv = dvm.DalvikVMFormat(dex)
                for string in dv.get_strings():
                    sanitized_string = sanitize_string(string)
                    urls = re.findall(r'https?://\S+', sanitized_string)
                    data['urls'].extend(urls)

        # Process URLs to extract domains and subdomains
        for url in data['urls']:
            parsed_url = tldextract.extract(url)
            subdomain = '.'.join(filter(None, [parsed_url.subdomain, parsed_url.domain, parsed_url.suffix]))
            domain = '.'.join(filter(None, [parsed_url.domain, parsed_url.suffix]))
            data['subdomains'].add(subdomain)
            data['domains'].add(domain)

        logging.info(f"Extracted features from {file_path}")
        return data
    except Exception as e:
        logging.error(f'Error while extracting features from {file_path}: {str(e)}')
        return data


def process_package(package_name, base_directory, apikey, db_path, start_date, end_date, desired_versions, highlight_config, num_cores, parser_selection):
    initialize_database(db_path)
    universal_cache_dir = os.path.join(base_directory, "apk_cache")
    os.makedirs(universal_cache_dir, exist_ok=True)

    downloaded_apks = download_apks([package_name], apikey, universal_cache_dir, db_path, start_date, end_date, desired_versions)

    if should_cancel():
        return None

    if downloaded_apks:
        all_data = process_package_apks(universal_cache_dir, package_name, num_cores, parser_selection)

        if should_cancel():
            return None

        figs = {}
        for data_type in ['urls', 'subdomains', 'domains']:
            # Convert highlight_config to the format for plot_data
            formatted_highlight_config = {item['regex']: item['color'] for item in highlight_config}
            fig = plot_data(all_data, package_name, formatted_highlight_config, data_type)
            figs[data_type] = fig

            if should_cancel():
                return None

        return figs
    else:
        return None


def process_package_apks(universal_cache_dir, package_name, num_cores, parser_selection):
    with open(os.path.join(universal_cache_dir, 'apk_log.json'), 'r') as f:
        apk_log = json.load(f)

    relevant_apks = apk_log.get(package_name, [])

    if not relevant_apks:
        print(f"No relevant APKs found for {package_name}")
        return []

    pool = mp.Pool(num_cores, maxtasksperchild=4)
    results = pool.starmap(process_file, [
        (apk['sha256'], universal_cache_dir, apk['vercode'], apk['vtscandate'], parser_selection) for apk in relevant_apks])
    pool.close()
    pool.join()

    all_data = []
    for result in results:
        if result is not None:
            all_data.extend(result)

    if not all_data:
        print(f"No data extracted from APKs for {package_name}")

    del results
    gc.collect()
    return all_data


def process_file(sha256, folder_path, vercode, vtscandate, parser_selection):
    file_path = os.path.join(folder_path, f"{sha256}.apk")
    if not os.path.exists(file_path):
        logging.warning(f"Warning: APK file not found for SHA256 {sha256}")
        return None

    try:
        logging.info(f"Processing file {sha256}.apk with {parser_selection} parser")
        urls = extract_apk_features(file_path, parser_selection)
        
        processed_data = []
        for url in urls:
            parsed_url = tldextract.extract(url)
            subdomain = '.'.join(filter(None, [parsed_url.subdomain, parsed_url.domain, parsed_url.suffix]))
            domain = '.'.join(filter(None, [parsed_url.domain, parsed_url.suffix]))
            processed_data.append({
                'version': vercode,
                'vtscandate': vtscandate,
                'urls': url,
                'subdomains': subdomain,
                'domains': domain
            })
        logging.info(f"Processed {len(processed_data)} items for {sha256}.apk")
        return processed_data
    except Exception as e:
        logging.error(f"Error processing file {sha256}.apk: {str(e)}")
        return None


def generate_download_link(fig, package_name, data_type):
    # Generate a unique filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{package_name}_{data_type}_{timestamp}.html"
    
    # Convert the figure to HTML
    plot_html = pio.to_html(fig, full_html=False)
    
    # Encode the HTML content
    encoded = base64.b64encode(plot_html.encode()).decode()
    
    # Create the download link
    href = f"data:text/html;base64,{encoded}"
    
    return html.Div([
        html.A(
            'Download Figure',
            id=f'download-link-{data_type}',
            download=filename,
            href=href,
            target="_blank",
            className="btn btn-primary mt-2"
        )
    ])


def find_folders_for_package(base_directory, package_name_pattern):
    matching_folders = []
    for folder_name in os.listdir(base_directory):
        if package_name_pattern in folder_name and os.path.isdir(os.path.join(base_directory, folder_name)):
            matching_folders.append(os.path.join(base_directory, folder_name))
    return matching_folders


def get_most_recent_folder(matching_folders):
    if not matching_folders:
        return None
    return max(matching_folders, key=os.path.getmtime)

import plotly.graph_objects as go
import pandas as pd
import re
import plotly.io as pio
from datetime import datetime
import base64
import gc

def truncate_string(s, max_length=100):
    return s if len(s) <= max_length else s[:max_length] + "..."

def plot_data(all_data, package_name, highlight_config, data_type, sort_order):
    print(f"Preparing data for plotting {data_type}...")
    
    MAX_STRING_LENGTH = 100

    if not all_data:
        print(f"No data available for {package_name}")
        return None

    df = pd.DataFrame(all_data)
    
    if 'Data' not in df.columns:
        print(f"Error: 'Data' not found in the data. Available columns: {df.columns.tolist()}")
        return None

    df['Data'] = df['Data'].apply(lambda x: truncate_string(x, MAX_STRING_LENGTH))
    df['Count'] = 1
    df = df.groupby(['version', 'Data', 'ui_order']).sum().reset_index()

    if df.empty:
        print(f"No data to plot for {data_type}.")
        return None

    # Sort versions based on sort_order
    if sort_order == 'ui':
        sorted_versions = df.sort_values('ui_order')['version'].unique()
    else:  # 'vercode'
        sorted_versions = sorted(df['version'].unique(), key=lambda x: int(x) if x.isdigit() else x)

    # pivot the count data
    df_count_pivot = df.pivot_table(index='Data', columns='version', values='Count', aggfunc='sum', fill_value=0)
    df_count_pivot = df_count_pivot[sorted_versions]

    # create a new list for x-axis labels
    sorted_versions_with_dates = sorted_versions

    #evolutionary sorting logic
    # 1: count appearances of each domain across all versions
    data_appearances = {}
    for version in sorted_versions:
        for item in df[df['version'] == version]['Data'].unique():
            data_appearances[item] = data_appearances.get(item, 0) + 1

    # 2: sort domains within each version based on appearances and re-addition
    version_sorted_data = {}
    for version in sorted_versions:
        current_version_data = df[df['version'] == version]['Data'].unique().tolist()
        # sort domains within the current version based on their total appearances (descending)
        sorted_data = sorted(current_version_data, key=lambda x: (-data_appearances[x], x))
        version_sorted_data[version] = sorted_data

    # 3: build the master list of domains, maintaining the staircase effect
    master_data_list = []
    seen_data = set()

    for version in sorted_versions:
        current_version_sorted_data = version_sorted_data[version]
        new_or_readded_data = [item for item in current_version_sorted_data if item not in seen_data]
        master_data_list.extend(new_or_readded_data)
        seen_data.update(new_or_readded_data)

    sorted_data = master_data_list

    #create the hover text matrix
    hover_text = []
    for item in sorted_data:
        hover_text_row = []
        for version in sorted_versions:
            count = df_count_pivot.at[item, version] if version in df_count_pivot.columns else 0
            hover_text_data = f"Feature: {truncate_string(item, MAX_STRING_LENGTH)}<br>Version: {version}<br>Count: {count}"
            hover_text_row.append(hover_text_data)
        hover_text.append(hover_text_row)

    # Create a list of dictionaries containing feature info
    feature_info = []
    for item in sorted_data:
        info = {
            'feature': truncate_string(item, MAX_STRING_LENGTH),
            'alienvault_link': f"https://otx.alienvault.com/indicator/domain/{item}",
            'whois_link': f"https://www.whois.com/whois/{item}"
        }
        feature_info.append(info)

    # Set a threshold for the maximum number of features to display
    MAX_FEATURES_TO_DISPLAY = 250

    if len(sorted_data) > MAX_FEATURES_TO_DISPLAY:
        # Create the figure without displaying it
        fig = go.Figure(data=go.Heatmap(
            showscale=False,
            z=df_count_pivot.reindex(sorted_data).values,
            x=sorted_versions,
            y=sorted_data,
            text=hover_text,
            hoverinfo='text',
            colorscale=[[0, 'white'], [0.01, 'grey'], [0.4, '#505050'], [1, 'black']],
            zmin=0,
            zmax=df_count_pivot.max().max(),
            xgap=1,
            ygap=1
        ))

        # Update layout
        fig.update_layout(
            title=f"{data_type.capitalize()} Presence and Frequency Across Versions, {package_name}",
            xaxis=dict(tickmode='array', tickvals=sorted_versions, ticktext=sorted_versions_with_dates),
            yaxis=dict(autorange="reversed")
        )

        # Create shapes for highlighting
        shapes = []
        if highlight_config:  # Add this check to handle cases when no highlight config is selected
            for data_idx, item in enumerate(sorted_data):
                for version_idx, version in enumerate(sorted_versions):
                    count = df_count_pivot.loc[item, version]
                    if count > 0:
                        matched_color = None
                        for highlight in reversed(highlight_config):
                            if re.search(highlight['regex'], item, re.IGNORECASE):
                                matched_color = highlight['color']
                                break
                        if matched_color:
                            shapes.append({
                                'type': 'rect',
                                'x0': version_idx - 0.5,
                                'y0': data_idx - 0.5,
                                'x1': version_idx + 0.5,
                                'y1': data_idx + 0.5,
                                'fillcolor': matched_color,
                                'opacity': 0.3,
                                'line': {'width': 0},
                            })

        fig.update_layout(shapes=shapes)

        return {
            'figure': fig,
            'feature_info': feature_info,
            'too_large_to_display': True,
            'feature_count': len(sorted_data)
        }
    else:
        # Create heatmap
        fig = go.Figure(data=go.Heatmap(
            showscale=False,
            z=df_count_pivot.reindex(sorted_data).values,
            x=sorted_versions,
            y=sorted_data,
            text=hover_text,
            hoverinfo='text',
            colorscale=[[0, 'white'], [0.01, 'grey'], [0.4, '#505050'], [1, 'black']],
            zmin=0,
            zmax=df_count_pivot.max().max(),
            xgap=1,
            ygap=1
        ))

        # Create shapes for highlighting
        shapes = []
        if highlight_config:  # Add this check to handle cases when no highlight config is selected
            for data_idx, item in enumerate(sorted_data):
                for version_idx, version in enumerate(sorted_versions):
                    count = df_count_pivot.loc[item, version]
                    if count > 0:
                        matched_color = None
                        for highlight in reversed(highlight_config):
                            if re.search(highlight['regex'], item, re.IGNORECASE):
                                matched_color = highlight['color']
                                break
                        if matched_color:
                            shapes.append({
                                'type': 'rect',
                                'x0': version_idx - 0.5,
                                'y0': data_idx - 0.5,
                                'x1': version_idx + 0.5,
                                'y1': data_idx + 0.5,
                                'fillcolor': matched_color,
                                'opacity': 0.3,
                                'line': {'width': 0},
                            })

        # update layout
        fig.update_layout(
            shapes=shapes,
            title=f"{data_type.capitalize()} Presence and Frequency Across Versions, {package_name}",
            xaxis=dict(tickmode='array', tickvals=list(range(len(sorted_versions))), ticktext=sorted_versions_with_dates),
            yaxis=dict(autorange="reversed")
        )

        return {
            'figure': fig,
            'feature_info': feature_info,
            'too_large_to_display': False,
            'feature_count': len(sorted_data)
        }

def create_pie_charts(version_vtscandate_subdomains_counts):
    pie_chart_figs = []
    df = pd.DataFrame(version_vtscandate_subdomains_counts, columns=['Version', 'vt_scan_date', 'Subdomain', 'Count'])
    df_grouped = df.groupby(['Version', 'Subdomain']).sum().reset_index()

    # Sorting versions in ascending order based on integer conversion if possible
    versions = sorted(df['Version'].unique(), key=lambda x: int(x) if x.isdigit() else x)

    for version in versions:
        df_version = df_grouped[df_grouped['Version'] == version]
        fig = go.Figure(data=[go.Pie(labels=df_version['Subdomain'], values=df_version['Count'],
                                     textinfo='none', hoverinfo='label+percent')])
        fig.update_layout(
            title=f"Subdomain Share for Version {version}",
            autosize=False,
            width=600,
            height=400,
        )
        pie_chart_figs.append(fig)

    return pie_chart_figs

import random
import math
import plotly.graph_objects as go

def plot_locations(locations):
    fig = go.Figure()

    # Group by (latitude, longitude) for offsett overlapping markers
    location_dict = {}
    for loc in locations:
        if loc:
            key = (loc['latitude'], loc['longitude'])
            if key not in location_dict:
                location_dict[key] = []
            location_dict[key].append(loc)

    for coords, locs in location_dict.items():
        if len(locs) > 1:
            angle = 0
            step = 360 / len(locs)
            radius = random.uniform(0, 5)  # Degrees latitude/longitude for offset
            for loc in locs:
                offset_lat = loc['latitude'] + radius * math.cos(math.radians(angle))
                offset_lon = loc['longitude'] + radius * math.sin(math.radians(angle))
                fig.add_trace(go.Scattergeo(
                    lon=[offset_lon],
                    lat=[offset_lat],
                    text=f"{loc['url']}<br>{loc['city']}, {loc['country']}",
                    mode='markers',
                    marker=dict(size=8, color='blue', symbol='circle'),
                    hoverinfo='text'
                ))
                angle += step
        else:
            loc = locs[0]
            fig.add_trace(go.Scattergeo(
                lon=[loc['longitude']],
                lat=[loc['latitude']],
                text=f"{loc['url']}<br>{loc['city']}, {loc['country']}",
                mode='markers',
                marker=dict(size=8, color='blue', symbol='circle'),
                hoverinfo='text'
            ))

    fig.update_layout(
        title='Geolocations of IPs of each endpoint',
        geo=dict(
            scope='world',
            projection_type='natural earth',
            showland=True,
            landcolor='rgb(243, 243, 243)',
            countrycolor='rgb(204, 204, 204)',
        )
    )
    return fig


class UILogger:
    def __init__(self):
        self.log_capture_string = StringIO()
        self.ch = logging.StreamHandler(self.log_capture_string)
        self.ch.setLevel(logging.INFO)
        self.formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        self.ch.setFormatter(self.formatter)

        self.logger = logging.getLogger('UILogger')
        self.logger.setLevel(logging.INFO)
        self.logger.addHandler(self.ch)

    def get_logs(self):
        return self.log_capture_string.getvalue()

ui_logger = UILogger()

# Add this function to check if a process should be cancelled
def should_cancel():
    return current_process != threading.current_thread()





def process_uploaded_apks(stored_data, highlight_config, num_cores, parser_selection, sort_order):
    results = {
        'urls': [],
        'domains': [],
        'subdomains': []
    }
    
    for i, item in enumerate(stored_data):
        # Use the server-side file path directly
        apk_path = item['server_path']
        features = extract_apk_features(apk_path, parser_selection)
        
        version = item['filename'] if sort_order == 'ui' else item['version_code']
        ui_index = i
        
        for data_type in ['urls', 'domains', 'subdomains']:
            results[data_type].extend([
                {'Data': feature, 'version': version, 'ui_order': ui_index}
                for feature in features[data_type]
            ])
    
    # Generate plots for each data type
    plot_results = {}
    for data_type in ['urls', 'domains', 'subdomains']:
        if results[data_type]:
            plot_result = plot_data(results[data_type], "User Uploaded APKs", highlight_config, data_type, sort_order)
            plot_results[data_type] = plot_result
        else:
            plot_results[data_type] = None
    
    return plot_results

def save_uploaded_files(stored_data, temp_dir):
    apk_paths = []
    for item in stored_data:
        content_type, content_string = item['content'].split(',')
        decoded = base64.b64decode(content_string)
        file_path = os.path.join(temp_dir, item['filename'])
        with open(file_path, 'wb') as f:
            f.write(decoded)
        apk_paths.append(file_path)
    return apk_paths


def save_uploaded_file_to_server(content, filename):
    # Create a directory to store uploaded APKs if it doesn't exist
    upload_dir = os.path.join(tempfile.gettempdir(), 'uploaded_apks')
    os.makedirs(upload_dir, exist_ok=True)

    # Generate a unique filename to avoid conflicts
    unique_filename = f"{os.urandom(8).hex()}_{filename}"
    file_path = os.path.join(upload_dir, unique_filename)

    # Save the file
    content_type, content_string = content.split(',')
    decoded = base64.b64decode(content_string)
    with open(file_path, 'wb') as f:
        f.write(decoded)

    return file_path















