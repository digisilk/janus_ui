from dash import dcc, html, callback_context, no_update
from dash.dependencies import Input, Output, State, ALL
from app import app
import dash_bootstrap_components as dbc

import layouts.home_layout as home
import layouts.apk_historical_analysis_layout as apk_historical_analysis
import layouts.historical_connectivity_layout as historical_connectivity
import layouts.other_layout as other
import layouts.svm_layout as svm_analysis
import layouts.apk_upload_layout as apk_upload
import layouts.apk_upload_dragdrop_layout as apk_upload_dragdrop
import layouts.sdk_presence_layout as sdk_presence
import layouts.string_presence_layout as string_presence
import layouts.user_apk_analysis_layout as user_apk_analysis

import callbacks.apk_historical_analysis_callbacks
import callbacks.other_callbacks 
import callbacks.svm_callbacks
import callbacks.apk_upload_callbacks
import callbacks.apk_upload_dragdrop_callbacks
import callbacks.historical_connectivity_callbacks
import callbacks.sdk_presence_callbacks
import callbacks.string_presence_callbacks
import callbacks.user_apk_analysis_callbacks

import dash_bootstrap_components as dbc

import gzip
import os
import urllib.request
from tqdm import tqdm
import pandas as pd

from create_sql_db import create_sqlite_db


import sys
import site

import sqlite3
import json



# Define navigation bar with a dropdown for historical analysis
navbar = dbc.NavbarSimple(
    children=[
        dbc.NavItem(dcc.Link('Home', href='/', className='nav-link')),
        dbc.DropdownMenu(
            children=[
                dbc.DropdownMenuItem("Connectivity", href="/historical-connectivity"),
                dbc.DropdownMenuItem("SDK Presence", href="/sdk-presence"),
                dbc.DropdownMenuItem("String Pattern Presence", href="/string-presence"),
                dbc.DropdownMenuItem("User APK Analysis", href="/user-apk-analysis"),
            ],
            nav=True,
            in_navbar=True,
            label="Historical Analysis",
        ),
        # dbc.NavItem(dcc.Link('Evolutionary Analysis (single package)', href='/apk-analysis', className='nav-link')),
        dbc.NavItem(dcc.Link('APK Strings', href='/apk-upload', className='nav-link')),
        dbc.NavItem(dcc.Link('APK Drag & Drop', href='/apk-upload-dragdrop', className='nav-link')),
    ],
    brand="Janus: A Social Science-Oriented App Analysis Suite. A project by Digisilk",
    brand_href="/",
    color="primary",
    dark=True,
)

# Define the app structure with a navigation bar
app.layout = dbc.Container([
    dcc.Location(id='url', refresh=False), 
    navbar,
    html.Div(id='page-content')
], fluid=True)

# Update the page based on the current URL
@app.callback(Output('page-content', 'children'), [Input('url', 'pathname')])
def display_page(pathname):
    if pathname == '/apk-analysis':
        return apk_historical_analysis.layout
    elif pathname == '/historical-connectivity':
        return historical_connectivity.layout
    #elif pathname == '/sdk-presence': WORK IN PROGRESS
        #return sdk_presence.layout
    elif pathname == '/string-presence':
        return string_presence.layout
    elif pathname == '/apk-upload':
        return apk_upload.layout
    elif pathname == '/apk-upload-dragdrop':
        return apk_upload_dragdrop.layout
    elif pathname == '/user-apk-analysis':
        return user_apk_analysis.layout
    else:
        return home.layout

def extract_package_ids_with_counts(conn, min_count=10):
    cursor = conn.cursor()
    cursor.execute("""
    SELECT pkg_name, COUNT(*) as count
    FROM apks
    GROUP BY pkg_name
    HAVING count > ?
    ORDER BY count DESC
    """, (min_count,))
    return [{"name": row[0], "count": row[1]} for row in cursor.fetchall()]

if __name__ == "__main__":
    filename = "latest_with-added-date.csv"
    db_filename = 'androzoo.db'
    package_ids_filename = "filtered_package_ids_with_counts10_ver.json"

    # Download database at startup/check
    def download_file_with_progress(url, output_path):
        class DownloadProgressBar(tqdm):
            def update_to(self, b=1, bsize=1, tsize=None):
                if tsize is not None:
                    self.total = tsize
                self.update(b * bsize - self.n)

        with DownloadProgressBar(unit='B', unit_scale=True, miniters=1, desc=url.split('/')[-1]) as t:
            urllib.request.urlretrieve(url, filename=output_path, reporthook=t.update_to)

    def check_file_corruption(file_path):
        try:
            with open(file_path, 'rb') as f:
                # Try to read a chunk of the file to check for corruption
                f.read(1024)
            return False
        except:
            return True

    #TODO; check age of database and update periodically and better corruption check

    # Update CSV file if it doesn't exist
    if not os.path.isfile(filename) or check_file_corruption(filename):
        url = "https://androzoo.uni.lu/static/lists/latest_with-added-date.csv.gz"
        print("Downloading file...")
        try:
            download_file_with_progress(url, filename + ".gz")
            print("File downloaded.")

            # Extract the gzip file
            print("Extracting file...")
            with gzip.open(filename + ".gz", "rb") as f_in:
                with open(filename, "wb") as f_out:
                    f_out.write(f_in.read())
            print("File extracted.")

            # Clean up the gzip file
            os.remove(filename + ".gz")

            if check_file_corruption(filename):
                print("File is corrupt after extraction. Please try downloading again.")
            else:
                print("File is successfully downloaded and extracted.")
        except Exception as e:
            print(f"An error occurred: {e}")
    else:
        print("File already exists and is not corrupt.")

    # Create or update SQLite database
    create_sqlite_db(filename, db_filename)
    
    # Generate package IDs JSON file
    print("Generating package IDs file...")
    if not os.path.isfile(package_ids_filename):
        try:
            conn = sqlite3.connect(db_filename)

            # Extract package IDs with counts
            print("Extracting and filtering package IDs...")
            filtered_data = extract_package_ids_with_counts(conn, min_count=10)
            print(f"Found {len(filtered_data)} packages with more than 10 versions")

            # Save to JSON file
            print(f"Saving to {package_ids_filename}...")
            with open(package_ids_filename, 'w') as f:
                json.dump(filtered_data, f)
            print("Package IDs file generated successfully")

            conn.close()

        except Exception as e:
            print(f"Error generating package IDs file: {e}")

    # start the Dash server
    app.run_server(debug=True, dev_tools_ui=True, dev_tools_props_check=True)
