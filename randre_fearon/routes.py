"""Routes for F-01 (Shipment Tracking) and F-02 (Manual Data Entry)."""

from flask import redirect, render_template, request, send_from_directory, url_for

from randre_fearon import randre_bp
from randre_fearon.entry_service import (
    CATEGORY_CHOICES,
    CURRENCY_CHOICES,
    ORIGIN_COUNTRIES,
    EntryValidationError,
    save_vehicle_record,
    validate_vehicle_form,
)
from randre_fearon.photo_upload import (
    delete_photos,
    save_photos,
    upload_dir,
    validate_photos,
)
from randre_fearon.tracking_service import build_tracking_view, find_shipment_by_bol
from shared.validators import is_valid_bill_of_lading

# NOTE: /tracking/ and /inventory/add are staff routes (purchasing_manager / owner). Per
# integration/fuse_checklist.md the @role_required decorator from shared/auth.py is added to
# them at fusion. Do NOT add it to vehicle_photo(): photos also appear on the public site (F-04).


@randre_bp.route("/tracking/", methods=["GET"])
def track_shipment():
    """F-01: Render Bill of Lading search page and tracking results."""
    searched = "bol" in request.args  # False on the very first visit, so no error is shown yet
    bol = request.args.get("bol", "").strip()[:100]
    shipment = find_shipment_by_bol(bol) if searched else None
    return render_template(
        "track_shipment.html",
        bol=bol,
        searched=searched,
        result=build_tracking_view(shipment) if shipment else None,
        bol_looks_valid=is_valid_bill_of_lading(bol),
    )


@randre_bp.route("/inventory/add", methods=["GET", "POST"])
def add_vehicle():
    """F-02: Render and handle manual vehicle logging form (deposit-paid required)."""
    form, errors, photos_lost = {}, {}, False

    if request.method == "POST":
        form = request.form.to_dict()
        photo_files = [f for f in request.files.getlist("photos") if f.filename]

        # 1) Check the form fields, then the photos, and gather every problem.
        cleaned = None
        try:
            cleaned = validate_vehicle_form(form)
        except EntryValidationError as exc:
            errors.update(exc.errors)
        photo_error = validate_photos(photo_files)
        if photo_error:
            errors["photos"] = photo_error

        # 2) Only when everything is fine: store the photos, then save the vehicle + shipment.
        if not errors:
            photo_urls = save_photos(photo_files)
            cleaned["photo_urls"] = photo_urls
            try:
                vehicle = save_vehicle_record(cleaned)
            except EntryValidationError as exc:  # e.g. same Bill of Lading saved a moment ago
                delete_photos(photo_urls)
                errors.update(exc.errors)
            except Exception:
                delete_photos(photo_urls)
                raise
            else:
                # Redirect after saving so pressing "refresh" cannot submit the form twice.
                return redirect(url_for("randre_bp.add_vehicle", saved=vehicle.shipment.bill_of_lading))

        # A browser cannot refill a file picker, so tell the user to choose photos again.
        photos_lost = bool(photo_files)

    # Green "saved" banner after a successful redirect (only for a Bill of Lading that really exists).
    saved = None
    saved_bol = request.args.get("saved", "").strip()[:100]
    if request.method == "GET" and saved_bol:
        shipment = find_shipment_by_bol(saved_bol)
        if shipment is not None:
            saved = build_tracking_view(shipment)

    return render_template(
        "log_vehicle.html",
        form=form,
        errors=errors,
        saved=saved,
        photos_lost=photos_lost,
        categories=CATEGORY_CHOICES,
        currencies=[(code, code) for code in CURRENCY_CHOICES],
        countries=[(name, name) for name in ORIGIN_COUNTRIES],
    ), (400 if errors else 200)


@randre_bp.route("/inventory/photos/<filename>", methods=["GET"])
def vehicle_photo(filename):
    """Serve an uploaded vehicle photo (send_from_directory blocks ../ path tricks)."""
    return send_from_directory(upload_dir(), filename)

