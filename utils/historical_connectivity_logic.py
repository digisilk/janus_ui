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
from collections import defaultdict
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

from .dex_parser import DEXParser
from utils.string_presence_utils import DEXParser, extract_apk_dex_files

# variable to track progress
progress = {
    'current_task': '',
    'total_tasks': 0,
    'completed_tasks': 0
}

import sqlite3
import plotly.io as pio
from dash.exceptions import PreventUpdate

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

#  track of the current process
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
            #todo, improve
            try:
                with zipfile.ZipFile(apk_path, 'r') as zip_ref:
                    zip_ref.testzip()
            except zipfile.BadZipFile:
                print(f"Corrupted APK detected: {apk_path}")
                trash_path = os.path.join(trash_dir, filename)
                shutil.move(apk_path, trash_path)
                print(f"Moved corrupted APK to trash: {trash_path}")


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


def extract_apk_features(file_path, data_type, use_cache_json, parser_selection):
    json_file_path = f"{file_path}.{data_type}.json"
    if os.path.exists(json_file_path) and use_cache_json:
        logging.info(f"Using cached data for {file_path}")
        with open(json_file_path, 'r') as json_file:
            data = json.load(json_file)
        return data
    else:
        data = []
        try:
            if parser_selection == "digisilk":
                logging.info(f"Using DigiSilk custom parser for {file_path}")
                dex_files = extract_apk_dex_files(file_path)
                for dex_data in dex_files:
                    parser = DEXParser(dex_data)
                    parser.parse()
                    for string in parser.strings:
                        sanitized_string = sanitize_string(string)
                        if 'urls' in data_type:
                            urls = re.findall(r'https?://\S+', sanitized_string)
                            data.extend(urls)
                        elif 'subdomains' in data_type or 'domains' in data_type:
                            urls = re.findall(r'https?://\S+', sanitized_string)
                            for url in urls:
                                parsed_url = tldextract.extract(url)
                                subdomain_full = '.'.join(
                                    [parsed_url.subdomain, parsed_url.domain, parsed_url.suffix]).strip('.')
                                if "%s" not in subdomain_full:
                                    if "." in subdomain_full:
                                        if 'subdomains' in data_type:
                                            data.append(subdomain_full)
                                        if 'domains' in data_type:
                                            domain = '.'.join([parsed_url.domain, parsed_url.suffix]).strip('.')
                                            if "." in domain:
                                                data.append(domain)
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
                        if 'urls' in data_type:
                            urls = re.findall(r'https?://\S+', sanitized_string)
                            data.extend(urls)
                        elif 'subdomains' in data_type or 'domains' in data_type:
                            urls = re.findall(r'https?://\S+', sanitized_string)
                            for url in urls:
                                parsed_url = tldextract.extract(url)
                                subdomain_full = '.'.join([parsed_url.subdomain, parsed_url.domain, parsed_url.suffix]).strip('.')
                                if "%s" not in subdomain_full:
                                    if "." in subdomain_full:
                                        if 'subdomains' in data_type:
                                            data.append(subdomain_full)
                                        if 'domains' in data_type:
                                            domain = '.'.join([parsed_url.domain, parsed_url.suffix]).strip('.')
                                            if "." in domain:
                                                data.append(domain)

            if any(dt in data_type for dt in ['permissions', 'services', 'activities', 'providers', 'receivers', 'libraries', 'java_classes']):
                logging.info(f"Extracting additional APK features for {file_path}")
                a, _, _ = AnalyzeAPK(file_path)

                if 'permissions' in data_type:
                    data.extend(a.get_permissions())
                if 'services' in data_type:
                    data.extend(a.get_services())
                if 'activities' in data_type:
                    data.extend(a.get_activities())
                if 'providers' in data_type:
                    data.extend(a.get_providers())
                if 'receivers' in data_type:
                    data.extend(a.get_receivers())
                if 'libraries' in data_type:
                    data.extend(a.get_libraries())
                if 'java_classes' in data_type:
                    for dex in a.get_all_dex():
                        dv = dvm.DalvikVMFormat(dex)
                        for clazz in dv.get_classes():
                            class_name = clazz.get_name()[1:-1].replace('/', '.')
                            data.append(class_name)

            logging.info(f"Extracted {len(data)} items of type {data_type} from {file_path}")

        except Exception as e:
            logging.error(f'Error while extracting {data_type} from {file_path}: {str(e)}')

        with open(json_file_path, 'w') as json_file:
            json.dump(data, json_file)
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
        urls = extract_apk_features(file_path, 'urls', True, parser_selection)
        
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
    # a unique filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{package_name}_{data_type}_{timestamp}.html"
    
    # Convert figure to HTML
    plot_html = pio.to_html(fig, full_html=False)
    
    # Encode HTML content
    encoded = base64.b64encode(plot_html.encode()).decode()
    
    # Create download link
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

def plot_data(all_data, package_name, highlight_config, data_type):
    print(f"Preparing data for plotting {data_type}...")
    
    MAX_STRING_LENGTH = 100

    if not all_data:
        print(f"No data available for {package_name}")
        return None

    df = pd.DataFrame(all_data)
    
    if data_type not in df.columns:
        print(f"Error: '{data_type}' not found in the data. Available columns: {df.columns.tolist()}")
        return None

    df = df[['version', 'vtscandate', data_type]].rename(columns={data_type: 'Data'})
    df['Data'] = df['Data'].apply(lambda x: truncate_string(x, MAX_STRING_LENGTH))
    df['Count'] = 1
    df = df.groupby(['version', 'vtscandate', 'Data']).sum().reset_index()

    if df.empty:
        print(f"No data to plot for {data_type}.")
        return None

    # convert date to datetime and format it as a string
    df['vtscandate'] = pd.to_datetime(df['vtscandate']).dt.strftime('%Y-%m-%d')
    df['version'] = df['version'].astype(str)

    # pivot the count and date data
    df_count_pivot = df.pivot_table(index='Data', columns='version', values='Count', aggfunc='sum', fill_value=0)
    df_date_pivot = df.pivot_table(index='Data', columns='version', values='vtscandate', aggfunc='first')

    sorted_versions = sorted(df_count_pivot.columns,
                             key=lambda s: [int(u) if u.isdigit() else u for u in re.split('(\d+)', s)])
    df_count_pivot = df_count_pivot[sorted_versions]
    df_date_pivot = df_date_pivot[sorted_versions]

    # create a new list for x-axis labels combining version and date
    sorted_versions_with_dates = []
    for version in sorted_versions:
        #find the earliest date for this version
        earliest_date = df[df['version'] == version]['vtscandate'].min()
        label = f"{version} ({earliest_date})"
        sorted_versions_with_dates.append(label)

    sorted_versions = sorted(df['version'].unique(),
                             key=lambda x: [int(part) if part.isdigit() else part for part in re.split('([0-9]+)', x)])

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
    #initialize a master list of domains across all versions
    master_data_list = []
    seen_data = set()

    for version in sorted_versions:
        #retrieve the sorted list of domains for the current version
        current_version_sorted_data = version_sorted_data[version]
        #filter to include only new or re-added domains not already in master_domain_list
        new_or_readded_data = [item for item in current_version_sorted_data if item not in seen_data]
        master_data_list.extend(new_or_readded_data)
        #update the seen_domains set
        seen_data.update(new_or_readded_data)

    sorted_data = master_data_list

    # Reverse the highlight_config items
    highlight_config_items = list(highlight_config.items())[::-1]

    #create the hover text matrix
    hover_text = []
    for item in sorted_data:
        hover_text_row = []
        for version in sorted_versions:
            count = df_count_pivot.at[item, version] if version in df_count_pivot.columns else 0
            date = df_date_pivot.at[item, version] if version in df_date_pivot.columns else ''
            hover_text_data = f"Feature: {truncate_string(item, MAX_STRING_LENGTH)}<br>Version: {version}<br>Count: {count}<br>Date: {date}"
            hover_text_row.append(hover_text_data)
        hover_text.append(hover_text_row)

    #prepare text summary
    text_summary = "Feature Analysis Summary:\n"
    for item in df_count_pivot.index:
        highlighted = False
        highlight_details = ""
        # check for regex matches and prepare highlighting
        for pattern, color in highlight_config_items:
            if re.search(pattern, item, re.IGNORECASE):
                highlighted = True
                highlight_details = f"Highlight: {pattern} (Color: {color})\n"

        text_summary += f"\nFeature: {item}\n"
        if highlighted:
            text_summary += f"  {highlight_details}"

        for version in sorted_versions:
            count = df_count_pivot.at[item, version]
            date = df_date_pivot.at[item, version] if df_date_pivot.at[item, version] is not None else "nan"
            text_summary += f"  Version {version} ({date}): Count = {count}\n"

    # save summary to a text file
    with open(f"{package_name}_data_summary.txt", 'w', encoding='utf-8') as file:
        file.write(text_summary)

    text_summary = "Feature Analysis Summary by Version:\n"
    # Iterate through each version
    for version in sorted_versions:
        date = df[df['version'] == version]['vtscandate'].min()  # Get the date for the version
        text_summary += f"\nVersion {version} ({date if date != 'nan' else 'No Date Available'}):\n"
        # Check each subdomain for the current version
        for item in df_count_pivot.index:
            count = df_count_pivot.at[item, version]
            if count > 0:  # Only list subdomains that have a count greater than 0
                text_summary += f" {item}   Count: {count}\n"
                # Check for regex matches and add them
                for pattern, color in highlight_config_items:
                    if re.search(pattern, item, re.IGNORECASE):
                        text_summary += f" MATCH: {pattern} (Color: {color})\n"

    # Save the condensed summary to a text file
    with open(f"{package_name}_condensed_summary.txt", 'w', encoding='utf-8') as file:
        file.write(text_summary)

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


        # adding color highlighting config, workaround for plotly, shapes for highlighting with regex support
        shapes = []
        for data_idx, item in enumerate(sorted_data):
            for version_idx, version in enumerate(sorted_versions):
                count = df_count_pivot.loc[item, version]
                if count > 0:
                    for pattern, color in highlight_config_items:  # Use the reversed items here
                        if re.search(pattern, item, re.IGNORECASE):
                            shapes.append({
                                'type': 'rect',
                                'x0': version_idx - 0.5,
                                'y0': data_idx - 0.5,
                                'x1': version_idx + 0.5,
                                'y1': data_idx + 0.5,
                                'fillcolor': color,
                                'opacity': 0.3,
                                'line': {'width': 0},
                            })
                            break  # exit loop after the first match to avoid overlapping shapes for multiple matches

        title_description = data_type.capitalize()

        # update xaxis ticktext with new labels
        fig.update_layout(
            shapes=shapes,
            title=f"{title_description} Presence and Frequency Across Versions, {package_name}",
            xaxis=dict(tickmode='array', tickvals=sorted_versions, ticktext=sorted_versions_with_dates),
            yaxis=dict(autorange="reversed"))  # reverse the y-axis to show earliest versions at the top)
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

        # adding color highlighting config, workaround for plotly, shapes for highlighting with regex support
        shapes = []
        for data_idx, item in enumerate(sorted_data):
            for version_idx, version in enumerate(sorted_versions):
                count = df_count_pivot.loc[item, version]
                if count > 0:
                    for pattern, color in highlight_config_items:  # Use the reversed items here
                        if re.search(pattern, item, re.IGNORECASE):
                            shapes.append({
                                'type': 'rect',
                                'x0': version_idx - 0.5,
                                'y0': data_idx - 0.5,
                                'x1': version_idx + 0.5,
                                'y1': data_idx + 0.5,
                                'fillcolor': color,
                                'opacity': 0.3,
                                'line': {'width': 0},
                            })
                            break  # exit loop after the first match to avoid overlapping shapes for multiple matches

        title_description = data_type.capitalize()

        # update xaxis ticktext with new labels
        fig.update_layout(
            shapes=shapes,
            title=f"{title_description} Presence and Frequency Across Versions, {package_name}",
            xaxis=dict(tickmode='array', tickvals=sorted_versions, ticktext=sorted_versions_with_dates),
            yaxis=dict(autorange="reversed")  # reverse the y-axis to show earliest versions at the top
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

    # Group by (latitude, longitude) for offset overlapping markers
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

import logging
from io import StringIO

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

def should_cancel():
    return current_process != threading.current_thread()





