# utils/apk_historical_analysis_util.py
import base64
import csv
import gc
import json
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

from utils.plotting import plot_data, generate_download_link

from .dex_parser import DEXParser

#  variable to track progress
progress = {
    'current_task': '',
    'total_tasks': 0,
    'completed_tasks': 0
}


def process_apks(n_clicks, api_key, start_date, end_date, package_list_input, desired_versions, highlight_config_str,
                 data_type_input, use_cache_json, core_count_input):
    if n_clicks is None:
        return "", ""

    package_list = [package_list_input.strip()]  # Only accept one package
    highlight_config = json.loads(highlight_config_str)

    global progress
    progress['total_tasks'] = len(package_list)
    progress['completed_tasks'] = 0

    start_date_str = datetime.strptime(start_date, '%Y-%m-%d').strftime('%Y-%m-%d ') + "23:59:59.999999"
    end_date_str = datetime.strptime(end_date, '%Y-%m-%d').strftime('%Y-%m-%d ') + "23:59:59.999999"

    # Validate and clean APKs
    base_dir = Path(__file__).parent.parent.absolute()
    universal_cache_dir = os.path.join(base_dir, "apk_cache")
    trash_dir = os.path.join(base_dir, "trash")
    validate_and_clean_apks(universal_cache_dir, trash_dir)

    results = []

    for package_name in package_list:
        if package_name:
            try:
                progress['current_task'] = f"Processing {package_name}"
                fig = process_package(
                    package_name.strip(),
                    os.getcwd(),
                    api_key,
                    'latest_with-added-date.csv',
                    start_date_str,
                    end_date_str,
                    int(desired_versions),
                    highlight_config,
                    data_type_input,
                    "true" in use_cache_json,
                    int(core_count_input),
                    download=True
                )

                if fig:
                    try:
                        download_link = generate_download_link(fig)
                        results.append(html.Div([
                            dcc.Graph(figure=fig, style={'height': '1000px'}),
                            html.A("Download Plotly Figure", href=download_link, download="plotly_figure.html")
                        ]))
                    except Exception as e:
                        results.append(html.P(f"Error generating plotly figure for {package_name}: {str(e)}"))

            except Exception as e:
                print(f"Error processing package {package_name}: {str(e)}")
                results.append(html.P(f"Error processing package {package_name}: {str(e)}"))
            progress['completed_tasks'] += 1

    return results


def validate_and_clean_apks(universal_cache_dir, trash_dir):
    os.makedirs(trash_dir, exist_ok=True)
    for filename in os.listdir(universal_cache_dir):
        if filename.endswith('.apk'):
            apk_path = os.path.join(universal_cache_dir, filename)
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


def find_sha256_vercode_vtscandate_old(package_name, csv_path, start_date, end_date):
    sha256_vercode_vtscandate_values = []
    start_date = datetime.strptime(start_date, '%Y-%m-%d %H:%M:%S.%f')
    end_date = datetime.strptime(end_date, '%Y-%m-%d %H:%M:%S.%f')
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        next(reader)
        for row in reader:
            if row[5] == package_name:
                vt_scan_date = datetime.strptime(row[10], '%Y-%m-%d %H:%M:%S.%f')
                if start_date <= vt_scan_date <= end_date:
                    sha256_vercode_vtscandate_values.append((row[0], row[6], row[10]))
    sha256_vercode_vtscandate_values.sort(key=lambda x: datetime.strptime(x[2], '%Y-%m-%d %H:%M:%S.%f'))
    return sha256_vercode_vtscandate_values


def find_sha256_vercode_vtscandate(package_name, csv_path, start_date, end_date):
    start_date = datetime.strptime(start_date, '%Y-%m-%d %H:%M:%S.%f')
    end_date = datetime.strptime(end_date, '%Y-%m-%d %H:%M:%S.%f')

    df = pd.read_csv(csv_path, usecols=[0, 5, 6, 10], names=['sha256', 'pkg_name', 'vercode', 'vt_scan_date'])
    df['vt_scan_date'] = pd.to_datetime(df['vt_scan_date'], format='%Y-%m-%d %H:%M:%S.%f', errors='coerce')

    mask = (
            (df['pkg_name'] == package_name) &
            (df['vt_scan_date'] >= start_date) &
            (df['vt_scan_date'] <= end_date)
    )

    filtered_df = df[mask].sort_values('vt_scan_date')

    return [
        (row.sha256, row.vercode, row.vt_scan_date.strftime('%Y-%m-%d %H:%M:%S.%f'))
        for row in filtered_df.itertuples(index=False)
    ]


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


def download_apks(package_names, apikey, universal_cache_dir, csv_path, start_date, end_date, desired_versions,
                  core_count):
    pool = mp.Pool(min(core_count, mp.cpu_count() - 1))
    download_tasks = []
    apk_log = {}
    for package_name in package_names:
        sha256_vercode_vtscandate_list = find_sha256_vercode_vtscandate(package_name, csv_path, start_date, end_date)
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

'''
class DEXParser:
    def __init__(self, data):
        self.data = data
        self.header = {}
        self.string_ids = []
        self.strings = []

    def parse(self):
        self.parse_header()
        self.parse_string_ids()
        self.parse_strings()

    def parse_header(self):
        header_data = self.data[:112]
        self.header = {
            'magic': header_data[:8],
            'checksum': struct.unpack('<I', header_data[8:12])[0],
            'signature': header_data[12:32],
            'file_size': struct.unpack('<I', header_data[32:36])[0],
            'header_size': struct.unpack('<I', header_data[36:40])[0],
            'endian_tag': struct.unpack('<I', header_data[40:44])[0],
            'link_size': struct.unpack('<I', header_data[44:48])[0],
            'link_off': struct.unpack('<I', header_data[48:52])[0],
            'map_off': struct.unpack('<I', header_data[52:56])[0],
            'string_ids_size': struct.unpack('<I', header_data[56:60])[0],
            'string_ids_off': struct.unpack('<I', header_data[60:64])[0],
            'type_ids_size': struct.unpack('<I', header_data[64:68])[0],
            'type_ids_off': struct.unpack('<I', header_data[68:72])[0],
            'proto_ids_size': struct.unpack('<I', header_data[72:76])[0],
            'proto_ids_off': struct.unpack('<I', header_data[76:80])[0],
            'field_ids_size': struct.unpack('<I', header_data[80:84])[0],
            'field_ids_off': struct.unpack('<I', header_data[84:88])[0],
            'method_ids_size': struct.unpack('<I', header_data[88:92])[0],
            'method_ids_off': struct.unpack('<I', header_data[92:96])[0],
            'class_defs_size': struct.unpack('<I', header_data[96:100])[0],
            'class_defs_off': struct.unpack('<I', header_data[100:104])[0],
            'data_size': struct.unpack('<I', header_data[104:108])[0],
            'data_off': struct.unpack('<I', header_data[108:112])[0],
        }

    def parse_string_ids(self):
        offset = self.header['string_ids_off']
        for i in range(self.header['string_ids_size']):
            string_data_off = struct.unpack('<I', self.data[offset:offset + 4])[0]
            self.string_ids.append(string_data_off)
            offset += 4

    def parse_strings(self):
        url_regex = re.compile(r'https?://\S+')
        for string_data_off in self.string_ids:
            size, offset = self.read_uleb128(string_data_off)
            string_data = self.data[offset:offset + size].decode('utf-8', errors='replace')
            if url_regex.search(string_data):
                self.strings.append(string_data)

    def read_uleb128(self, offset):
        result = 0
        shift = 0
        size = 0
        while True:
            byte = self.data[offset]
            offset += 1
            size += 1
            result |= (byte & 0x7f) << shift
            if byte & 0x80 == 0:
                break
            shift += 7
        return result, offset
'''

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


def extract_apk_features(file_path, data_type, use_cache_json):
    json_file_path = f"{file_path}.{data_type}.json"
    if os.path.exists(json_file_path) and use_cache_json:
        with open(json_file_path, 'r') as json_file:
            data = json.load(json_file)
        return data
    else:
        data = []
        try:
            '''a, _, _ = AnalyzeAPK(file_path)
            if 'urls' or 'subdomains' or 'domains' in data_type:
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
                                subdomain_full = '.'.join(
                                    [parsed_url.subdomain, parsed_url.domain, parsed_url.suffix]).strip('.')
                                if "%s" not in subdomain_full:
                                    if "." in subdomain_full:
                                        if 'subdomains' in data_type:
                                            data.append(subdomain_full)
                                        if 'domains' in data_type:
                                            domain = '.'.join([parsed_url.domain, parsed_url.suffix]).strip('.')
                                            if "." in domain:
                                                data.append(domain)'''

            dex_files = extract_apk_dex_files(file_path)
            print("Using custom parser...")
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
            if 'permissions' or 'services' or 'activities' or 'providers' or 'receivers' or 'libraries' or 'java_classes' in data_type:
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
        except Exception as e:
            print(f'Error while extracting {data_type} from {file_path}: {str(e)}')
        with open(json_file_path, 'w') as json_file:
            json.dump(data, json_file)
        return data


def process_package(package_name, base_directory, apikey, csv_path, start_date, end_date, desired_versions,
                    highlight_config, data_type, use_cache_json, core_count, download=True):
    universal_cache_dir = os.path.join(base_directory, "apk_cache")
    os.makedirs(universal_cache_dir, exist_ok=True)

    if download:
        downloaded_apks = download_apks([package_name], apikey, universal_cache_dir, csv_path, start_date, end_date,
                                        desired_versions, core_count)
    '''else:
        # Load APK log and get the relevant APKs for this package
        with open(os.path.join(universal_cache_dir, 'apk_log.json'), 'r') as f:
            apk_log = json.load(f)
        downloaded_apks = [find_apk_by_partial_sha256(universal_cache_dir, apk['sha256']) for apk in
                           apk_log.get(package_name, [])]
        downloaded_apks = [apk for apk in downloaded_apks if apk is not None]'''

    if downloaded_apks:
        version_vtscandate_subdomains = process_package_apks(universal_cache_dir, package_name, data_type,
                                                             use_cache_json, core_count)
        print(version_vtscandate_subdomains)

        # Plot the existing data
        fig = plot_data(version_vtscandate_subdomains, package_name, highlight_config, data_type)

        del version_vtscandate_subdomains
        gc.collect()
        return fig
    else:
        return None


def process_package_apks(universal_cache_dir, package_name, data_type, use_cache_json, core_count):
    with open(os.path.join(universal_cache_dir, 'apk_log.json'), 'r') as f:
        apk_log = json.load(f)

    relevant_apks = apk_log.get(package_name, [])

    pool = mp.Pool(min(core_count, mp.cpu_count() - 1), maxtasksperchild=4)
    results = pool.starmap(process_file, [
        (apk['sha256'], universal_cache_dir, data_type, use_cache_json, apk['vercode'], apk['vtscandate']) for apk in
        relevant_apks])
    pool.close()
    pool.join()

    version_vtscandate_subdomains_counts = []
    for result in results:
        if result is not None:
            version_vtscandate_subdomains_counts.extend(result)

    del results
    gc.collect()
    return version_vtscandate_subdomains_counts


def process_file(sha256, folder_path, data_type, use_cache_json, vercode, vtscandate):
    file_path = os.path.join(folder_path, f"{sha256}.apk")
    if not os.path.exists(file_path):
        print(f"Warning: APK file not found for SHA256 {sha256}")
        return None

    try:
        a, _, _ = AnalyzeAPK(file_path)
        version = vercode  # Use the vercode from apk_log instead of extracting it again

        subdomains = extract_apk_features(file_path, data_type, use_cache_json)
        subdomain_counts = defaultdict(int)
        for subdomain in subdomains:
            subdomain_counts[subdomain] += 1
        del a
        gc.collect()
        return [(version, vtscandate, subdomain, count) for subdomain, count in subdomain_counts.items()]
    except Exception as e:
        print(f"Error processing file {sha256}.apk: {str(e)}")
        return None


def generate_download_link(fig):
    fig_html = fig.to_html(full_html=True, include_plotlyjs=True)
    fig_bytes = fig_html.encode('utf-8')
    fig_base64 = base64.b64encode(fig_bytes).decode('utf-8')
    data_url = f'data:text/html;base64,{fig_base64}'
    return data_url


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
