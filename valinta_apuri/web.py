import os
from datetime import datetime

import numpy as np
from flask import Flask, Response, current_app, make_response, render_template, request, send_from_directory
from flask_compress import Compress
from flask_htmx import HTMX
from werkzeug.middleware.proxy_fix import ProxyFix

from valinta_apuri.config import Settings
from valinta_apuri.filters import filter_workshops, parse_filters
from valinta_apuri.snapshot_store import RedisSnapshotStore, SnapshotCache


def create_app():
    settings = Settings.from_environment()
    store = RedisSnapshotStore(settings)
    store.wait_until_available()
    cache = SnapshotCache(store, settings.web_refresh_interval_seconds)
    cache.start()
    cache.wait_for_initial_load(timeout=5)

    project_root = os.path.dirname(os.path.dirname(__file__))
    app = Flask(
        __name__,
        template_folder=os.path.join(project_root, "templates"),
        static_folder=os.path.join(project_root, "static"),
        static_url_path="/static",
    )
    app.extensions["valinta_cache"] = cache
    app.extensions["valinta_htmx"] = HTMX(app)
    Compress(app)
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)
    app.jinja_env.tests["nan"] = is_nan

    register_routes(app)
    return app


def is_nan(value):
    try:
        return np.isnan(value)
    except (TypeError, ValueError):
        return False


def get_snapshot():
    return current_app.extensions["valinta_cache"].get()


def get_last_updated():
    updated_at = get_snapshot().updated_at
    if not updated_at:
        return None
    return datetime.fromtimestamp(updated_at).strftime("%d.%m.%Y %H:%M:%S")


def static_url(filename):
    app = current_app
    file_path = os.path.join(app.static_folder, filename)
    if filename == "style.css" and not os.path.exists(file_path):
        file_path = os.path.join(app.template_folder, filename)
    if not os.path.exists(file_path):
        return f"/static/{filename}"
    return f"/static/{filename}?v={int(os.path.getmtime(file_path))}"


def register_routes(app):
    @app.route("/", methods=["GET"])
    def index():
        hints = [
            ("Link", f"<{static_url('style.css')}>; rel=preload; as=style"),
            ("Link", f"<{static_url('BwGradual-Regular.woff2')}>; rel=preload; as=font; crossorigin"),
            ("Link", f"<{static_url('BG.webp')}>; rel=preload; as=image"),
        ]
        if "wsgi.early_hints" in request.environ:
            request.environ["wsgi.early_hints"](hints)

        snapshot = get_snapshot()
        dataframe = snapshot.dataframe.copy().sort_values(by=["Workshop"])
        response = make_response(render_template(
            "index.html",
            categories=snapshot.categories,
            rowItems=dataframe.itertuples(name=None),
            links=snapshot.links,
            last_updated=get_last_updated(),
        ))
        for name, value in hints:
            response.headers.add(name, value)
        return response

    @app.route("/submit", methods=["POST"])
    def submit():
        if current_app.extensions["valinta_htmx"]:
            snapshot = get_snapshot()
            selection = parse_filters(request.form, snapshot.dataframe, snapshot.categories)
            dataframe = filter_workshops(snapshot.dataframe, selection).sort_values(by=["Workshop"])
            return render_template(
                "partials/valikko_kortit.html",
                aste=list(enumerate([
                    "1. Luokka", "2. Luokka", "3. Luokka", "4. Luokka", "5. Luokka",
                    "6. Luokka", "7. Luokka", "8. Luokka", "9. Luokka", "2. aste",
                ])),
                selected_levels=selection.levels,
                selected_days=selection.days,
                selected_categories=selection.categories,
                selected_locations=selection.locations,
                args=request.form,
                df=dataframe.to_html(classes="data", header="true", index=True, justify="center"),
                rowItems=dataframe.itertuples(name=None),
                categories=snapshot.categories,
                locations=snapshot.dataframe["Location"].unique(),
                last_updated=get_last_updated(),
                links=snapshot.links,
            )

    @app.after_request
    def add_cache_headers(response):
        if request.path.startswith("/static/"):
            response.cache_control.no_cache = None
            response.cache_control.max_age = 86400 * 365
            response.cache_control.public = True
        return response

    @app.context_processor
    def utility_processor():
        return {"static_url": static_url, "last_updated": get_last_updated}

    @app.route("/static/style.css")
    def serve_dynamic_css():
        response = Response(render_template("style.css"), content_type="text/css")
        response.cache_control.no_cache = None
        response.cache_control.max_age = 86400 * 365
        response.cache_control.public = True
        return response

    @app.route("/robots.txt")
    @app.route("/sitemap.xml")
    def static_from_root():
        return send_from_directory(current_app.static_folder, request.path[1:])

    @app.errorhandler(404)
    def page_not_found(error):
        if request.path.startswith("/static/img_cur/") and request.path.endswith(".webp"):
            return send_from_directory(current_app.static_folder, "generic.jpg"), 307
        return render_template("404.html"), 404
