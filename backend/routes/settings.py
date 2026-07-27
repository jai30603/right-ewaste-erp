from flask import Blueprint, render_template, request, redirect, url_for, jsonify
from repositories import settings_repository
from repositories.activity_log_repository import log_activity
from backend.common.utils.flash_helpers import flash_success, flash_error, flash_warning

settings_bp = Blueprint("settings", __name__)

@settings_bp.route("/settings", methods=["GET", "POST"])
def settings():
    if request.method == "POST":
        try:
            if "default_currency" in request.form:
                settings_repository.set_setting("CURRENCY", request.form["default_currency"])
            if "default_timezone" in request.form:
                settings_repository.set_setting("TIMEZONE", request.form["default_timezone"])
            # Prefix configurations
            prefixes = {
                "PURCHASE": request.form.get("purchase_prefix"),
                "SALES": request.form.get("sales_prefix"),
                "CERTIFICATE": request.form.get("cert_prefix")
            }
            for key, prefix in prefixes.items():
                if prefix:
                    series = settings_repository.get_number_series(key)
                    if series:
                        series["prefix"] = prefix
                        settings_repository.save_number_series(key, series)
            if "smtp_host" in request.form:
                settings_repository.set_setting("NOTIFICATION_EMAIL_HOST", request.form["smtp_host"])
                
            log_activity(
                "System Administrator",
                "System Settings Updated",
                "Updated general preferences, document sequence patterns, and SMTP server details.",
                module="Settings"
            )
            flash_success("System settings saved successfully.")
        except Exception as e:
            flash_error(f"Failed to save settings: {e}")
        return redirect(url_for("settings.settings"))

    # Load all settings
    all_settings = settings_repository.get_all_settings()
    all_series = settings_repository.get_all_number_series()
    categories = settings_repository.get_all_categories()
    units = settings_repository.get_all_units()
    
    return render_template(
        "settings/settings.html",
        settings=all_settings,
        series=all_series,
        categories=categories,
        units=units
    )

@settings_bp.route("/settings/general", methods=["POST"])
def save_general():
    try:
        keys = ["ERP_NAME", "COMPANY_NAME", "CURRENT_FINANCIAL_YEAR", "TIMEZONE", "DATE_FORMAT", "TIME_FORMAT", "CURRENCY", "DECIMAL_PRECISION", "WEIGHT_PRECISION"]
        for k in keys:
            if k in request.form:
                settings_repository.set_setting(k, request.form[k])
        
        log_activity("System Administrator", "Settings Updated", "Updated general system settings.", module="Settings")
        flash_success("General settings updated successfully.")
    except Exception as e:
        flash_error(f"Failed to update general settings: {e}")
    return redirect(url_for("settings.settings"))

@settings_bp.route("/settings/numbering", methods=["POST"])
def save_numbering():
    try:
        # Load all series keys
        series_keys = ["PURCHASE", "SALES", "CERTIFICATE", "MATERIAL", "PARTY", "PROCESSING"]
        for key in series_keys:
            prefix_field = f"prefix_{key.lower()}"
            start_field = f"start_{key.lower()}"
            pad_field = f"pad_{key.lower()}"
            reset_field = f"reset_{key.lower()}"
            
            if prefix_field in request.form:
                data = {
                    "prefix": request.form[prefix_field],
                    "suffix": request.form.get(f"suffix_{key.lower()}", ""),
                    "starting_number": int(request.form.get(start_field, 1)),
                    "current_number": int(request.form.get(f"current_{key.lower()}", 0)),
                    "padding_length": int(request.form.get(pad_field, 6)),
                    "reset_yearly": 1 if request.form.get(reset_field) == "on" or request.form.get(reset_field) == "1" else 0,
                    "last_reset_year": int(request.form.get(f"year_{key.lower()}", 2026))
                }
                settings_repository.save_number_series(key, data)
                
        log_activity("System Administrator", "Settings Updated", "Updated number series formatting configuration.", module="Settings")
        flash_success("Numbering sequences saved successfully.")
    except Exception as e:
        flash_error(f"Failed to save numbering sequences: {e}")
    return redirect(url_for("settings.settings"))

@settings_bp.route("/settings/tax", methods=["POST"])
def save_tax():
    try:
        keys = ["DEFAULT_GST", "TAX_ROUNDING"]
        for k in keys:
            if k in request.form:
                settings_repository.set_setting(k, request.form[k])
        log_activity("System Administrator", "Settings Updated", "Updated default tax configuration settings.", module="Settings")
        flash_success("Tax & GST settings updated successfully.")
    except Exception as e:
        flash_error(f"Failed to save tax configurations: {e}")
    return redirect(url_for("settings.settings"))

@settings_bp.route("/settings/certificate", methods=["POST"])
def save_certificate():
    try:
        keys = ["CERT_LOGO", "CERT_SIGNATURE_TITLE", "CERT_DECLARATION", "CERT_WATERMARK"]
        for k in keys:
            if k in request.form:
                settings_repository.set_setting(k, request.form[k])
        log_activity("System Administrator", "Settings Updated", "Updated default certificate engine settings.", module="Settings")
        flash_success("Certificate defaults updated successfully.")
    except Exception as e:
        flash_error(f"Failed to save certificate defaults: {e}")
    return redirect(url_for("settings.settings"))

@settings_bp.route("/settings/theme", methods=["POST"])
def save_theme():
    try:
        keys = ["THEME_MODE", "THEME_SIDEBAR", "THEME_ACCENT"]
        for k in keys:
            if k in request.form:
                settings_repository.set_setting(k, request.form[k])
        log_activity("System Administrator", "Settings Updated", "Updated theme settings configuration.", module="Settings")
        flash_success("Theme settings saved successfully.")
    except Exception as e:
        flash_error(f"Failed to save theme configurations: {e}")
    return redirect(url_for("settings.settings"))

@settings_bp.route("/settings/notifications", methods=["POST"])
def save_notifications():
    try:
        keys = ["NOTIFICATION_ENABLE_EMAIL", "NOTIFICATION_EMAIL_HOST"]
        for k in keys:
            val = request.form.get(k, "0")
            if k == "NOTIFICATION_ENABLE_EMAIL" and val == "on":
                val = "1"
            settings_repository.set_setting(k, val)
        log_activity("System Administrator", "Settings Updated", "Updated notifications settings configuration.", module="Settings")
        flash_success("Notification settings saved successfully.")
    except Exception as e:
        flash_error(f"Failed to save notification settings: {e}")
    return redirect(url_for("settings.settings"))

@settings_bp.route("/settings/categories/add", methods=["POST"])
def save_category():
    name = request.form.get("category_name", "").strip()
    if not name:
        flash_warning("Category name cannot be empty.")
    else:
        try:
            settings_repository.add_category(name)
            log_activity("System Administrator", "Material Category Created", f"Added category: {name}", module="Settings")
            flash_success(f"Material category '{name}' added successfully.")
        except Exception as e:
            flash_error(f"Failed to add category: {e}")
    return redirect(url_for("settings.settings"))

@settings_bp.route("/settings/categories/delete/<int:cat_id>", methods=["POST"])
def remove_category(cat_id):
    try:
        settings_repository.delete_category(cat_id)
        log_activity("System Administrator", "Material Category Deleted", f"Deleted category ID: {cat_id}", module="Settings")
        flash_success("Material category deleted successfully.")
    except Exception as e:
        flash_error(f"Failed to delete category: {e}")
    return redirect(url_for("settings.settings"))

@settings_bp.route("/settings/units/add", methods=["POST"])
def save_unit():
    name = request.form.get("unit_name", "").strip()
    if not name:
        flash_warning("Unit name cannot be empty.")
    else:
        try:
            settings_repository.add_unit(name)
            log_activity("System Administrator", "Unit Created", f"Added measurement unit: {name}", module="Settings")
            flash_success(f"Measurement unit '{name}' added successfully.")
        except Exception as e:
            flash_error(f"Failed to add unit: {e}")
    return redirect(url_for("settings.settings"))

@settings_bp.route("/settings/units/delete/<int:unit_id>", methods=["POST"])
def remove_unit(unit_id):
    try:
        settings_repository.delete_unit(unit_id)
        log_activity("System Administrator", "Unit Deleted", f"Deleted unit ID: {unit_id}", module="Settings")
        flash_success("Measurement unit deleted successfully.")
    except Exception as e:
        flash_error(f"Failed to delete unit: {e}")
    return redirect(url_for("settings.settings"))
