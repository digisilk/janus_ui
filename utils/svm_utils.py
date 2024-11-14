import csv
import os
import re
import gc
import pickle
import requests
import gzip
import shutil
from datetime import datetime
import pandas as pd
import numpy as np
from androguard.core.bytecodes import dvm
from androguard.misc import AnalyzeAPK
from sklearn.svm import SVC
from collections import defaultdict
import tldextract
import time
API_KEY = None
CSV_PATH = "latest_with-added-date.csv.gz"
BASE_DOWNLOAD_DIR = "downloaded_apks"



def set_api_key(key):
    global API_KEY
    API_KEY = key

def download_file_with_progress(url, filename):
    response = requests.get(url, stream=True)
    total = response.headers.get('content-length')
    if total is None:
        with open(filename, 'wb') as f:
            f.write(response.content)
    else:
        downloaded = 0
        total = int(total)
        with open(filename, 'wb') as f:
            for data in response.iter_content(chunk_size=4096):
                downloaded += len(data)
                f.write(data)
                done = int(50 * downloaded / total)
                print(f"\r[{'=' * done}{' ' * (50-done)}] {done * 2}%", end='')

def download_and_extract_csv():
    csv_file_path = "latest_with-added-date.csv"
    if not os.path.isfile(csv_file_path):
        print("Downloading Androzoo CSV...")
        download_file_with_progress("https://androzoo.uni.lu/static/lists/latest_with-added-date.csv.gz", CSV_PATH)
        print("\nExtracting CSV...")
        with gzip.open(CSV_PATH, 'rb') as f_in, open(csv_file_path, 'wb') as f_out:
            shutil.copyfileobj(f_in, f_out)
    return csv_file_path

def find_apks_metadata(package_names, start_date, end_date, csv_file):
    metadata = []
    with open(csv_file, mode='r', encoding='utf-8') as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            if row['pkg_name'] in package_names and row['vt_scan_date']:
                try:
                    vt_scan_date = datetime.strptime(row['vt_scan_date'], "%Y-%m-%d %H:%M:%S")
                    if start_date <= vt_scan_date <= end_date:
                        metadata.append((row['pkg_name'], row['sha256'], row['vercode'], vt_scan_date))
                except ValueError:
                    continue  # Skip rows with parsing errors
    return metadata

def download_apk(sha256, pkg_name, vt_date, download_dir):
    url = f"https://androzoo.uni.lu/api/download?apikey={API_KEY}&sha256={sha256}"
    date_str = vt_date.strftime("%Y%m%d")
    local_file_path = os.path.join(download_dir, f"{pkg_name}_{date_str}_{sha256}.apk")
    print(f"\nDownloading APK: {sha256} for package {pkg_name} on {date_str}")
    download_file_with_progress(url, local_file_path)

def download_apks_for_config(package_names, start_date, end_date, desired_versions, folder_name):
    download_folder = os.path.join(BASE_DOWNLOAD_DIR, folder_name)
    os.makedirs(download_folder, exist_ok=True)
    csv_file = download_and_extract_csv()
    for package_name in package_names:
        metadata = find_apks_metadata([package_name], start_date, end_date, csv_file)
        metadata = sorted(metadata, key=lambda x: x[3], reverse=True)[:desired_versions]
        for pkg_name, sha256, _, vt_date in metadata:
            download_apk(sha256, pkg_name, vt_date, download_folder)

# Define feature extractor functions for different types of features
def extract_full_urls_from_apk(a):
    full_urls = set()
    try:
        for dex in a.get_all_dex():
            dv = dvm.DalvikVMFormat(dex)
            for string in dv.get_strings():
                urls = re.findall(r'https?://\S+', string)
                full_urls.update(urls)
    except Exception as e:
        print(f'Error while extracting full URLs: {str(e)}')
    finally:
        gc.collect()
    return full_urls

def extract_subdomains_from_apk(a):
    subdomains = set()
    try:
        for dex in a.get_all_dex():
            dv = dvm.DalvikVMFormat(dex)
            for string in dv.get_strings():
                urls = re.findall(r'https?://\S+', string)
                for url in urls:
                    parsed_url = tldextract.extract(url)
                    subdomain_full = '.'.join(part for part in [parsed_url.subdomain, parsed_url.domain, parsed_url.suffix] if part).strip('.')
                    if subdomain_full and "%s" not in subdomain_full:
                        subdomains.add(subdomain_full)
    except Exception as e:
        print(f'Error while extracting subdomains: {str(e)}')
    finally:
        gc.collect()
    return subdomains

def extract_permissions(a):
    return set(a.get_permissions())

def extract_libraries(a):
    return set(a.get_libraries())

def extract_services(a):
    return set(a.get_services())

def extract_features_from_apk(apk_path, feature_extractors):
    a, d, dx = AnalyzeAPK(apk_path)
    features = set()
    for extractor in feature_extractors:
        extracted_features = extractor(a)
        if isinstance(extracted_features, set):
            features |= extracted_features
    return features

def extract_features_and_labels(folder_paths, save_path, feature_extractors):
    if os.path.exists(save_path):
        with open(save_path, 'rb') as f:
            features_list, labels_list = pickle.load(f)
    else:
        features_list = []
        labels_list = []
        for folder, label in folder_paths.items():
            for apk in os.listdir(folder):
                if apk.endswith('.apk'):
                    apk_path = os.path.join(folder, apk)
                    features = extract_features_from_apk(apk_path, feature_extractors)
                    features_list.append(features)
                    labels_list.append(label)
        with open(save_path, 'wb') as f:
            pickle.dump((features_list, labels_list), f)
    return features_list, labels_list

def prepare_dataframe(features_list, labels_list):
    all_features = set().union(*features_list)
    data = defaultdict(list)
    for features in features_list:
        for feature in all_features:
            data[feature].append(1 if feature in features else 0)
    df = pd.DataFrame(data)
    df['label'] = labels_list
    return df

def perform_svm_analysis(df):
    X = df.drop('label', axis=1)
    y = df['label'].map({'Sample1': 0, 'Sample2': 1})
    model = SVC(kernel='linear', probability=True)
    model.fit(X, y)
    feature_importance = model.coef_[0]
    sorted_indices = np.argsort(feature_importance)
    sorted_features = [(X.columns[i], feature_importance[i]) for i in sorted_indices]
    return sorted_features
