"""
==============================================================================
INTRODUCTION — shakir_russell/routes.py
==============================================================================
Author:      Shakir Russell (Student ID: 620181663)
Course:      COMP2140 — Introduction to Software Engineering
Feature:     F-06 Shipment Status & ETA Updating + Staff Authentication

What this file does:
    This file defines all web URLs (routes) for Shakir's section:
    - GET/POST /shipments/manage        -> Search a shipment by BoL, view all
                                           active shipments, and update status/ETA.
    - POST     /shipments/update/<bol>  -> Direct update endpoint for a specific BoL.
    - POST     /shipments/delete/<bol>  -> Soft-delete a shipment (SRS §3.2).
    - GET/POST /staff/login             -> Staff portal login page (RBAC).
    - POST     /staff/logout            -> Clears the staff session and logs out.

Libraries used:
    - flask (current_app, redirect, render_template, request, session, url_for):
      * `render_template` loads our HTML files and fills in dynamic data.
      * `request` reads URL query parameters (GET) and submitted form fields (POST).
      * `session` stores the logged-in staff member's ID, username, and role.
      * `redirect` & `url_for` send the browser to another route safely.
      * `current_app` lets us check if other team Blueprints are registered.

What this file pulls from the shared/group code:
    - `shared/auth.py` -> `role_required`: Shared decorator that blocks
      unauthenticated users (redirects to /staff/login) and blocks unauthorized
      roles (returns HTTP 403 Forbidden). Owner is always allowed.
    - `shakir_russell/__init__.py` -> `shakir_bp`: Our Blueprint object.
    - `shakir_russell/status_update_service.py`: Our service functions that
      talk to `shared/database.py` and `shared/models.py`.
    - `ashaya_watts` (`ashaya_bp.customer_home`): When staff log out, we
      redirect them to Ashaya's public storefront (if registered in `app.py`).
==============================================================================
"""

# Import Flask tools needed to handle HTTP requests, sessions, templates, and redirects
from flask import current_app, redirect, render_template, request, session, url_for

# Pull the shared Role-Based Access Control (RBAC) decorator from shared/auth.py (SRS §3.2)
from shared.auth import role_required

# Pull our Blueprint object from shakir_russell/__init__.py
from shakir_russell import shakir_bp

# Pull our F-06 service functions and status constants from status_update_service.py
from shakir_russell.status_update_service import (
    STATUS_BADGE_CLASSES,
    STATUS_CHOICES,
    authenticate_staff,
    find_active_shipment,
    get_all_active_shipments,
    soft_delete_shipment,
    update_shipment_status,
)


@shakir_bp.route("/shipments/manage", methods=["GET", "POST"])
@role_required("purchasing_manager", "internal_staff")  # Only Owner, Purchasing Manager, or Internal Staff
def manage_shipments():
    """F-06: Search a shipment by BoL and update its transit status and ETA."""
    # Variable `error_message`: stores any validation or lookup error to display on the page
    error_message = None

    # Variable `success_message`: stores a confirmation message after saving or deleting
    success_message = None

    # Variable `selected_shipment`: the Shipment object currently loaded in the edit form (or None)
    selected_shipment = None

    # Variable `search_bol`: the Bill of Lading typed into the search box (from URL ?bol=...)
    search_bol = request.args.get("bol", "").strip()[:100]

    # Handle form submission when staff clicks "Save Shipment Update" (HTTP POST)
    if request.method == "POST":
        # Read the Bill of Lading number from the submitted form
        # Variable `form_bol`: BoL of the shipment being updated
        form_bol = request.form.get("bill_of_lading", "").strip()

        # Read the newly selected transit status from the dropdown (SR-1)
        # Variable `new_status`: e.g., "In Transit", "Delayed", "Arrived", or "Cleared"
        new_status = request.form.get("status", "").strip()

        # Read the new ETA date string from the date picker (SR-2)
        # Variable `new_eta`: e.g., "2026-12-15" or "" if left blank
        new_eta = request.form.get("eta_date", "").strip()

        # Read the optional delay reason text input (used when status is "Delayed")
        # Variable `delay_reason`: explanation of weather/port delay
        delay_reason = request.form.get("delay_reason", "").strip()

        # Keep the BoL in the search box in case we need to re-render with an error
        search_bol = form_bol

        try:
            # Call our service function to validate and save the update to the database (SR-3)
            # Variable `updated`: the saved Shipment object
            updated = update_shipment_status(
                bill_of_lading=form_bol,
                new_status=new_status,
                new_eta=new_eta or None,
                delay_reason=delay_reason or None,
            )
            # Redirect after POST (Post/Redirect/Get pattern) so refreshing does not re-submit
            return redirect(
                url_for(
                    "shakir_bp.manage_shipments",
                    bol=updated.bill_of_lading,
                    updated="1",
                )
            )
        except LookupError as exc:
            # Shipment was not found in the database — show error with HTTP 404 status
            error_message = str(exc)
            all_shipments = get_all_active_shipments()
            return (
                render_template(
                    "update_shipment.html",
                    search_bol=search_bol,
                    selected_shipment=None,
                    shipments=all_shipments,
                    status_choices=STATUS_CHOICES,
                    badge_classes=STATUS_BADGE_CLASSES,
                    error_message=error_message,
                    success_message=None,
                ),
                404,
            )
        except ValueError as exc:
            # Invalid status, invalid date, or invalid BoL — show error with HTTP 400 status
            error_message = str(exc)
            selected_shipment = find_active_shipment(form_bol)
            all_shipments = get_all_active_shipments()
            return (
                render_template(
                    "update_shipment.html",
                    search_bol=search_bol,
                    selected_shipment=selected_shipment,
                    shipments=all_shipments,
                    status_choices=STATUS_CHOICES,
                    badge_classes=STATUS_BADGE_CLASSES,
                    error_message=error_message,
                    success_message=None,
                ),
                400,
            )

    # Handle normal page load or BoL search (HTTP GET)
    if search_bol:
        # Look up the searched Bill of Lading in the shared database
        selected_shipment = find_active_shipment(search_bol)
        # If the user searched for a BoL that does not exist (or was soft-deleted), show a message
        if selected_shipment is None:
            error_message = f"Shipment '{search_bol}' was not found."

    # Check if we just redirected here after a successful update (?updated=1)
    if request.args.get("updated") == "1" and selected_shipment is not None:
        success_message = (
            f"Shipment {selected_shipment.bill_of_lading} updated to "
            f"'{selected_shipment.status}' (ETA: {selected_shipment.eta_date or 'Not set'})."
        )

    # Check if we just redirected here after a successful soft-delete (?deleted=<bol>)
    # Variable `deleted_bol`: BoL that was just hidden from active inventory
    deleted_bol = request.args.get("deleted", "").strip()
    if deleted_bol:
        success_message = (
            f"Shipment {deleted_bol} has been archived (soft-deleted) and hidden from active views."
        )

    # Variable `all_shipments`: list of all active shipments for the quick-select table
    all_shipments = get_all_active_shipments()

    # Render templates/update_shipment.html with all data needed by the page
    return render_template(
        "update_shipment.html",
        search_bol=search_bol,
        selected_shipment=selected_shipment,
        shipments=all_shipments,
        status_choices=STATUS_CHOICES,
        badge_classes=STATUS_BADGE_CLASSES,
        error_message=error_message,
        success_message=success_message,
    )


@shakir_bp.route("/shipments/update/<bol>", methods=["POST"])
@role_required("purchasing_manager", "internal_staff")  # Only Owner, Purchasing Manager, or Internal Staff
def update_shipment_by_bol(bol):
    """F-06: Direct POST route to update one shipment using the BoL in the URL."""
    # Read updated values from the submitted form
    # Variable `new_status`: new transit status from the dropdown
    new_status = request.form.get("status", "").strip()

    # Variable `new_eta`: new estimated arrival date (YYYY-MM-DD) or blank
    new_eta = request.form.get("eta_date", "").strip()

    # Variable `delay_reason`: optional reason when status is Delayed
    delay_reason = request.form.get("delay_reason", "").strip()

    try:
        # Save the update to the shared database using our service function
        updated = update_shipment_status(
            bill_of_lading=bol,
            new_status=new_status,
            new_eta=new_eta or None,
            delay_reason=delay_reason or None,
        )
    except LookupError as exc:
        # Return HTTP 404 if the BoL does not exist
        return (
            render_template(
                "update_shipment.html",
                search_bol=bol,
                selected_shipment=None,
                shipments=get_all_active_shipments(),
                status_choices=STATUS_CHOICES,
                badge_classes=STATUS_BADGE_CLASSES,
                error_message=str(exc),
                success_message=None,
            ),
            404,
        )
    except ValueError as exc:
        # Return HTTP 400 if status or date was invalid
        return (
            render_template(
                "update_shipment.html",
                search_bol=bol,
                selected_shipment=find_active_shipment(bol),
                shipments=get_all_active_shipments(),
                status_choices=STATUS_CHOICES,
                badge_classes=STATUS_BADGE_CLASSES,
                error_message=str(exc),
                success_message=None,
            ),
            400,
        )

    # Redirect back to the manage page with a green confirmation banner
    return redirect(
        url_for(
            "shakir_bp.manage_shipments",
            bol=updated.bill_of_lading,
            updated="1",
        )
    )


@shakir_bp.route("/shipments/delete/<bol>", methods=["POST"])
@role_required("purchasing_manager", "internal_staff")  # Only Owner, Purchasing Manager, or Internal Staff
def delete_shipment_by_bol(bol):
    """SRS §3.2 Soft Delete: Hide an outdated shipment without permanently erasing it."""
    try:
        # Call our service function to set is_deleted=True and deleted_at=now
        archived = soft_delete_shipment(bol)
    except LookupError as exc:
        # Return HTTP 404 if the shipment could not be found
        return (
            render_template(
                "update_shipment.html",
                search_bol=bol,
                selected_shipment=None,
                shipments=get_all_active_shipments(),
                status_choices=STATUS_CHOICES,
                badge_classes=STATUS_BADGE_CLASSES,
                error_message=str(exc),
                success_message=None,
            ),
            404,
        )

    # Redirect back to the manage page and show the soft-delete confirmation message
    return redirect(
        url_for(
            "shakir_bp.manage_shipments",
            deleted=archived.bill_of_lading,
        )
    )


@shakir_bp.route("/staff/login", methods=["GET", "POST"])
def staff_login():
    """Staff login entry point for Role-Based Access Control (SRS §3.2)."""
    # If the staff member is already logged in, send them straight to the shipment page
    if "user_id" in session:
        return redirect(url_for("shakir_bp.manage_shipments"))

    # Variable `error_message`: shown if username or password is wrong
    error_message = None

    # Variable `entered_username`: remembers the typed username if login fails
    entered_username = ""

    # Handle login form submission (HTTP POST)
    if request.method == "POST":
        # Read username and password from the submitted HTML form
        entered_username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        # Verify credentials using our service function against the shared `users` table
        # Variable `user`: authenticated User object, or None if invalid
        user = authenticate_staff(entered_username, password)

        if user is not None:
            # Clear any old session data before starting the new login session
            session.clear()
            # Save the keys that `shared/auth.py` checks (`user_id` and `user_role`)
            session["user_id"] = user.id
            session["username"] = user.username
            session["user_role"] = user.role
            # Redirect the signed-in staff member to the F-06 shipment management page
            return redirect(url_for("shakir_bp.manage_shipments"))

        # Login failed — prepare an error message and return HTTP 401 Unauthorized
        error_message = "Invalid username or password. Please try again."
        return (
            render_template(
                "staff_login.html",
                error_message=error_message,
                entered_username=entered_username,
            ),
            401,
        )

    # Normal GET request — display the empty staff login form
    return render_template(
        "staff_login.html",
        error_message=error_message,
        entered_username=entered_username,
    )


@shakir_bp.route("/staff/logout", methods=["POST"])
def staff_logout():
    """Log out the current staff member by clearing the Flask session."""
    # Remove user_id, username, and user_role from the session cookie
    session.clear()

    # If Ashaya's public storefront Blueprint is registered (full app), redirect there
    if "ashaya_bp.customer_home" in current_app.view_functions:
        return redirect(url_for("ashaya_bp.customer_home"))

    # Otherwise (during isolated testing), redirect back to the staff login page
    return redirect(url_for("shakir_bp.staff_login"))
