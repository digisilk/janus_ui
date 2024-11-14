import os
import zipfile
import struct
import re
from collections import defaultdict
from datetime import datetime
import requests
import pandas as pd
import plotly.graph_objects as go
import sqlite3
import dash_bootstrap_components as dbc
from dash import html

DEFAULT_STRING_PATTERNS = {
    "Payments": r"(visa|mastercard|paypal|stripe|square|braintree|adyen|worldpay|checkout|payment gateway)",
    "Databases": r"(sqlite|mysql|postgresql|mongodb|oracle|firebird|mariadb|cassandra|couchbase|redis)",
    "Cloud Services": r"(aws|amazon web services|azure|microsoft cloud|google cloud|gcp|ibm cloud|oracle cloud|digitalocean|heroku)",
    "Social Media": r"(facebook|twitter|instagram|linkedin|pinterest|snapchat|tiktok|whatsapp|telegram|signal)",
    "Analytics": r"(google analytics|firebase analytics|mixpanel|amplitude|segment|flurry|appsflyer|adjust|kochava)",
    "Advertising": r"(admob|mopub|applovin|ironsource|unity ads|vungle|chartboost|adcolony|tapjoy|facebook audience network)"
}

# Configuration
CACHE_DIR = "apk_cache"
DB_PATH = "androzoo.db"

if not os.path.exists(CACHE_DIR):
    os.makedirs(CACHE_DIR)

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
            'string_ids_size': struct.unpack('<I', header_data[56:60])[0],
            'string_ids_off': struct.unpack('<I', header_data[60:64])[0],
        }

    def parse_string_ids(self):
        offset = self.header['string_ids_off']
        for i in range(self.header['string_ids_size']):
            string_data_off = struct.unpack('<I', self.data[offset:offset + 4])[0]
            self.string_ids.append(string_data_off)
            offset += 4

    def parse_strings(self):
        for string_data_off in self.string_ids:
            size, offset = self.read_uleb128(string_data_off)
            string_data = self.data[offset:offset + size].decode('utf-8', errors='replace')
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

def download_apk(api_key, sha256):
    local_filename = os.path.join(CACHE_DIR, f"{sha256}.apk")
    if not os.path.exists(local_filename):
        url = f"https://androzoo.uni.lu/api/download?apikey={api_key}&sha256={sha256}"
        with requests.get(url, stream=True) as r:
            if r.status_code == 200:
                with open(local_filename, 'wb') as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        f.write(chunk)
                print(f"Downloaded: {local_filename}")
            else:
                print(f"Failed to download {sha256}, status code: {r.status_code}")
    else:
        print(f"Using cached APK: {local_filename}")
    return local_filename

def extract_apk_dex_files(apk_path):
    dex_files = []
    with zipfile.ZipFile(apk_path, 'r') as z:
        for filename in z.namelist():
            if filename.endswith('.dex'):
                dex_data = z.read(filename)
                dex_files.append(dex_data)
    return dex_files

def analyze_strings(apk_path, string_patterns):
    dex_files = extract_apk_dex_files(apk_path)
    matched_strings = defaultdict(list)

    for dex_data in dex_files:
        parser = DEXParser(dex_data)
        parser.parse()
        for string in parser.strings:
            for pattern_name, pattern in string_patterns.items():
                if re.search(pattern, string, re.IGNORECASE):
                    matched_strings[pattern_name].append(string)

    return dict(matched_strings)

def fetch_apks(db_path, package_name, start_date, end_date):
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute('''SELECT sha256, vercode, vt_scan_date FROM apks
                 WHERE pkg_name = ? AND vt_scan_date BETWEEN ? AND ?
                 ORDER BY vt_scan_date''', (package_name, start_date, end_date))
    return c.fetchall()

def sample_apks(apks, samples_per_year):
    apks_by_year = defaultdict(list)
    for apk in apks:
        year = apk[2][:4]  # Assuming vt_scan_date is in the format YYYY-MM-DD
        apks_by_year[year].append(apk)

    sampled_apks = []
    for year, year_apks in apks_by_year.items():
        sample_size = min(samples_per_year, len(year_apks))
        step = max(1, len(year_apks) // sample_size)
        sampled_apks.extend(year_apks[::step][:sample_size])

    return sorted(sampled_apks, key=lambda x: x[2])  # Sort by vt_scan_date

def process_apks_for_string_presence(api_key, package_name, start_date, end_date, samples_per_year, highlight_config, string_patterns):
    apks = fetch_apks(DB_PATH, package_name, start_date, end_date)
    sampled_apks = sample_apks(apks, samples_per_year)

    string_results = []
    all_string_matches = defaultdict(list)
    for sha256, vercode, vt_scan_date in sampled_apks:
        apk_path = download_apk(api_key, sha256)
        if apk_path:
            string_matches = analyze_strings(apk_path, string_patterns)
            for pattern, matches in string_matches.items():
                string_results.append((vercode, vt_scan_date, pattern, len(matches)))
                all_string_matches[pattern].extend(matches)

    fig = plot_data(string_results, "String Pattern Presence", package_name, highlight_config)
    present_patterns = list(set([result[2] for result in string_results if result[3] > 0]))
    return fig, present_patterns, dict(all_string_matches)

def plot_data(data, title, package_name, highlight_config):
    df = pd.DataFrame(data, columns=['Version', 'vt_scan_date', 'Feature', 'Count'])
    df['vt_scan_date'] = pd.to_datetime(df['vt_scan_date']).dt.strftime('%Y-%m-%d')
    df['Version'] = df['Version'].astype(str)

    df_pivot = df.pivot_table(index='Feature', columns='Version', values='Count', aggfunc='sum', fill_value=0)
    df_date_pivot = df.pivot_table(index='Feature', columns='Version', values='vt_scan_date', aggfunc='first')

    # Filter out rows with all zero values
    df_pivot = df_pivot.loc[(df_pivot != 0).any(axis=1)]
    df_date_pivot = df_date_pivot.loc[df_pivot.index]

    sorted_versions = sorted(df_pivot.columns, key=lambda s: [int(u) if u.isdigit() else u for u in re.split('(\d+)', s)])
    df_pivot = df_pivot[sorted_versions]
    df_date_pivot = df_date_pivot[sorted_versions]

    sorted_versions_with_dates = [f"{v} ({df[df['Version'] == v]['vt_scan_date'].min()})" for v in sorted_versions]

    feature_appearances = {feature: sum(df_pivot.loc[feature] > 0) for feature in df_pivot.index}
    sorted_features = sorted(feature_appearances.keys(), key=lambda x: (-feature_appearances[x], x))

    hover_text = [[f"Feature: {feature}<br>Version: {version}<br>Count: {df_pivot.at[feature, version]}<br>Date: {df_date_pivot.at[feature, version]}"
                   for version in sorted_versions] for feature in sorted_features]

    fig = go.Figure(data=go.Heatmap(
        z=df_pivot.loc[sorted_features, sorted_versions].values,
        x=sorted_versions,
        y=sorted_features,
        text=hover_text,
        hoverinfo='text',
        colorscale=[[0, 'white'], [0.01, 'lightgrey'], [0.5, 'grey'], [1, 'black']],
        showscale=False
    ))

    shapes = []
    for feature_idx, feature in enumerate(sorted_features):
        for version_idx, version in enumerate(sorted_versions):
            if df_pivot.at[feature, version] > 0:
                for pattern, color in highlight_config.items():
                    if re.search(pattern, feature, re.IGNORECASE):
                        shapes.append({
                            'type': 'rect',
                            'x0': version_idx - 0.5,
                            'y0': feature_idx - 0.5,
                            'x1': version_idx + 0.5,
                            'y1': feature_idx + 0.5,
                            'fillcolor': color,
                            'opacity': 0.3,
                            'line': {'width': 0},
                        })
                        break

    fig.update_layout(
        shapes=shapes,
        title=f'{title} - {package_name}',
        xaxis=dict(title='Version', tickmode='array', tickvals=sorted_versions, ticktext=sorted_versions_with_dates),
        yaxis=dict(title='Feature', autorange="reversed")
    )

    return fig

def get_string_info(present_patterns, string_matches):
    string_info = []
    for pattern in present_patterns:
        matches = string_matches.get(pattern, [])
        string_info.append(
            dbc.Card(
                dbc.CardBody([
                    html.H5(pattern, className="card-title"),
                    html.P(f"Total matches: {len(matches)}", className="card-text"),
                    html.H6("Matched strings:", className="mt-3"),
                    html.Ul([html.Li(match) for match in matches[:10]]),  # Show first 10 matches
                    html.P(f"... and {len(matches) - 10} more" if len(matches) > 10 else "", className="card-text")
                ]),
                className="mb-3"
            )
        )
    return string_info
