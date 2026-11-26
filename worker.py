"""
Cloudflare Python Worker entrypoint for the Karmanjahni Flask application.

Wraps `app.create_app()` with Cloudflare's built-in WSGI adapter (`workers.wsgi`)
so the full integrated Flask app runs on Cloudflare Workers without changing
local development (`flask --app app run`) or pytest tests.
"""

import hashlib
import hmac
import os

from sqlalchemy.pool import StaticPool
import werkzeug.security as _werkzeug_security

# Pyodide's WebAssembly Python build omits OpenSSL's scrypt and pbkdf2_hmac.
# Provide a pure-Python RFC 2898 pbkdf2_hmac polyfill (using stdlib hmac + sha256)
# and use 1000 iterations on Cloudflare Workers so login stays well within the
# Worker free-tier CPU budget while remaining 100% compatible with Werkzeug.
if not hasattr(hashlib, "pbkdf2_hmac"):

    def _pure_pbkdf2_hmac(hash_name, password, salt, iterations, dklen=None):
        digest_mod = getattr(hashlib, hash_name)
        hlen = digest_mod().digest_size
        if dklen is None:
            dklen = hlen
        out = bytearray()
        block_index = 1
        while len(out) < dklen:
            u = hmac.new(
                password, salt + block_index.to_bytes(4, "big"), digest_mod
            ).digest()
            t = bytearray(u)
            for _ in range(iterations - 1):
                u = hmac.new(password, u, digest_mod).digest()
                for i in range(hlen):
                    t[i] ^= u[i]
            out.extend(t)
            block_index += 1
        return bytes(out[:dklen])

    hashlib.pbkdf2_hmac = _pure_pbkdf2_hmac

if not hasattr(hashlib, "scrypt"):
    _orig_generate_password_hash = _werkzeug_security.generate_password_hash

    def _wasm_generate_password_hash(password, method="pbkdf2:sha256:1000", salt_length=16):
        if method in ("scrypt", "pbkdf2:sha256"):
            method = "pbkdf2:sha256:1000"
        return _orig_generate_password_hash(password, method=method, salt_length=salt_length)

    _werkzeug_security.generate_password_hash = _wasm_generate_password_hash

# Default to in-memory SQLite on Cloudflare Workers so there are zero filesystem
# permission or /tmp-reset issues between deploy snapshot and runtime requests.
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("UPLOAD_FOLDER", "/tmp/uploads")

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
    """Ensure tables, duty schedule, demo records, and testaccount exist on first request."""
    global _seeded
    if _seeded:
        return
    initialize_inventory()
    created_accounts = seed_demo()
    demo_password = os.environ.get("DEMO_PASSWORD", "testpassword")
    demo_hash = _werkzeug_security.generate_password_hash(
        demo_password, method="pbkdf2:sha256:1000"
    )
    if created_accounts:
        for username, _ in created_accounts:
            user = User.query.filter_by(username=username).first()
            if user is not None:
                user.password_hash = demo_hash

    # Create/ensure the requested owner login: testaccount / testpassword
    test_user = User.query.filter_by(username="testaccount").first()
    if test_user is None:
        db.session.add(
            User(
                username="testaccount",
                email="testaccount@karmanjahni.com",
                password_hash=demo_hash,
                role="owner",
                is_active=True,
            )
        )
    else:
        test_user.password_hash = demo_hash
        test_user.role = "owner"
        test_user.is_active = True

    db.session.commit()
    _seeded = True


# Expose the Flask WSGI app as the Cloudflare Worker Default entrypoint
try:
    from workers import wsgi

    Default = wsgi.entrypoint(app)
except ModuleNotFoundError:
    Default = None
