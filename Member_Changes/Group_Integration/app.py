"""
Karmanjahni Shipment and Inventory Tracking System
Main Flask Application (Final Fusion Entrypoint)

Registers all 5 team member Blueprints and serves shared design resources.
"""

import os
from flask import Flask, send_from_directory
from shared.config import Config
from shared.demo_data import seed_demo_command
from shared.database import db

# Import each team member's isolated Blueprint
from randre_fearon import randre_bp
from amanda_morgan import amanda_bp
from ashaya_watts import ashaya_bp
from tyrone_palmer import tyrone_bp
from shakir_russell import shakir_bp


def create_app(config_object=Config):
    base_dir = os.path.abspath(os.path.dirname(__file__))

    app = Flask(
        __name__,
        template_folder=os.path.join(base_dir, "shared", "templates"),
    )
    app.config.from_object(config_object)
    app.cli.add_command(seed_demo_command)

    # Initialize shared database
    db.init_app(app)
    with app.app_context():
        import shared.models  # noqa: F401
        db.create_all()

    # Serve shared design resources (theme.css, logo, tokens) at /resources/<path>
    resources_dir = os.path.join(base_dir, "resources")

    @app.route("/resources/<path:filename>")
    def serve_resources(filename):
        return send_from_directory(resources_dir, filename)

    # Register all 5 team member Blueprints
    app.register_blueprint(ashaya_bp)   # F-04: Public Customer Storefront (/, /browse)
    app.register_blueprint(randre_bp)   # F-01 & F-02: Tracking (/tracking) & Data Entry (/inventory)
    app.register_blueprint(amanda_bp)   # F-03: Sales Tablet Specs (/tablet)
    app.register_blueprint(tyrone_bp)   # F-05: Dynamic Pricing (/pricing)
    app.register_blueprint(shakir_bp)   # F-06: Shipment Status & ETA Updating (/shipments)

    return app


app = create_app()

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
