import base64
import os
import zipfile
from dash import Input, Output, State, html
from app import app
from utils.dex_parser import DEXParser

@app.callback(
    Output('apk-upload-output', 'children'),
    [Input('upload-apk', 'contents')],
    [State('upload-apk', 'filename')]
)
def analyze_apk(contents, filename):
    if contents is not None:
        # Decode the file contents
        content_type, content_string = contents.split(',')
        decoded = base64.b64decode(content_string)
        
        # Save the uploaded file
        apk_path = 'uploaded_apk.apk'
        with open(apk_path, 'wb') as f:
            f.write(decoded)
        
        # Extract the DEX file from the APK
        with zipfile.ZipFile(apk_path, 'r') as zip_ref:
            zip_ref.extract('classes.dex', 'extracted_apk')
        
        # Parse the DEX file
        dex_file_path = os.path.join('extracted_apk', 'classes.dex')
        parser = DEXParser(dex_file_path)
        parser.parse()
        strings = parser.get_strings()
        
        # Clean up extracted files
        os.remove(apk_path)
        os.remove(dex_file_path)
        os.rmdir('extracted_apk')
        
        # Display the strings
        return html.Pre('\n'.join(strings))
    return 'No file uploaded yet.'