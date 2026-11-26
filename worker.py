"""
Cloudflare Python Worker entrypoint for the Karmanjahni Flask application.

Wraps `app.create_app()` with Cloudflare's built-in WSGI adapter (`workers.wsgi`)
so the full integrated Flask app runs on Cloudflare Workers without changing
local development (`flask --app app run`) or pytest tests.
"""

import os
import traceback

from sqlalchemy.pool import StaticPool

# Default to in-memory SQLite on Cloudflare Workers so there are zero filesystem
# permission or /tmp-reset issues between deploy snapshot and runtime requests.
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("UPLOAD_FOLDER", "/tmp/uploads")

from werkzeug.exceptions import HTTPException  # noqa: E402
from werkzeug.security import generate_password_hash  # noqa: E402

from app import create_app  # noqa: E402
from shared.config import Config  # noqa: E402
from shared.database import db  # noqa: E402
from shared.demo_data import seed_demo  # noqa: E402
from shared.duty_schedule import initialize_inventory  # noqa: E402
from shared.models import User  # noqa: E402


class CloudflareConfig(Config):
    """Worker config that keeps one shared in-memory SQLite DB per Worker isolate."""

    if Config.SQLALCHEMY_DATABASE_URI == "sqlite:///:memory:":
        SQLALCHEMY_ENGINE_OPTIONS = {
            "poolclass": StaticPool,
            "connect_args": {"check_same_thread": False},
        }


app = create_app(CloudflareConfig)
_seeded = False


@app.before_request
def _ensure_demo_seeded():
    """Ensure tables, duty schedule, and demo records exist on the first request."""
    global _seeded
    if _seeded:
        return
    initialize_inventory()
    created_accounts = seed_demo()
    demo_password = os.environ.get("DEMO_PASSWORD", "Karmanjahni2026!")
    if created_accounts:
        for username, _ in created_accounts:
            user = User.query.filter_by(username=username).first()
            if user is not None:
                user.password_hash = generate_password_hash(demo_password)
        db.session.commit()
    _seeded = True


@app.errorhandler(Exception)
def _handle_unexpected_error(err):
    """Show exact Python traceback on unexpected 500s during Cloudflare setup."""
    if isinstance(err, HTTPException):
        return err
    return f"<pre>{traceback.format_exc()}</pre>", 500


# Expose the Flask WSGI app as the Cloudflare Worker Default entrypoint
try:
    from workers import wsgi

    Default = wsgi.entrypoint(app)
except ModuleNotFoundError:
    Default = None
