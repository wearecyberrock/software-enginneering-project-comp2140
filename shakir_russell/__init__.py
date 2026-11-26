"""
==============================================================================
INTRODUCTION — shakir_russell/__init__.py
==============================================================================
Author:      Shakir Russell (Student ID: 620181663)
Course:      COMP2140 — Introduction to Software Engineering
Feature:     F-06 Shipment Status & ETA Updating + Staff Login (SRS §3.2)

What this file does:
    This file turns the `shakir_russell/` folder into a Python package and
    creates a Flask "Blueprint" called `shakir_bp`. A Blueprint is like a
    mini-app for my section so my routes, HTML templates, and CSS/JS files
    stay neatly separated from my teammates' folders.

Libraries used:
    - flask (Blueprint): A lightweight Python web framework. `Blueprint` lets
      us group our routes and connect them to the main `app.py` later.

What this file connects to in the group code:
    - `app.py` (main project file): Imports `shakir_bp` from this file and
      registers it with `app.register_blueprint(shakir_bp)`.
    - `shakir_russell/routes.py`: Imported at the bottom so all `@shakir_bp.route`
      URL handlers get attached to `shakir_bp`.
==============================================================================
"""

# Import Blueprint from the Flask library so we can create our feature module
from flask import Blueprint

# Create the Blueprint object for Shakir's F-06 feature and staff login
# Variable `shakir_bp`: holds the Blueprint that `app.py` will register
shakir_bp = Blueprint(
    "shakir_bp",                      # Internal name of this Blueprint in Flask
    __name__,                         # Tells Flask where this package lives on disk
    template_folder="templates",      # Look inside shakir_russell/templates/ for HTML files
    static_folder="static",           # Look inside shakir_russell/static/ for CSS and JS files
    static_url_path="/shakir/static", # URL prefix used in HTML to load our CSS/JS files
)

# Import routes.py AFTER creating `shakir_bp` so routes.py can attach its URLs to `shakir_bp`
# (The `# noqa` comment tells code linters that putting this import at the bottom is intentional)
from shakir_russell import routes  # noqa: E402, F401
