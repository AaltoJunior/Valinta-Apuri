from flask import (Flask, redirect, render_template, request,
                   send_from_directory, url_for, abort, Response)
from flask_compress import Compress

import pandas as pd
import numpy as np
from dotenv import load_dotenv
import os

from termcolor import colored

import time
from datetime import datetime

import threading

import os

from time import sleep
from pathlib import Path



def data_update_loop():
    # This function runs in a separate thread and periodically checks if the data files have been updated.
    global time_old
    while True:
        global df, categories
        time_new = os.path.getmtime("./tmp/data.pkl")
        if time_new > time_old:
            print("Changes detected in data.pkl, reloading...")
            df = pd.read_pickle("./tmp/data.pkl")
            cat = pd.read_pickle("./tmp/categories.pkl")
            categories = cat.tolist()
            time_old = time_new
            data_loaded.set()
        time.sleep(60)  # Check every 60 seconds



# Wait until both files exist
while not (Path("./tmp/data.pkl").exists() and Path("./tmp/categories.pkl").exists()):
    print("Waiting for data files to be created...")
    time.sleep(1)


df = pd.DataFrame()  # Placeholder until we load real data
categories = [] # Placeholder until we load real data

# Start the polling in a separate thread so it doesn't block the Flask app
time_old = 0 # Initialize to 0 so the first check will always load the data
data_loaded = threading.Event()
poller_thread = threading.Thread(target=data_update_loop, daemon=True)
poller_thread.start()

data_loaded.wait(timeout=5)  # Wait until the initial data is loaded before starting the Flask app


app = Flask(__name__)
Compress(app) # Enable gzip compression for responses

@app.route('/', methods=['GET'])
def index():
    # Serve early hints for preloading critical assets like .css and fonts
    if 'wsgi.early_hints' in request.environ:
        request.environ['wsgi.early_hints']([
            ('Link', f'<{static_url("style.css")}>; rel=preload; as=style'),
            ('Link', f'<{static_url("BwGradual-Regular.woff2")}>; rel=preload; as=font; crossorigin'),
            ('Link', f'<{static_url("BG.webp")}>; rel=preload; as=image'),
    ])
    
    global time_old
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
        locations=df['Location'].unique(),
        last_updated=datetime.fromtimestamp(time_old).strftime('%Y-%m-%d %H:%M:%S')
    )

# Route to get all data in a simple table format (used for debugging and testing) disabled by default
# @app.route("/test", methods=['GET'])
# def test():
#     return df.to_html(classes='data', header="true")

@app.after_request
def add_cache_headers(response):
    if request.path.startswith('/static/'):
        response.cache_control.no_cache = None
        response.cache_control.max_age = 86400 * 3
        response.cache_control.public = True
    return response

def static_url(filename):
    filepath = os.path.join(app.static_folder, filename)
    if not os.path.exists(filepath):
        return f'/static/{filename}'
    timestamp = int(os.path.getmtime(filepath))
    return f'/static/{filename}?v={timestamp}'

@app.context_processor
def utility_processor():
    return dict(static_url=static_url)


# Route for robots.txt and sitemap.xml to be accessible    
@app.route('/robots.txt')
@app.route('/sitemap.xml')
def static_from_root():
    return send_from_directory(app.static_folder, request.path[1:])

# Custom 404 error handler to serve a generic image for missing images in img_cur, and a friendly 404 page for other missing resources
@app.errorhandler(404)
def page_not_found(e):
    # Check if the request was for a missing image in img_cur
    if request.path.startswith('/static/img_cur/') and request.path.endswith('.jpg'):
        # Return a generic image from your static folder
        return send_from_directory('static', 'generic.jpg'), 307
    # Otherwise, show the normal 404 page
    return render_template('404.html'), 404

if __name__ == '__main__':
    app.run(debug=False, host="0.0.0.0", port=80)