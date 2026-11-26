"""Public Routes for F-04 Customer Interface Search (Restricted Public View)."""

from flask import render_template, request, jsonify, abort
from ashaya_watts import ashaya_bp
from ashaya_watts.public_catalog_service import search_public_inventory, get_public_vehicle


@ashaya_bp.route("/", methods=["GET"])
@ashaya_bp.route("/browse", methods=["GET"])
def customer_home():
    """F-04: Public dealership landing page with make/model search."""
    return inventory_page("available")


@ashaya_bp.get("/upcoming-arrivals")
def upcoming_arrivals():
    return inventory_page("upcoming")


def inventory_page(section):
    query = request.args.get("q", "")
    vehicles = search_public_inventory(query, section, request.args.get("transmission", ""))
    return render_template("customer_home.html", query=query, vehicles=vehicles, section=section)


@ashaya_bp.route("/vehicle/<int:vehicle_id>", methods=["GET"])
def customer_vehicle_detail(vehicle_id: int):
    """F-04: Public-only vehicle detail page (NO internal purchase costs or BoL)."""
    vehicle = get_public_vehicle(vehicle_id)
    if vehicle is None:
        abort(404)
    return render_template("customer_vehicle_detail.html", vehicle=vehicle)


@ashaya_bp.route("/api/public/vehicles", methods=["GET"])
def api_public_vehicles():
    """F-04: Public JSON search endpoint (strictly sanitized fields only)."""
    query = request.args.get("q", "")
    section = request.args.get("section")
    if section not in (None, "available", "upcoming"):
        abort(400)
    return jsonify(search_public_inventory(query, section, request.args.get("transmission", "")))
