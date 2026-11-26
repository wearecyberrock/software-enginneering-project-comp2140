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
_seeded = False


@app.before_request
def _ensure_demo_seeded():
    """Seed demo vehicles, FX rates, duty tiers, and staff users on the first request.

    Done lazily (not at top-level import) so Cloudflare's deploy-time memory snapshot
    never hits entropy/PRNG restrictions from password hashing or token generation.
    """
    global _seeded
    if _seeded:
        return
    created_accounts = seed_demo()
    demo_password = os.environ.get("DEMO_PASSWORD", "Karmanjahni2026!")
    if created_accounts:
        for username, _ in created_accounts:
            user = User.query.filter_by(username=username).first()
            if user is not None:
                user.password_hash = generate_password_hash(demo_password)
        db.session.commit()
    _seeded = True


# Expose the Flask WSGI app as the Cloudflare Worker Default entrypoint
Default = wsgi.entrypoint(app)
