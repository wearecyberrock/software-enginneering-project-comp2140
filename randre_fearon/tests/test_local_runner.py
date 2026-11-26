"""Checks the stand-alone runner (python -m randre_fearon.run_local) and the team's sample data."""

import os

from randre_fearon.run_local import ROOT, create_local_app
from shared.config import TestConfig
from shared.database import db


def test_local_runner_loads_sample_data_and_serves_both_pages():
    app = create_local_app(TestConfig, load_samples=True)
    client = app.test_client()
    try:
        # The database lives in <repo>/instance/ (like app.py), never inside randre_fearon/.
        assert app.instance_path == os.path.join(ROOT, "instance")

        # shared/seed_data.sql: KJ-BOL-2026-001 is the Tacoma (In Transit, ETA 2026-12-30) ...
        html = client.get("/tracking/?bol=KJ-BOL-2026-001").get_data(as_text=True)
        assert "In Transit" in html and "2026-12-30" in html and "Toyota Tacoma Pickup" in html
        # ... and KJ-BOL-2026-002 is delayed, so it must be highlighted.
        html = client.get("/tracking/?bol=KJ-BOL-2026-002").get_data(as_text=True)
        assert "badge-delayed" in html and "2026-12-18" in html

        assert client.get("/inventory/add").status_code == 200
        assert client.get("/").status_code == 302                              # home -> /tracking/
        assert client.get("/resources/design/theme.css").status_code == 200    # shared brand styling loads
    finally:
        with app.app_context():
            db.session.remove()
            db.drop_all()
