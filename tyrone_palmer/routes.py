"""Routes for F-05 Dynamic Pricing Estimates & Rate Maintenance."""

from flask import (
    render_template,
    jsonify,
    abort,
    request,
    redirect,
    url_for,
    session,
)
from secrets import token_hex, compare_digest

from tyrone_palmer import tyrone_bp
from tyrone_palmer.pricing_engine import calculate_estimated_jmd_price
from tyrone_palmer.rates_service import (
    get_all_fx_rates,
    get_all_duty_tiers,
    update_fx_rate,
    update_duty_tier,
)

from shared.models import Vehicle
from shared.auth import role_required


@tyrone_bp.route(
    "/pricing/estimate/<int:vehicle_id>",
    methods=["GET"]
)
def pricing_estimate(vehicle_id: int):
    """F-05: Return a public-safe estimated JMD price."""

    vehicle = Vehicle.query.filter_by(
        id=vehicle_id,
        is_deleted=False,
        deposit_paid=True,
    ).first()

    if vehicle is None:
        abort(404)

    try:
        estimated_price = calculate_estimated_jmd_price(vehicle)

    except ValueError:
        return jsonify({
            "vehicle_id": vehicle.id,
            "estimated_jmd_price": None,
            "status": "unavailable",
            "error": "Price estimate is currently unavailable."
        }), 422

    response = jsonify({
        "vehicle_id": vehicle.id,
        "estimated_jmd_price": str(estimated_price),
        "currency": "JMD",
        "status": "success"
    })

    response.headers["Cache-Control"] = "no-store"

    return response


@tyrone_bp.route(
    "/admin/pricing-rates",
    methods=["GET", "POST"]
)
@role_required("purchasing_manager")
def manage_rates():
    """Allow authorized staff to update pricing variables."""

    error = None
    success = None

    if "pricing_csrf_token" not in session:
        session["pricing_csrf_token"] = token_hex(32)

    if request.method == "POST":

        submitted_token = request.form.get("csrf_token", "")

        if not compare_digest(
            submitted_token,
            session["pricing_csrf_token"]
        ):
            abort(400)

        action = request.form.get("action")

        try:
            if action == "update_fx":

                currency_code = request.form.get(
                    "currency_code", ""
                )

                new_rate = request.form.get("rate_to_jmd")

                update_fx_rate(currency_code, new_rate)

            elif action == "update_duty":

                tier_id = int(request.form.get("tier_id", ""))

                new_percentage = request.form.get(
                    "duty_percentage"
                )

                update_duty_tier(tier_id, new_percentage)

            else:
                raise ValueError("Invalid update action.")

            return redirect(
                url_for(
                    "tyrone_bp.manage_rates",
                    updated="1"
                )
            )

        except (ValueError, TypeError) as exc:
            error = str(exc)

    if request.args.get("updated") == "1":
        success = "Pricing variables updated successfully."

    fx_rates = get_all_fx_rates()
    duty_tiers = get_all_duty_tiers()

    return render_template(
        "manage_rates.html",
        fx_rates=fx_rates,
        duty_tiers=duty_tiers,
        error=error,
        success=success,
        csrf_token=session["pricing_csrf_token"]
    )
