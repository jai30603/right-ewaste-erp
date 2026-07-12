import io
import os
from datetime import date
from urllib.parse import urlparse
from flask import (
    Blueprint, render_template, request,
    redirect, url_for, flash, Response, abort,
)
from xhtml2pdf import pisa

from repositories.sales_repository import (
    get_all_invoices,
    get_invoice_by_id,
    get_invoice_items,
    create_sales_invoice,
    update_sales_invoice,
    delete_sales_invoice,
)
from repositories.party_repository import get_all_parties, get_party_by_id
from repositories.material_repository import get_all_materials
from repositories.company_repository import get_company

sales_bp = Blueprint("sales", __name__)

PAYMENT_MODES = ["Cash", "NEFT", "RTGS", "UPI", "Cheque", "Credit"]


# ── Helpers ───────────────────────────────────────────────────────────────────

def _invoice_context(invoice_id):
    """Shared data bundle for view + PDF routes."""
    invoice = get_invoice_by_id(invoice_id)
    if not invoice:
        abort(404)
    items   = get_invoice_items(invoice_id)
    party   = get_party_by_id(invoice["party_id"])
    company = get_company()
    is_intra = (
        company and party and
        str(company["state_code"]).strip() == str(party["state_code"]).strip()
    )
    return dict(
        invoice  = invoice,
        items    = items,
        party    = party,
        company  = company,
        is_intra = is_intra,
    )


# ── List ──────────────────────────────────────────────────────────────────────

@sales_bp.route("/sales")
def sales():
    invoices = get_all_invoices()
    return render_template("sales.html", invoices=invoices)


# ── Add ───────────────────────────────────────────────────────────────────────

@sales_bp.route("/sales/add", methods=["GET", "POST"])
def add_sales_invoice():
    parties   = get_all_parties()
    materials = get_all_materials()
    company   = get_company()
    company_state_code = company["state_code"] if company else ""

    if request.method == "POST":
        errors = _validate_header(request.form)

        material_ids    = request.form.getlist("material_id[]")
        qtys            = request.form.getlist("qty[]")
        weights         = request.form.getlist("weight[]")
        pieces_list     = request.form.getlist("pieces[]")
        rates           = request.form.getlist("rate[]")
        amounts         = request.form.getlist("amount[]")
        gst_percentages = request.form.getlist("gst_percentage[]")

        items = []
        for i in range(len(material_ids)):
            mid = material_ids[i].strip()
            if not mid:
                continue
            items.append({
                "material_id":    int(mid),
                "qty":            float(qtys[i]            or 0),
                "weight":         float(weights[i]         or 0),
                "pieces":         int(pieces_list[i]       or 0),
                "rate":           float(rates[i]           or 0),
                "amount":         float(amounts[i]         or 0),
                "gst_percentage": float(gst_percentages[i] or 0),
            })

        if not items:
            errors["items"] = "Add at least one item."

        if errors:
            flash("Please fix the errors below.", "danger")
            return render_template(
                "sales_form.html",
                form=request.form,
                parties=parties,
                materials=materials,
                payment_modes=PAYMENT_MODES,
                company_state_code=company_state_code,
                errors=errors,
                today=date.today().isoformat(),
            )

        party            = get_party_by_id(int(request.form["party_id"]))
        party_state_code = party["state_code"] if party else ""

        try:
            invoice_id = create_sales_invoice(
                party_id           = request.form["party_id"],
                invoice_date       = request.form["invoice_date"],
                payment_mode       = request.form.get("payment_mode"),
                transporter        = request.form.get("transporter"),
                vehicle_number     = request.form.get("vehicle_number"),
                remarks            = request.form.get("remarks"),
                items              = items,
                company_state_code = company_state_code,
                party_state_code   = party_state_code,
            )
        except RuntimeError as exc:
            flash(str(exc), "danger")
            return render_template(
                "sales_form.html",
                form=request.form,
                parties=parties,
                materials=materials,
                payment_modes=PAYMENT_MODES,
                company_state_code=company_state_code,
                errors={},
                today=date.today().isoformat(),
            )

        flash("Sales invoice created successfully.", "success")
        return redirect(url_for("sales.view_invoice", invoice_id=invoice_id))

    return render_template(
        "sales_form.html",
        form=None,
        parties=parties,
        materials=materials,
        payment_modes=PAYMENT_MODES,
        company_state_code=company_state_code,
        errors={},
        today=date.today().isoformat(),
    )


# ── Edit ────────────────────────────────────────────────────────────────────

@sales_bp.route("/sales/<int:invoice_id>/edit", methods=["GET", "POST"])
def edit_sales_invoice(invoice_id):
    existing = get_invoice_by_id(invoice_id)
    if not existing:
        flash("Sales invoice not found.", "danger")
        return redirect(url_for("sales.sales"))

    parties = get_all_parties()
    materials = get_all_materials()
    company = get_company()
    company_state_code = company["state_code"] if company else ""

    if request.method == "POST":
        errors = _validate_header(request.form)
        material_ids = request.form.getlist("material_id[]")
        qtys = request.form.getlist("qty[]")
        weights = request.form.getlist("weight[]")
        pieces_list = request.form.getlist("pieces[]")
        rates = request.form.getlist("rate[]")
        amounts = request.form.getlist("amount[]")
        gst_percentages = request.form.getlist("gst_percentage[]")

        items = []
        for i in range(len(material_ids)):
            mid = material_ids[i].strip()
            if not mid:
                continue
            items.append({
                "material_id": int(mid),
                "qty": float(qtys[i] or 0),
                "weight": float(weights[i] or 0),
                "pieces": int(pieces_list[i] or 0),
                "rate": float(rates[i] or 0),
                "amount": float(amounts[i] or 0),
                "gst_percentage": float(gst_percentages[i] or 0),
            })

        if not items:
            errors["items"] = "Add at least one item."

        if errors:
            flash("Please fix the errors below.", "danger")
            return render_template(
                "sales_form.html",
                form=request.form,
                parties=parties,
                materials=materials,
                payment_modes=PAYMENT_MODES,
                company_state_code=company_state_code,
                errors=errors,
                today=existing["invoice_date"],
                invoice_id=invoice_id,
            )

        party = get_party_by_id(int(request.form["party_id"]))
        party_state_code = party["state_code"] if party else ""
        update_sales_invoice(
            invoice_id,
            request.form["party_id"],
            request.form["invoice_date"],
            request.form.get("payment_mode"),
            request.form.get("transporter"),
            request.form.get("vehicle_number"),
            request.form.get("remarks"),
            items,
            company_state_code,
            party_state_code,
        )
        flash("Sales invoice updated successfully.", "success")
        return redirect(url_for("sales.view_invoice", invoice_id=invoice_id))

    existing_items = get_invoice_items(invoice_id)
    form_data = dict(existing)
    form_data["party_id"] = str(existing["party_id"] or "")
    form_data["invoice_date"] = existing["invoice_date"]
    form_data["payment_mode"] = existing["payment_mode"] or ""
    form_data["transporter"] = existing["transporter"] or ""
    form_data["vehicle_number"] = existing["vehicle_number"] or ""
    form_data["remarks"] = existing["remarks"] or ""

    return render_template(
        "sales_form.html",
        form=form_data,
        parties=parties,
        materials=materials,
        payment_modes=PAYMENT_MODES,
        company_state_code=company_state_code,
        errors={},
        today=existing["invoice_date"],
        invoice_id=invoice_id,
        existing_items=existing_items,
    )


@sales_bp.route("/sales/<int:invoice_id>/delete", methods=["POST"])
def delete_sales_invoice_route(invoice_id):
    existing = get_invoice_by_id(invoice_id)
    if not existing:
        flash("Sales invoice not found.", "danger")
        return redirect(url_for("sales.sales"))
    delete_sales_invoice(invoice_id)
    flash("Sales invoice deleted successfully.", "warning")
    return redirect(url_for("sales.sales"))


# ── View / Preview ────────────────────────────────────────────────────────────

@sales_bp.route("/sales/<int:invoice_id>/view")
def view_invoice(invoice_id):
    ctx = _invoice_context(invoice_id)
    return render_template("sales_invoice.html", **ctx)


# ── Download PDF ──────────────────────────────────────────────────────────────

def _fetch_pdf_resource(uri, rel):
    parsed = urlparse(uri)
    if parsed.scheme == 'file':
        path = parsed.path
        if path.startswith('/') and path[2:3] == ':':
            path = path[1:]
        return os.path.normpath(path)
    if uri.startswith('/static/'):
        root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
        return os.path.normpath(os.path.join(root, uri.lstrip('/').replace('/', os.sep)))
    return uri

@sales_bp.route("/sales/<int:invoice_id>/pdf")
def download_pdf(invoice_id):
    ctx  = _invoice_context(invoice_id)
    html = render_template("sales_invoice_pdf.html", **ctx)

    buf = io.BytesIO()
    pisa.CreatePDF(io.StringIO(html), dest=buf, link_callback=_fetch_pdf_resource)
    pdf_bytes = buf.getvalue()

    filename = f"{ctx['invoice']['invoice_number']}.pdf"
    return Response(
        pdf_bytes,
        mimetype="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Length": len(pdf_bytes),
        },
    )


# ── Email (mailto link handled in template) ───────────────────────────────────

@sales_bp.route("/sales/<int:invoice_id>/email")
def email_invoice(invoice_id):
    ctx = _invoice_context(invoice_id)
    return render_template("sales_invoice.html", open_email_modal=True, **ctx)


# ── Validation ────────────────────────────────────────────────────────────────

def _validate_header(form):
    errors = {}
    if not form.get("party_id", "").strip():
        errors["party_id"] = "Customer is required."
    if not form.get("invoice_date", "").strip():
        errors["invoice_date"] = "Invoice date is required."
    return errors
