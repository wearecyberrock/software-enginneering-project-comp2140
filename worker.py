"""
Cloudflare Python Worker entrypoint for the Karmanjahni Flask application.

Wraps `app.create_app()` with Cloudflare's built-in WSGI adapter (`workers.wsgi`)
so the full integrated Flask app runs on Cloudflare Workers without changing
local development (`flask --app app run`) or pytest tests.
"""

import os

# Cloudflare Workers has a writable /tmp filesystem inside the Pyodide sandbox.
# Default to /tmp for SQLite and uploaded photos if no external DATABASE_URL is set.
os.environ.setdefault("DATABASE_URL", "sqlite:////tmp/karmanjahni.db")
os.environ.setdefault("UPLOAD_FOLDER", "/tmp/uploads")

from workers import wsgi  # noqa: E402
from werkzeug.security import generate_password_hash  # noqa: E402

from app import create_app  # noqa: E402
from shared.database import db  # noqa: E402
from shared.demo_data import seed_demo  # noqa: E402
from shared.models import User  # noqa: E402

app = create_app()

# Seed the demo vehicles (BOL-000, BOL-001), FX rates, duty tiers, and staff users
# automatically when the Worker starts up.
with app.app_context():
    created_accounts = seed_demo()
    # Set a known password for demo accounts on Cloudflare (override via DEMO_PASSWORD secret)
    demo_password = os.environ.get("DEMO_PASSWORD", "Karmanjahni2026!")
    if created_accounts:
        for username, _ in created_accounts:
            user = User.query.filter_by(username=username).first()
            if user is not None:
                user.password_hash = generate_password_hash(demo_password)
        db.session.commit()

# Expose the Flask WSGI app as the Cloudflare Worker Default entrypoint
Default = wsgi.entrypoint(app)
