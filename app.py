from flask import (Flask, redirect, render_template, request,
                   send_from_directory, url_for, abort, Response)

import pandas as pd
import numpy as np
from dotenv import load_dotenv
import os

import hashlib
import hmac
from termcolor import colored

import dropbox
from dropbox import DropboxOAuth2FlowNoRedirect


import os
import shutil
from openpyxl import load_workbook
from openpyxl_image_loader import SheetImageLoader

from time import sleep

load_dotenv()
DP_ALLOW_NEW_WEBHOOKS = os.getenv("DP_ALLOW_NEW_WEBHOOKS")
APP_SECRET = os.getenv("DP_secret")
APP_KEY = os.getenv("DP_key")
# DP_access_token = os.getenv("DP_access_token")

dbx = None
oauth_result = None

def initialize_dropbox_interactive():
    global dbx, oauth_result
    auth_flow = DropboxOAuth2FlowNoRedirect(APP_KEY, use_pkce=True, token_access_type='offline')

    authorize_url = auth_flow.start()
    print("1. Go to: " + authorize_url)
    print("2. Click \"Allow\" (you might have to log in first).")
    print("3. Copy the authorization code.")
    # auth_code = input("Enter the authorization code here: ").strip()
    
    print("Waiting 5 minutes to allow user to get the code...")
    sleep(300) # Wait for 5 minutes to allow user to get the code
    
    print("Reading authorization code from environment variable DP_AUTH_CODE")
    
    load_dotenv(override=True)
    auth_code = os.getenv("DP_AUTH_CODE").strip()
    # print(f"Using auth_code: {auth_code}")

    try:
        oauth_result = auth_flow.finish(auth_code)
    except Exception as e:
        print('Error: %s' % (e,))
        exit(1)
        

    dbx = dropbox.Dropbox(oauth2_refresh_token=oauth_result.refresh_token, app_key=APP_KEY)
    dbx.users_get_current_account()

def dropbox_content_hash(file_path):
    """Calculate the Dropbox content hash for a local file."""
    CHUNK_SIZE = 4 * 1024 * 1024  # 4MB chunks
    
    chunk_hashes = []
    
    with open(file_path, 'rb') as f:
        while True:
            chunk = f.read(CHUNK_SIZE)
            if not chunk:
                break
            chunk_hashes.append(hashlib.sha256(chunk).digest())
    
    if not chunk_hashes:
        return hashlib.sha256(b'').hexdigest()
    
    return hashlib.sha256(b''.join(chunk_hashes)).hexdigest()

def strip_list(items):
    """Trim whitespace for each item and normalize capitalization.

    This makes the first character uppercase and the rest lowercase (e.g. "ma" -> "Ma").
    It is used for columns like `Days` and `Category` so values match the UI labels.
    """
    out = []
    for item in items:
        s = str(item).strip()
        if s:
            s = s.capitalize()
        out.append(s)
    return out

def to_int_list(items):
    return [int(item.strip()) for item in items if item.strip().isdigit()]


def load_and_process_excel(file_path='dp/d.xlsx'):
    """
    Load and process Excel file data.
    
    Args:
        file_path (str): Path to the Excel file
        
    Returns:
        tuple: (processed_dataframe, categories_list)
    """
    # Read the Excel file, using the first row as column headers
    df = pd.read_excel(file_path, header=0)

    for col in ['Days', 'Category']:
        if col in df.columns:
            df[col] = df[col].astype(str).str.split(',')
            df[col] = df[col].apply(strip_list)

    if 'Level' in df.columns:
        df['Level'] = df['Level'].astype(str).str.split(',')
        df['Level'] = df['Level'].apply(to_int_list)

    df['Category'] = df['Category'].replace('', np.nan)
    df['Location'] = df['Location'].replace('', np.nan)
    cdf = df.dropna(subset=['Category'])
    categories = (
        cdf['Category']
        .explode()
        .map(lambda x: x.strip())
        .dropna()
        .loc[lambda s: (s != '') & (s.str.lower() != 'nan')]
        .unique()
        .tolist()
    )
    
    return df, categories

def check_and_update_data():
    """Check Dropbox for updates and reload data if the file has changed."""
    dropbox_metadata = dbx.files_get_metadata('/d.xlsx')
    print(f"Dropbox modified: {dropbox_metadata.server_modified}")
    print(f"Dropbox content_hash: {dropbox_metadata.content_hash}")
    local_file_path = 'dp/d.xlsx'
    try:
        local_hash = dropbox_content_hash(local_file_path)
        print(f"Local file hash: {local_hash}")
        
        # Compare hashes
        if local_hash == dropbox_metadata.content_hash:
            print("✅ Files are identical!")
        else:
            print("❌ Files differ!")
            print("Downloading the latest file from Dropbox...")
            dbx.files_download_to_file('dp/d.xlsx', '/d.xlsx')
            print("Download complete.")
            
            # Update global variables
            global df, categories
            df, categories = load_and_process_excel()
            print("✅ Data reloaded successfully!")
            load_img_from_excel()
    except FileNotFoundError:
        print(f"Local file '{local_file_path}' not found. Download it first.")
        
        
def load_img_from_excel():
    output_folder = "static/img_tmp"

    # Clean the output folder if it exists, then recreate it
    if os.path.exists(output_folder):
        shutil.rmtree(output_folder)
    os.makedirs(output_folder, exist_ok=True)

    wb = load_workbook('dp/d.xlsx')
    sheet = wb['Sheet1']
    image_loader = SheetImageLoader(sheet)

    # Loop through all rows in column H (e.g., H2 to H100)
    for row in range(2, sheet.max_row + 1):
        cell = f'H{row}'
        img_name = row - 2  # Adjusting to start from 0 for image naming
        if image_loader.image_in(cell):
            image = image_loader.get(cell)
            image.save(os.path.join(output_folder, f'{img_name}.png'))
            print(f"Saved image in {cell} as {output_folder}/{img_name}.png")
    
    print("✅ Pictures reloaded successfully!")
    



initialize_dropbox_interactive()
# Check for updates in data on startup
check_and_update_data()

# Load initial data
df, categories = load_and_process_excel()

app = Flask(__name__)


@app.route('/', methods=['GET'])
def index():
    # Collect selected levels, days, and categories from query parameters

    selected_days = [day for day in ["Ma", "Ti", "Ke", "To", "Pe"] if request.args.get(day) == "True"]
    
    # Collect individual lvlN keys (if present) and group values submitted under 'lvl_group'
    selected_levels = set(
        int(key.replace('lvl', ''))
        for key in request.args
        if key.startswith('lvl') and request.args.get(key) == "True"
    )

    # request.args.getlist('lvl_group') returns multiple selected group values (e.g. "1,2")
    for group_val in request.args.getlist('lvl_group'):
        for part in group_val.split(','):
            part = part.strip()
            if part.isdigit():
                selected_levels.add(int(part))

    # Use a sorted list downstream (same shape as before)
    selected_levels = sorted(selected_levels)
    
    selected_locations = [loc for loc in df['Location'].unique() if request.args.get(loc) == "True"]

    # Debugging help: print raw and parsed values so we can spot encoding/parse issues
    try:
        print("DEBUG request.args:", dict(request.args))
        print("DEBUG lvl_group raw:", request.args.getlist('lvl_group'))
        print("DEBUG selected_levels (after parse):", selected_levels)
    except Exception:
        pass
    
    selected_categories = [cat for cat in categories if request.args.get(cat) == "True"]

    # Show no data if no filters are selected
    if not selected_levels and not selected_days and not selected_categories:
        df_filtered = df.copy() #df.iloc[0:0]  # Empty DataFrame with same columns
    else:
        df_filtered = df.copy()
        # Apply filters in the order: Category -> Level -> Day
        if selected_categories and not df_filtered.empty:
            df_filtered = df_filtered[df_filtered['Category'].apply(lambda cats: any(cat in cats for cat in selected_categories))]
        if selected_levels and not df_filtered.empty:
            df_filtered = df_filtered[df_filtered['Level'].apply(lambda levels: any(lvl in levels for lvl in selected_levels))]
        if selected_days and not df_filtered.empty:
            df_filtered = df_filtered[df_filtered['Days'].apply(lambda days: any(day in days for day in selected_days))]
        if selected_locations and not df_filtered.empty:
            df_filtered = df_filtered[df_filtered['Location'].apply(lambda locs: any(loc in str(locs) for loc in selected_locations))]
            
    return render_template(
      'index.html',
      # Pass a concrete list so the value can be iterated multiple times in templates
      aste=list(enumerate(["1. Luokka", "2. Luokka", "3. Luokka", "4. Luokka", "5. Luokka",
          "6. Luokka", "7. Luokka", "8. Luokka", "9. Luokka", "2. Aste"])),
        selected_levels=selected_levels,
        selected_days=selected_days,
        selected_categories=selected_categories,
        selected_locations=selected_locations,
        args=request.args,
        df=df_filtered.to_html(classes='data', header="true", index=True, justify='center'),
        rowItems=df_filtered.itertuples(name=None),
        categories=categories,
        locations=df['Location'].unique()
    )

@app.route("/test", methods=['GET'])
def test():
    return df.to_html(classes='data', header="true")
    # return render_template('test.html')
    
    
@app.route('/webhook', methods=['GET'])
def verify():
    '''Respond to the webhook verification (GET request) by echoing back the challenge parameter.'''
    if DP_ALLOW_NEW_WEBHOOKS:
        resp = Response(request.args.get('challenge'))
        resp.headers['Content-Type'] = 'text/plain'
        resp.headers['X-Content-Type-Options'] = 'nosniff'
        return resp
    else:
        return Response("New webhooks are not allowed", status=403)

@app.route('/webhook', methods=['POST'])
def webhook_post():
    try:
        print("=== Webhook POST Request ===")
        print("Headers:", dict(request.headers))
        print("JSON Data:", request.get_json())
        print("Raw Data:", request.get_data(as_text=True))
        
        signature = request.headers.get('X-Dropbox-Signature')
        print("X-Dropbox-Signature:", signature)
        
        if APP_SECRET is None:
            print("ERROR: APP_SECRET is None!")
            return Response("Configuration Error", status=500)
            
        if signature is None:
            print("ERROR: X-Dropbox-Signature header missing!")
            return Response("Missing Signature", status=400)
        
        x = hmac.compare_digest(signature, hmac.new(APP_SECRET.encode(), request.data, hashlib.sha256).hexdigest())
        if x: 
            print(colored("=== Signature valid! ===", "green"))
            check_and_update_data()
        else:
            print(colored("ERROR: Invalid signature!", "red"))
            return Response("Invalid Signature", status=403)

        return Response("OK", status=200)
        
    except Exception as e:
        print("ERROR:", str(e))
        return Response(f"Error: {str(e)}", status=500)
    
@app.errorhandler(404)
def page_not_found(e):
    # Check if the request was for a missing image in img_tmp
    # print(request.headers.get('Accept'))
    if request.path.startswith('/static/img_tmp/') and request.path.endswith('.png'):
        # Return a generic image from your static folder
        return send_from_directory('static', 'generic.jpg'), 307
    # Otherwise, show the normal 404 page
    return render_template('404.html'), 404

if __name__ == '__main__':
    app.run(debug=False)