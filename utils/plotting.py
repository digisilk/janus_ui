import plotly.graph_objects as go
import pandas as pd
import re
import plotly.io as pio
from datetime import datetime
import base64
import gc

def plot_data(version_vtscandate_subdomains_counts, package_name, highlight_config, data_type):
    print("Preparing data for plotting...")
    data = [{'Version': str(version), 'vt_scan_date': vt_scan_date, 'Subdomain': sd, 'Count': count} for
            version, vt_scan_date, sd, count in version_vtscandate_subdomains_counts]
    df = pd.DataFrame(data)
    if df.empty:
        print("No data to plot.")
        return

    print(df)

    # convert date to datetime and format it as a string
    df['vt_scan_date'] = pd.to_datetime(df['vt_scan_date']).dt.strftime('%Y-%m-%d')
    df['Version'] = df['Version'].astype(str)

    # pivot the count and date data
    df_count_pivot = df.pivot_table(index='Subdomain', columns='Version', values='Count', aggfunc='sum', fill_value=0)
    df_date_pivot = df.pivot_table(index='Subdomain', columns='Version', values='vt_scan_date', aggfunc='first')

    sorted_versions = sorted(df_count_pivot.columns,
                             key=lambda s: [int(u) if u.isdigit() else u for u in re.split('(\d+)', s)])
    df_count_pivot = df_count_pivot[sorted_versions]
    df_date_pivot = df_date_pivot[sorted_versions]

    # create a new list for x-axis labels combining version and date
    sorted_versions_with_dates = []
    for version in sorted_versions:
        #find the earliest date for this version
        earliest_date = df[df['Version'] == version]['vt_scan_date'].min()
        label = f"{version} ({earliest_date})"
        sorted_versions_with_dates.append(label)

    sorted_versions = sorted(df['Version'].unique(),
                             key=lambda x: [int(part) if part.isdigit() else part for part in re.split('([0-9]+)', x)])

    #evolutionary sorting logic
    # 1: count appearances of each domain across all versions
    domain_appearances = {}
    for version in sorted_versions:
        for domain in df[df['Version'] == version]['Subdomain'].unique():
            domain_appearances[domain] = domain_appearances.get(domain, 0) + 1

    # 2: sort domains within each version based on appearances and re-addition
    version_sorted_domains = {}
    for version in sorted_versions:
        current_version_domains = df[df['Version'] == version]['Subdomain'].unique().tolist()
        # sort domains within the current version based on their total appearances (descending)
        sorted_domains = sorted(current_version_domains, key=lambda x: (-domain_appearances[x], x))
        version_sorted_domains[version] = sorted_domains

    # 3: build the master list of domains, maintaining the staircase effect
    #initialize a master list of domains across all versions
    master_domain_list = []
    seen_domains = set()

    for version in sorted_versions:
        #retrieve the sorted list of domains for the current version
        current_version_sorted_domains = version_sorted_domains[version]
        #filter to include only new or re-added domains not already in master_domain_list
        new_or_readded_domains = [domain for domain in current_version_sorted_domains if domain not in seen_domains]
        master_domain_list.extend(new_or_readded_domains)
        #update the seen_domains set
        seen_domains.update(new_or_readded_domains)

    sorted_subdomains = master_domain_list

    #create the hover text matrix
    hover_text = []
    for subdomain in sorted_subdomains:
        hover_text_row = []
        for version in sorted_versions:
            count = df_count_pivot.at[subdomain, version] if version in df_count_pivot.columns else 0
            date = df_date_pivot.at[subdomain, version] if version in df_date_pivot.columns else ''
            hover_text_data = f"Feature: {subdomain}<br>Version: {version}<br>Count: {count}<br>Date: {date}"
            hover_text_row.append(hover_text_data)
        hover_text.append(hover_text_row)

    #prepare text summary
    text_summary = "Feature Analysis Summary:\n"
    for subdomain in df_count_pivot.index:
        highlighted = False
        highlight_details = ""
        # check for regex matches and prepare highlighting
        for pattern, color in highlight_config.items():
            if re.search(pattern, subdomain, re.IGNORECASE):
                highlighted = True
                highlight_details = f"Highlight: {pattern} (Color: {color})\n"

        text_summary += f"\nFeature: {subdomain}\n"
        if highlighted:
            text_summary += f"  {highlight_details}"

        for version in sorted_versions:
            count = df_count_pivot.at[subdomain, version]
            date = df_date_pivot.at[subdomain, version] if df_date_pivot.at[subdomain, version] is not None else "nan"
            text_summary += f"  Version {version} ({date}): Count = {count}\n"

    # save summary to a text file
    with open(f"{package_name}_data_summary.txt", 'w', encoding='utf-8') as file:
        file.write(text_summary)

    text_summary = "Feature Analysis Summary by Version:\n"
    # Iterate through each version
    for version in sorted_versions:
        date = df[df['Version'] == version]['vt_scan_date'].min()  # Get the date for the version
        text_summary += f"\nVersion {version} ({date if date != 'nan' else 'No Date Available'}):\n"
        # Check each subdomain for the current version
        for subdomain in df_count_pivot.index:
            count = df_count_pivot.at[subdomain, version]
            if count > 0:  # Only list subdomains that have a count greater than 0
                text_summary += f" {subdomain}   Count: {count}\n"
                # Check for regex matches and add them
                for pattern, color in highlight_config.items():
                    if re.search(pattern, subdomain, re.IGNORECASE):
                        text_summary += f" MATCH: {pattern} (Color: {color})\n"

    # Save the condensed summary to a text file
    with open(f"{package_name}_condensed_summary.txt", 'w', encoding='utf-8') as file:
        file.write(text_summary)

    # Create heatmap
    fig = go.Figure(data=go.Heatmap(
        showscale=False,
        z=df_count_pivot.reindex(sorted_subdomains).values,
        x=sorted_versions,
        y=sorted_subdomains,
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
    for subdomain_idx, subdomain in enumerate(sorted_subdomains):
        for version_idx, version in enumerate(sorted_versions):
            count = df_count_pivot.loc[subdomain, version]
            if count > 0:
                for pattern, color in highlight_config.items():
                    if re.search(pattern, subdomain, re.IGNORECASE):  # re.IGNORECASE make the search case-insensitive
                        shapes.append({
                            'type': 'rect',
                            'x0': version_idx - 0.5,
                            'y0': subdomain_idx - 0.5,
                            'x1': version_idx + 0.5,
                            'y1': subdomain_idx + 0.5,
                            'fillcolor': color,
                            'opacity': 0.3,
                            'line': {'width': 0},
                        })
                        break  # exit loop after the first match to avoid overlapping shapes for multiple matches

    title_description = ', '.join(data_type).title()

    # update xaxis ticktext with new labels
    fig.update_layout(
        shapes=shapes,
        title=title_description +' Presence and Frequency Across Versions, ' + package_name,
        xaxis=dict(tickmode='array', tickvals=sorted_versions, ticktext=sorted_versions_with_dates),
        yaxis=dict(autorange="reversed")  # reverse the y-axis to show earliest versions at the top
    )

    #save plot to HTML
    date_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f'{package_name}_{title_description}{date_str}.html'
    print(filename)
    pio.write_html(fig, file=filename, auto_open=False)
    return fig

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

def generate_download_link(fig):
    fig_html = fig.to_html(full_html=True, include_plotlyjs=True)
    fig_bytes = fig_html.encode('utf-8')
    fig_base64 = base64.b64encode(fig_bytes).decode('utf-8')
    data_url = f'data:text/html;base64,{fig_base64}'
    return data_url