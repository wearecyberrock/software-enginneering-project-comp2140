"""Shared test setup for randre_fearon/tests (F-01 and F-02).

The tests build a tiny Flask app that contains ONLY Randre's blueprint (not app.py), so they
keep working no matter what state the other members' folders are in.
"""

import sys
from pathlib import Path

import pytest
from flask import Flask

# Make the repo root importable so `pytest randre_fearon/tests` works from any directory.
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@pytest.fixture()
def flask_app(tmp_path):
    """A fresh app with an empty in-memory database for every single test."""
    from randre_fearon import randre_bp
    from shared.config import TestConfig
    from shared.database import db
    import shared.models  # noqa: F401  (registers the tables)

    application = Flask(__name__, template_folder=str(ROOT / "shared" / "templates"))
    application.config.from_object(TestConfig)                 # in-memory SQLite
    application.config["UPLOAD_FOLDER"] = str(tmp_path / "uploads")  # photos go to a temp folder
    db.init_app(application)
    application.register_blueprint(randre_bp)

    with application.app_context():
        db.create_all()

    yield application

    with application.app_context():
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def client(flask_app):
    return flask_app.test_client()
