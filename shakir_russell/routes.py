"""Routes for F-06 Shipment Status & ETA Updating and Staff Authentication."""

from flask import current_app, redirect, render_template, request, session, url_for

from shakir_russell import shakir_bp
from shakir_russell.status_update_service import (
    STATUS_BADGE_CLASSES,
    STATUS_OPTIONS,
    authenticate_staff,
    get_active_shipment,
    list_active_shipments,
    soft_delete_shipment,
    update_shipment_status,
)
from shared.auth import role_required

SHIPMENT_ADMIN_ROLES = ("owner", "purchasing_manager", "internal_staff")


def _render_manage_page(
    *,
    bol_query: str = "",
    selected=None,
    message: str | None = None,
    error: str | None = None,
    status_code: int = 200,
):
    """Render the F-06 shipment management view with consistent context."""
    shipments = list_active_shipments(bol_query)
    html = render_template(
        "update_shipment.html",
        shipments=shipments,
        selected=selected,
        bol_query=bol_query,
        status_options=STATUS_OPTIONS,
        badge_classes=STATUS_BADGE_CLASSES,
        message=message,
        error=error,
        staff_username=session.get("username", "Staff"),
        staff_role=session.get("user_role", ""),
    )
    return html, status_code


@shakir_bp.route("/shipments/manage", methods=["GET", "POST"])
@role_required(*SHIPMENT_ADMIN_ROLES)
def manage_shipments():
    """F-06: Search shipments by BoL and update transit status / ETA."""
    message = request.args.get("message")
    error = request.args.get("error")
    bol_query = request.args.get("bol", "").strip()
    selected = get_active_shipment(bol_query) if bol_query else None

    if request.method == "POST":
        bol = request.form.get("bill_of_lading", "").strip()
        new_status = request.form.get("status", "").strip()
        new_eta = request.form.get("eta_date", "").strip()
        delay_reason = request.form.get("delay_reason", "")
        try:
            selected = update_shipment_status(
                bill_of_lading=bol,
                new_status=new_status,
                new_eta=new_eta or None,
                delay_reason=delay_reason,
            )
            message = f"Updated shipment {selected.bill_of_lading} to '{selected.status}'."
        except (ValueError, LookupError) as exc:
            error = str(exc)
            selected = get_active_shipment(bol)
            return _render_manage_page(
                bol_query=bol_query,
                selected=selected,
                error=error,
                status_code=400,
            )

    if bol_query and selected is None and not error and not list_active_shipments(bol_query):
        error = f"No active shipment found matching '{bol_query}'."

    return _render_manage_page(
        bol_query=bol_query,
        selected=selected,
        message=message,
        error=error,
    )


@shakir_bp.route("/shipments/update/<bol>", methods=["GET", "POST"])
@role_required(*SHIPMENT_ADMIN_ROLES)
def update_shipment(bol: str):
    """F-06: Direct route to view or update a specific shipment by Bill of Lading."""
    shipment = get_active_shipment(bol)
    if shipment is None:
        return _render_manage_page(
            error=f"Active shipment '{bol}' was not found.",
            status_code=404,
        )

    if request.method == "POST":
        new_status = request.form.get("status", "").strip()
        new_eta = request.form.get("eta_date", "").strip()
        delay_reason = request.form.get("delay_reason", "")
        try:
            shipment = update_shipment_status(
                bill_of_lading=bol,
                new_status=new_status,
                new_eta=new_eta or None,
                delay_reason=delay_reason,
            )
            return _render_manage_page(
                selected=shipment,
                message=f"Updated shipment {shipment.bill_of_lading} to '{shipment.status}'.",
            )
        except (ValueError, LookupError) as exc:
            return _render_manage_page(
                selected=shipment,
                error=str(exc),
                status_code=400,
            )

    return _render_manage_page(selected=shipment)


@shakir_bp.route("/shipments/delete/<bol>", methods=["POST"])
@role_required(*SHIPMENT_ADMIN_ROLES)
def delete_shipment(bol: str):
    """SRS §3.2: Soft-delete a shipment record without permanently erasing history."""
    try:
        shipment = soft_delete_shipment(bol)
        return redirect(
            url_for(
                "shakir_bp.manage_shipments",
                message=f"Archived shipment {shipment.bill_of_lading} (soft-deleted).",
            )
        )
    except (ValueError, LookupError) as exc:
        return _render_manage_page(error=str(exc), status_code=404)


@shakir_bp.route("/staff/login", methods=["GET", "POST"])
def staff_login():
    """Staff login entry point for RBAC (SRS §3.2)."""
    error = None
    username = ""
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user = authenticate_staff(username, password)
        if user is None:
            error = "Invalid username or password."
            return render_template("staff_login.html", error=error, username=username), 401

        session.clear()
        session["user_id"] = user.id
        session["username"] = user.username
        session["user_role"] = user.role
        return redirect(url_for("shakir_bp.manage_shipments"))

    return render_template("staff_login.html", error=error, username=username)


@shakir_bp.route("/staff/logout", methods=["POST"])
def staff_logout():
    """Clear the active staff session and return to the public storefront (or login)."""
    session.clear()
    if "ashaya_bp.customer_home" in current_app.view_functions:
        return redirect(url_for("ashaya_bp.customer_home"))
    return redirect(url_for("shakir_bp.staff_login"))
