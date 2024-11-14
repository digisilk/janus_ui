import os
import zipfile
import re
import sqlite3
import pandas as pd
import plotly.graph_objects as go
from collections import defaultdict
from datetime import datetime
import requests
import dash_bootstrap_components as dbc
from dash import html

CACHE_DIR = "apk_cache"
DB_PATH = "androzoo.db"

 # SDK patterns
sdk_patterns = {
        'HMS Core': rb'com\.huawei\.hms',
        'GMS Core': rb'com\.google\.android\.gms',
        'Firebase': rb'com\.google\.firebase',
        'Amazon AWS': rb'com\.amazonaws',
        'Microsoft Azure': rb'com\.microsoft\.azure',
        'Tencent Cloud': rb'com\.tencent\.qcloud',
        'Alibaba Cloud': rb'com\.alibaba\.sdk',
        'Baidu Cloud': rb'com\.baidu\.cloud',

        # Social Media
        'Facebook SDK': rb'com\.facebook',
        'Twitter SDK': rb'com\.twitter\.sdk',
        'VK SDK': rb'com\.vk\.sdk',
        'Weibo SDK': rb'com\.sina\.weibo\.sdk',
        'LINE SDK': rb'com\.linecorp\.linesdk',
        'Kakao SDK': rb'com\.kakao\.sdk',

        # Messaging and Communication
        'Twilio': rb'com\.twilio',
        'SendBird': rb'com\.sendbird\.android',
        'Agora': rb'io\.agora',

        # Analytics
        'Google Analytics': rb'com\.google\.android\.gms\.analytics',
        'Flurry': rb'com\.flurry\.android',
        'Mixpanel': rb'com\.mixpanel\.android',
        'AppsFlyer': rb'com\.appsflyer',
        'Amplitude': rb'com\.amplitude\.api',
        'Umeng': rb'com\.umeng',
        'Yandex Metrica': rb'com\.yandex\.metrica',

        # Ad Networks
        'AdMob': rb'com\.google\.android\.gms\.ads',
        'Facebook Audience Network': rb'com\.facebook\.ads',
        'Unity Ads': rb'com\.unity3d\.ads',
        'AppLovin': rb'com\.applovin',
        'Vungle': rb'com\.vungle',
        'Chartboost': rb'com\.chartboost\.sdk',
        'InMobi': rb'com\.inmobi',
        'Yandex Mobile Ads': rb'com\.yandex\.mobile\.ads',

        # Payment
        'Stripe': rb'com\.stripe\.android',
        'PayPal': rb'com\.paypal\.android',
        'Braintree': rb'com\.braintreepayments',
        'Alipay': rb'com\.alipay\.sdk',
        'WeChat Pay': rb'com\.tencent\.mm\.opensdk',

        # Maps and Location
        'Google Maps': rb'com\.google\.android\.gms\.maps',
        'Mapbox': rb'com\.mapbox\.mapboxsdk',
        'HERE Maps': rb'com\.here',
        'Yandex MapKit': rb'com\.yandex\.mapkit',

        # Push Notifications
        'OneSignal': rb'com\.onesignal',
        'Urban Airship': rb'com\.urbanairship',
        'Pushwoosh': rb'com\.pushwoosh',

        # Crash Reporting
        'Crashlytics': rb'com\.crashlytics\.android',
        'Bugsnag': rb'com\.bugsnag\.android',
        'Sentry': rb'io\.sentry',

        # Security
        'Kaspersky': rb'com\.kaspersky\.sdk',
        'Avast': rb'com\.avast\.android',

        # VPN
        'OpenVPN': rb'de\.blinkt\.openvpn',
        'NordVPN': rb'com\.nordvpn\.android',

        # Game Engines
        'Unity': rb'com\.unity3d\.player',
        'Unreal Engine': rb'com\.epicgames\.ue4',
        'Cocos2d': rb'org\.cocos2d',

        # AR/VR
        'ARCore': rb'com\.google\.ar',
        'Vuforia': rb'com\.vuforia',

        # IoT
        'Samsung SmartThings': rb'com\.samsung\.android\.sdk\.smartthings',
        'Xiaomi IoT': rb'com\.xiaomi\.miot',

        # Chinese Tech Giants
        'WeChat SDK': rb'com\.tencent\.mm\.opensdk',
        'Alibaba SDK': rb'com\.alibaba\.sdk',
        'Baidu SDK': rb'com\.baidu\.android',
        'Xiaomi SDK': rb'com\.xiaomi\.sdk',

        # Russian Tech
        'Mail.ru SDK': rb'ru\.mail\.sdk',
        'OK (Odnoklassniki) SDK': rb'ru\.ok\.android\.sdk',

        # Indian Tech
        'Paytm SDK': rb'com\.paytm\.pgsdk',
        'PhonePe SDK': rb'com\.phonepe\.sdk',

        # Japanese Tech
        'Rakuten SDK': rb'com\.rakuten\.sdk',
        'Yahoo Japan SDK': rb'jp\.co\.yahoo\.android\.sdk',

        # Korean Tech
        'Naver SDK': rb'com\.naver\.sdk',

        # Southeast Asian Tech
        'Grab SDK': rb'com\.grab\.sdk',
        'Gojek SDK': rb'com\.gojek\.sdk',

        # Latin American Tech
        'Mercado Pago SDK': rb'com\.mercadopago\.android\.sdk',

        # Middle Eastern Tech
        'Careem SDK': rb'com\.careem\.sdk',

        # African Tech
        'M-Pesa SDK': rb'com\.safaricom\.mpesa',

        # Cryptocurrency
        'Coinbase SDK': rb'com\.coinbase\.android\.sdk',
        'Blockchain.com SDK': rb'com\.blockchain\.android',

        # Machine Learning
        'TensorFlow Lite': rb'org\.tensorflow\.lite',
        'PyTorch Mobile': rb'org\.pytorch\.mobile',

        # Augmented Reality
        'ARCore': rb'com\.google\.ar\.core',
        'Apple ARKit': rb'com\.apple\.arkit',

        # Cross-platform Frameworks
        'React Native': rb'com\.facebook\.react',
        'Flutter': rb'io\.flutter',
        'Xamarin': rb'mono\.android',
        'Cordova': rb'org\.apache\.cordova',

        # Backend as a Service (BaaS)
        'Parse': rb'com\.parse',
        'Back4App': rb'com\.back4app\.android',

        # Real-time Databases
        'Firebase Realtime Database': rb'com\.google\.firebase\.database',
        'Realm': rb'io\.realm',

        # Voice Assistants
        'Alexa': rb'com\.amazon\.alexa',
        'Google Assistant': rb'com\.google\.android\.apps\.googleassistant',

        # Biometrics
        'Fingerprint SDK': rb'com\.samsung\.android\.sdk\.pass',

        # Mobile Device Management (MDM)
        'VMware AirWatch': rb'com\.airwatch\.sdk',
        'MobileIron': rb'com\.mobileiron\.sdk',

        # Bluetooth Low Energy (BLE)
        'Nordic Semiconductor BLE': rb'no\.nordicsemi\.android\.ble',

        # Near Field Communication (NFC)
        'NFC Tools': rb'com\.nxp\.nfc\.sdk',

        # Fitness and Health
        'Google Fit': rb'com\.google\.android\.gms\.fitness',
        'Apple HealthKit': rb'com\.apple\.healthkit',

        # Audio Processing
        'Spotify SDK': rb'com\.spotify\.sdk',
        'Shazam SDK': rb'com\.shazam\.android\.sdk',

        # Video Processing
        'ExoPlayer': rb'com\.google\.android\.exoplayer',

        # Content Delivery Networks (CDN)
        'Akamai': rb'com\.akamai\.android',
        'Cloudflare': rb'com\.cloudflare\.sdk',

        # Customer Support
        'Zendesk': rb'com\.zendesk\.sdk',
        'Intercom': rb'io\.intercom\.android',

        # App Performance Monitoring
        'New Relic': rb'com\.newrelic\.agent\.android',
        'AppDynamics': rb'com\.appdynamics\.eumagent',

        # OCR (Optical Character Recognition)
        'Google ML Kit (OCR)': rb'com\.google\.mlkit\.vision\.text',
        'Tesseract OCR': rb'com\.googlecode\.tesseract\.android',

        # Database
        'SQLite': rb'android\.database\.sqlite',
        'Couchbase Lite': rb'com\.couchbase\.lite',

        # Testing
        'Espresso': rb'androidx\.test\.espresso',
        'Robolectric': rb'org\.robolectric',

        # Continuous Integration/Delivery
        'Fastlane': rb'tools\.fastlane',
        'Jenkins': rb'org\.jenkinsci\.plugins',

        # Blockchain
        'Web3j': rb'org\.web3j',
        'Ethereum': rb'org\.ethereum',

        # IoT Protocols
        'MQTT': rb'org\.eclipse\.paho\.client\.mqttv3',
        'CoAP': rb'org\.eclipse\.californium\.core',

        # 3D Rendering
        'OpenGL ES': rb'android\.opengl',
        'Vulkan': rb'android\.vulkan',

        # Geofencing
        'Radar': rb'io\.radar\.sdk',

        # Feature Flagging
        'LaunchDarkly': rb'com\.launchdarkly\.android',

        # A/B Testing
        'Optimizely': rb'com\.optimizely\.ab',

        # Deep Linking
        'Branch': rb'io\.branch\.referral',

        # In-App Updates
        'Google Play Core': rb'com\.google\.android\.play\.core',

        # App Security
        'ProGuard': rb'proguard\.annotation',
        'DexGuard': rb'com\.guardsquare\.dexguard',

        # AI and ChatBots
        'Dialogflow': rb'com\.google\.cloud\.dialogflow',
        'IBM Watson': rb'com\.ibm\.watson\.developer\_cloud',

        # Data Synchronization
        'SyncAdapter': rb'android\.content\.AbstractThreadedSyncAdapter',
}

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

def analyze_sdks(apk_path, sdk_patterns):
    results = {sdk: False for sdk in sdk_patterns}
    try:
        with zipfile.ZipFile(apk_path, 'r') as apk:
            dex_files = [f for f in apk.namelist() if f.endswith('.dex')]
            for dex_file in dex_files:
                with apk.open(dex_file) as dex:
                    content = dex.read()
                    for sdk, pattern in sdk_patterns.items():
                        if re.search(pattern, content):
                            results[sdk] = True
    except Exception as e:
        print(f"An error occurred while analyzing {apk_path}: {str(e)}")
    return results

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
        year = apk[2][:4]  # assuming vt_scan_date is in the format YYYY-MM-DD
        apks_by_year[year].append(apk)

    sampled_apks = []
    for year, year_apks in apks_by_year.items():
        sample_size = min(samples_per_year, len(year_apks))
        step = max(1, len(year_apks) // sample_size)
        sampled_apks.extend(year_apks[::step][:sample_size])

    return sorted(sampled_apks, key=lambda x: x[2])  # sort by vt_scan_date

def process_apks_for_sdk_presence(api_key, package_name, start_date, end_date, samples_per_year, highlight_config):
    apks = fetch_apks(DB_PATH, package_name, start_date, end_date)
    sampled_apks = sample_apks(apks, samples_per_year)

    sdk_results = []
    for sha256, vercode, vt_scan_date in sampled_apks:
        apk_path = download_apk(api_key, sha256)
        if apk_path:
            sdk_matches = analyze_sdks(apk_path, sdk_patterns)
            for sdk, present in sdk_matches.items():
                sdk_results.append((vercode, vt_scan_date, sdk, 1 if present else 0))

    df = pd.DataFrame(sdk_results, columns=['Version', 'vt_scan_date', 'SDK', 'Present'])
    df['vt_scan_date'] = pd.to_datetime(df['vt_scan_date']).dt.strftime('%Y-%m-%d')
    df['Version'] = df['Version'].astype(str)

    df_pivot = df.pivot_table(index='SDK', columns='Version', values='Present', aggfunc='sum', fill_value=0)
    df_date_pivot = df.pivot_table(index='SDK', columns='Version', values='vt_scan_date', aggfunc='first')

    sorted_versions = sorted(df_pivot.columns,
                             key=lambda s: [int(u) if u.isdigit() else u for u in re.split('(\d+)', s)])
    df_pivot = df_pivot[sorted_versions]
    df_date_pivot = df_date_pivot[sorted_versions]

    sorted_versions_with_dates = [f"{v} ({df[df['Version'] == v]['vt_scan_date'].min()})" for v in sorted_versions]

    # Evolutionary sorting logic
    sdk_appearances = {sdk: sum(df_pivot.loc[sdk] > 0) for sdk in df_pivot.index}
    
    # Build the master list of SDKs, maintaining the staircase effect
    master_sdk_list = []
    seen_sdks = set()

    for version in sorted_versions:
        current_version_sdks = df_pivot.index[df_pivot[version] > 0].tolist()
        new_or_readded_sdks = [sdk for sdk in current_version_sdks if sdk not in seen_sdks]
        new_or_readded_sdks.sort(key=lambda x: (-sdk_appearances[x], x))
        master_sdk_list.extend(new_or_readded_sdks)
        seen_sdks.update(new_or_readded_sdks)

    sorted_sdks = master_sdk_list

    hover_text = [[f"SDK: {sdk}<br>Version: {version}<br>Present: {'Yes' if df_pivot.at[sdk, version] > 0 else 'No'}<br>Date: {df_date_pivot.at[sdk, version]}"
                   for version in sorted_versions] for sdk in sorted_sdks]

    fig = go.Figure(data=go.Heatmap(
        z=df_pivot.loc[sorted_sdks, sorted_versions].values,
        x=sorted_versions,
        y=sorted_sdks,
        text=hover_text,
        hoverinfo='text',
        colorscale=[[0, 'white'], [1, 'black']],
        showscale=False
    ))

    shapes = []
    for sdk_idx, sdk in enumerate(sorted_sdks):
        for version_idx, version in enumerate(sorted_versions):
            if df_pivot.at[sdk, version] > 0:
                for pattern, color in highlight_config.items():
                    byte_pattern = pattern.encode('utf-8')
                    if re.search(byte_pattern, sdk_patterns[sdk], re.IGNORECASE):
                        shapes.append({
                            'type': 'rect',
                            'x0': version_idx - 0.5,
                            'y0': sdk_idx - 0.5,
                            'x1': version_idx + 0.5,
                            'y1': sdk_idx + 0.5,
                            'fillcolor': color,
                            'opacity': 0.3,
                            'line': {'width': 0},
                        })
                        break

    fig.update_layout(
        title=f'SDK Presence Over Time - {package_name}',
        xaxis=dict(title='Version', tickmode='array', tickvals=sorted_versions, ticktext=sorted_versions_with_dates),
        yaxis=dict(title='SDK', autorange="reversed"),
        shapes=shapes
    )

    present_sdks = [sdk for sdk in sorted_sdks if df_pivot.loc[sdk].sum() > 0]
    return fig, present_sdks

def get_sdk_info(present_sdks):
    sdk_info = []
    for sdk in present_sdks:
        description = sdk_descriptions.get(sdk, 'No description available.')
        sdk_info.append(
            dbc.Card(
                dbc.CardBody([
                    html.H5(sdk, className="card-title"),
                    html.P(description, className="card-text")
                ]),
                className="mb-3"
            )
        )
    return sdk_info

sdk_descriptions = {
    'HMS Core': "Huawei Mobile Services core library for Android apps.",
    'GMS Core': "Google Mobile Services core library for Android apps.",
    'Firebase': "Google's mobile platform for app development.",
    'Amazon AWS': "Amazon Web Services SDK for cloud services integration.",
    'Microsoft Azure': "Microsoft's cloud computing platform SDK.",
    'Tencent Cloud': "Tencent's cloud services SDK for mobile apps.",
    'Alibaba Cloud': "Alibaba's cloud computing platform SDK.",
    'Baidu Cloud': "Baidu's cloud services SDK for mobile applications.",
    'Facebook SDK': "Facebook's SDK for social media integration.",
    'Twitter SDK': "Twitter's SDK for social media integration.",
    'VK SDK': "VKontakte social network SDK for Russian market.",
    'Weibo SDK': "Sina Weibo social media platform SDK for Chinese market.",
    'LINE SDK': "LINE messaging app SDK for Asian markets.",
    'Kakao SDK': "Kakao social platform SDK for Korean market.",
    'Twilio': "Cloud communications platform for messaging and voice.",
    'SendBird': "Chat and messaging SDK for real-time communication.",
    'Agora': "Real-time voice and video SDK.",
    'Google Analytics': "Web and mobile app analytics service by Google.",
    'Flurry': "Yahoo's analytics and monetization platform.",
    'Mixpanel': "Product analytics for user behavior tracking.",
    'AppsFlyer': "Mobile attribution and marketing analytics platform.",
    'Amplitude': "Product analytics for tracking user behavior.",
    'Umeng': "Mobile app analytics platform popular in China.",
    'Yandex Metrica': "Web and app analytics service by Yandex.",
    'AdMob': "Google's mobile advertising platform.",
    'Facebook Audience Network': "Facebook's mobile advertising network.",
    'Unity Ads': "Mobile game monetization platform.",
    'AppLovin': "Mobile marketing and monetization platform.",
    'Vungle': "In-app video advertising platform.",
    'Chartboost': "Mobile game monetization and programmatic advertising platform.",
    'InMobi': "Mobile advertising and discovery platform.",
    'Yandex Mobile Ads': "Mobile advertising platform by Yandex.",
    'Stripe': "Online payment processing platform.",
    'PayPal': "Online payments system.",
    'Braintree': "Payment gateway for online and mobile businesses.",
    'Alipay': "Online payment platform widely used in China.",
    'WeChat Pay': "Mobile payment service integrated with WeChat.",
    'Google Maps': "Google's mapping and location services.",
    'Mapbox': "Custom online maps provider.",
    'HERE Maps': "Mapping and location data platform.",
    'Yandex MapKit': "Mapping services by Yandex.",
    'OneSignal': "Customer engagement platform with push notifications.",
    'Urban Airship': "Customer engagement platform for mobile apps.",
    'Pushwoosh': "Multi-platform push notification service.",
    'Crashlytics': "Crash reporting and analytics tool.",
    'Bugsnag': "Error monitoring and reporting platform.",
    'Sentry': "Application monitoring and error tracking software.",
    'Kaspersky': "Cybersecurity and anti-virus solutions.",
    'Avast': "Security software for mobile devices.",
    'OpenVPN': "Virtual Private Network implementation.",
    'NordVPN': "VPN service provider SDK.",
    'Unity': "Cross-platform game engine.",
    'Unreal Engine': "3D creation platform for games and other applications.",
    'Cocos2d': "Open-source game development framework.",
    'ARCore': "Google's platform for building augmented reality experiences.",
    'Vuforia': "Augmented reality SDK for mobile devices.",
    'Samsung SmartThings': "IoT platform for smart home devices.",
    'Xiaomi IoT': "Internet of Things platform by Xiaomi.",
    'WeChat SDK': "WeChat's SDK for app integration with the platform.",
    'Alibaba SDK': "Alibaba's e-commerce and cloud services SDK.",
    'Baidu SDK': "Baidu's mobile services SDK.",
    'Xiaomi SDK': "Xiaomi's mobile services SDK.",
    'Mail.ru SDK': "Russian internet company's SDK for various services.",
    'OK (Odnoklassniki) SDK': "SDK for Russian social network Odnoklassniki.",
    'Paytm SDK': "Indian digital payment platform SDK.",
    'PhonePe SDK': "Indian digital payments platform SDK.",
    'Rakuten SDK': "Japanese e-commerce and internet company's SDK.",
    'Yahoo Japan SDK': "Yahoo Japan's services SDK.",
    'Naver SDK': "South Korean search engine and internet content service's SDK.",
    'Grab SDK': "Southeast Asian ride-hailing and delivery platform SDK.",
    'Gojek SDK': "Indonesian multi-service platform SDK.",
    'Mercado Pago SDK': "Latin American online payments system SDK.",
    'Careem SDK': "Middle Eastern ride-hailing platform SDK.",
    'M-Pesa SDK': "African mobile phone-based money transfer service SDK.",
    'Coinbase SDK': "Cryptocurrency exchange platform SDK.",
    'Blockchain.com SDK': "Cryptocurrency wallet and exchange service SDK.",
    'TensorFlow Lite': "Lightweight machine learning framework for mobile and embedded devices.",
    'PyTorch Mobile': "Mobile version of the PyTorch machine learning framework.",
    'Apple ARKit': "Apple's augmented reality development platform.",
    'React Native': "Framework for building native apps using React.",
    'Flutter': "Google's UI toolkit for building natively compiled applications.",
    'Xamarin': "Microsoft's platform for building cross-platform mobile applications.",
    'Cordova': "Mobile application development framework.",
    'Parse': "Open-source backend platform.",
    'Back4App': "Backend as a Service platform based on Parse.",
    'Firebase Realtime Database': "Cloud-hosted NoSQL database for real-time data syncing.",
    'Realm': "Mobile database that runs directly inside phones, tablets or wearables.",
    'Alexa': "Amazon's virtual assistant AI technology.",
    'Google Assistant': "Google's virtual assistant AI technology.",
    'Fingerprint SDK': "Biometric authentication SDK for fingerprint recognition.",
    'VMware AirWatch': "Enterprise mobility management and security platform.",
    'MobileIron': "Mobile device management and security platform.",
    'Nordic Semiconductor BLE': "Bluetooth Low Energy solutions provider.",
    'NFC Tools': "Near Field Communication development tools.",
    'Google Fit': "Health-tracking platform developed by Google.",
    'Apple HealthKit': "Health and fitness data management framework by Apple.",
    'Spotify SDK': "Music streaming service SDK.",
    'Shazam SDK': "Music recognition technology SDK.",
    'ExoPlayer': "Media player for Android developed by Google.",
    'Akamai': "Content delivery network and cloud service provider.",
    'Cloudflare': "Web infrastructure and website security company.",
    'Zendesk': "Customer service software and support ticket system.",
    'Intercom': "Customer messaging platform.",
    'New Relic': "Software analytics tool suite.",
    'AppDynamics': "Application performance management and IT operations analytics.",
    'Google ML Kit (OCR)': "Machine learning SDK for mobile developers, including OCR capabilities.",
    'Tesseract OCR': "Optical Character Recognition engine.",
    'SQLite': "Lightweight, serverless database engine.",
    'Couchbase Lite': "Embedded NoSQL database for mobile and edge devices.",
    'Espresso': "Android UI testing framework.",
    'Robolectric': "Unit testing framework for Android.",
    'Fastlane': "App automation and management tool.",
    'Jenkins': "Open-source automation server for CI/CD.",
    'Web3j': "Lightweight Java and Android library for integration with Ethereum clients.",
    'Ethereum': "Decentralized, open-source blockchain with smart contract functionality.",
    'MQTT': "Lightweight messaging protocol for small sensors and mobile devices.",
    'CoAP': "Constrained Application Protocol for use with constrained nodes and networks.",
    'OpenGL ES': "Cross-platform graphics API for rendering 2D and 3D graphics on embedded systems.",
    'Vulkan': "Low-overhead, cross-platform 3D graphics and compute API.",
    'Radar': "Location data infrastructure and SDK.",
    'LaunchDarkly': "Feature management platform.",
    'Optimizely': "Digital experience platform with A/B testing capabilities.",
    'Branch': "Mobile linking and measurement platform.",
    'Google Play Core': "Android library for in-app updates and feature modules.",
    'ProGuard': "Java bytecode optimizer and obfuscator.",
    'DexGuard': "Android-specific optimizer and obfuscator.",
    'Dialogflow': "Natural language understanding platform for building conversational interfaces.",
    'IBM Watson': "Suite of enterprise-ready AI services, applications, and tooling.",
    'SyncAdapter': "Android framework component for performing data synchronization.",
}