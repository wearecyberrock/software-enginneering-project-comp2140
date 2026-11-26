"""Run ONLY Randre's pages (F-01 tracking + F-02 data entry) on their own.

Why this exists: `python app.py` loads all five members' folders, so it cannot start while
any one of them has a problem. This small runner loads just randre_fearon/, so you can try
your pages (and take screenshots for the test plan) at any time.

Run it from the repo root:
    python -m randre_fearon.run_local
Then open:
    http://127.0.0.1:5000/tracking/        (F-01)
    http://127.0.0.1:5000/inventory/add    (F-02)

The team's sample data (shared/seed_data.sql) is loaded the first time, when the database is
empty. Links to other members' pages in the top menu show "Not Found" here - that is expected.
"""

import os

from flask import Flask, redirect, send_from_directory

from randre_fearon import randre_bp
from shakir_russell import shakir_bp
from shared.config import Config
from shared.database import db
from shared.models import Vehicle

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))


def load_sample_data():
    """Run shared/seed_data.sql (3 sample vehicles + shipments such as KJ-BOL-2026-001)."""
    with open(os.path.join(ROOT, "shared", "seed_data.sql"), encoding="utf-8") as sql_file:
        sql = sql_file.read()
    connection = db.engine.raw_connection()
    try:
        connection.executescript(sql)
        connection.commit()
    finally:
        connection.close()


def create_local_app(config_object=Config, load_samples=True):
    """Build a Flask app that has only Randre's blueprint plus the shared theme files."""
    app = Flask(
        __name__,
        root_path=ROOT,  # same root as app.py, so the uploads/ folder is shared
        instance_path=os.path.join(ROOT, "instance"),  # ...and so is the database (instance/karmanjahni.db)
        template_folder=os.path.join(ROOT, "shared", "templates"),
    )
    app.config.from_object(config_object)
    db.init_app(app)

    with app.app_context():
        db.create_all()
        if load_samples and Vehicle.query.count() == 0:
            load_sample_data()

    @app.route("/resources/<path:filename>")
    def serve_resources(filename):
        return send_from_directory(os.path.join(ROOT, "resources"), filename)

    @app.route("/")
    def home():
        return redirect("/tracking/")

    app.register_blueprint(randre_bp)
    app.register_blueprint(shakir_bp)
    return app


if __name__ == "__main__":
    create_local_app().run(debug=True, host="127.0.0.1", port=5000)
