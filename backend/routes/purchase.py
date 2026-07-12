import io
import os
from datetime import date
from urllib.parse import urlparse
from flask import Blueprint, render_template, request, redirect, url_for, flash, Response, abort
from xhtml2pdf import pisa

from repositories.purchase_repository import (
    get_all_purchase_invoices,
    get_purchase_invoice_by_id,
    get_purchase_invoice_items,
    create_purchase_invoice,
    update_purchase_invoice,
    delete_purchase_invoice,
    search_purchase_invoice,
)
from repositories.party_repository import get_all_parties, get_party_by_id
from repositories.material_repository import get_all_materials
from repositories.company_repository import get_company

purchase_bp = Blueprint("purchase", __name__)

PAYMENT_MODES = ["Cash", "UPI", "NEFT", "RTGS", "Cheque", "Credit"]


def _invoice_context(invoice_id):
    invoice = get_purchase_invoice_by_id(invoice_id)
    if not invoice:
        abort(404)
    items = get_purchase_invoice_items(invoice_id)
    supplier = get_party_by_id(invoice["supplier_id"])
    company = get_company()
    is_intra = (
        company and supplier and
        str(company["state_code"]).strip() == str(supplier["state_code"]).strip()
    )
    return dict(invoice=invoice, items=items, supplier=supplier, company=company, is_intra=is_intra)


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


@purchase_bp.route("/purchase")
def purchase():
    q = request.args.get("q", "").strip()
    invoices = search_purchase_invoice(q) if q else get_all_purchase_invoices()
    return render_template("purchase.html", invoices=invoices, q=q)


@purchase_bp.route("/purchase/add", methods=["GET", "POST"])
def add_purchase_invoice():
    parties = get_all_parties()
    materials = get_all_materials()
    company = get_company()
    company_state_code = company["state_code"] if company else ""
    suppliers = [p for p in parties if p["party_type"] in {"SUPPLIER", "BOTH"}]

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
                "purchase_form.html",
                form=request.form,
                suppliers=suppliers,
                materials=materials,
                payment_modes=PAYMENT_MODES,
                company_state_code=company_state_code,
                errors=errors,
                today=date.today().isoformat(),
            )

        supplier = get_party_by_id(int(request.form["supplier_id"]))
        supplier_state_code = supplier["state_code"] if supplier else ""

        try:
            invoice_id = create_purchase_invoice(
                party_id=request.form["supplier_id"],
                invoice_date=request.form["invoice_date"],
                supplier_invoice_number=request.form.get("supplier_invoice_number"),
                payment_mode=request.form.get("payment_mode"),
                transporter=request.form.get("transporter"),
                vehicle_number=request.form.get("vehicle_number"),
                remarks=request.form.get("remarks"),
                items=items,
                company_state_code=company_state_code,
                party_state_code=supplier_state_code,
            )
        except Exception as exc:
            flash(str(exc), "danger")
            return render_template(
                "purchase_form.html",
                form=request.form,
                suppliers=suppliers,
                materials=materials,
                payment_modes=PAYMENT_MODES,
                company_state_code=company_state_code,
                errors={},
                today=date.today().isoformat(),
            )

        flash("Purchase invoice created successfully.", "success")
        return redirect(url_for("purchase.view_purchase_invoice", invoice_id=invoice_id))

    return render_template(
        "purchase_form.html",
        form=None,
        suppliers=suppliers,
        materials=materials,
        payment_modes=PAYMENT_MODES,
        company_state_code=company_state_code,
        errors={},
        today=date.today().isoformat(),
    )


@purchase_bp.route("/purchase/<int:invoice_id>/view")
def view_purchase_invoice(invoice_id):
    ctx = _invoice_context(invoice_id)
    return render_template("purchase_invoice.html", **ctx)


@purchase_bp.route("/purchase/<int:invoice_id>/pdf")
def download_purchase_pdf(invoice_id):
    ctx = _invoice_context(invoice_id)
    html = render_template("purchase_invoice_pdf.html", **ctx)
    buf = io.BytesIO()
    pisa.CreatePDF(io.StringIO(html), dest=buf, link_callback=_fetch_pdf_resource)
    pdf_bytes = buf.getvalue()
    filename = f"{ctx['invoice']['purchase_invoice_number']}.pdf"
    return Response(pdf_bytes, mimetype="application/pdf", headers={"Content-Disposition": f'attachment; filename="{filename}"', "Content-Length": len(pdf_bytes)})


@purchase_bp.route("/purchase/<int:invoice_id>/print")
def print_purchase_invoice(invoice_id):
    ctx = _invoice_context(invoice_id)
    return render_template("purchase_invoice.html", **ctx)


@purchase_bp.route("/purchase/<int:invoice_id>/edit", methods=["GET", "POST"])
def edit_purchase_invoice(invoice_id):
    existing = get_purchase_invoice_by_id(invoice_id)
    if not existing:
        flash("Purchase invoice not found.", "danger")
        return redirect(url_for("purchase.purchase"))

    parties = get_all_parties()
    materials = get_all_materials()
    company = get_company()
    company_state_code = company["state_code"] if company else ""
    suppliers = [p for p in parties if p["party_type"] in {"SUPPLIER", "BOTH"}]

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
                "purchase_form.html",
                form=request.form,
                suppliers=suppliers,
                materials=materials,
                payment_modes=PAYMENT_MODES,
                company_state_code=company_state_code,
                errors=errors,
                today=existing["invoice_date"],
                invoice_id=invoice_id,
            )

        supplier = get_party_by_id(int(request.form["supplier_id"]))
        supplier_state_code = supplier["state_code"] if supplier else ""
        update_purchase_invoice(
            invoice_id,
            request.form["supplier_id"],
            request.form["invoice_date"],
            request.form.get("supplier_invoice_number"),
            request.form.get("payment_mode"),
            request.form.get("transporter"),
            request.form.get("vehicle_number"),
            request.form.get("remarks"),
            items,
            company_state_code,
            supplier_state_code,
        )
        flash("Purchase invoice updated successfully.", "success")
        return redirect(url_for("purchase.view_purchase_invoice", invoice_id=invoice_id))

    existing_items = get_purchase_invoice_items(invoice_id)
    form_data = dict(existing)
    form_data["supplier_id"] = str(existing["supplier_id"] or "")
    form_data["invoice_date"] = existing["invoice_date"]
    form_data["supplier_invoice_number"] = existing["supplier_invoice_number"] or ""
    form_data["payment_mode"] = existing["payment_mode"] or ""
    form_data["transporter"] = existing["transporter"] or ""
    form_data["vehicle_number"] = existing["vehicle_number"] or ""
    form_data["remarks"] = existing["remarks"] or ""

    return render_template(
        "purchase_form.html",
        form=form_data,
        suppliers=suppliers,
        materials=materials,
        payment_modes=PAYMENT_MODES,
        company_state_code=company_state_code,
        errors={},
        today=existing["invoice_date"],
        invoice_id=invoice_id,
        existing_items=existing_items,
    )


@purchase_bp.route("/purchase/<int:invoice_id>/delete", methods=["POST"])
def delete_purchase_invoice_route(invoice_id):
    existing = get_purchase_invoice_by_id(invoice_id)
    if not existing:
        flash("Purchase invoice not found.", "danger")
        return redirect(url_for("purchase.purchase"))
    delete_purchase_invoice(invoice_id)
    flash("Purchase invoice deleted successfully.", "warning")
    return redirect(url_for("purchase.purchase"))


def _validate_header(form):
    errors = {}
    if not form.get("supplier_id", "").strip():
        errors["supplier_id"] = "Supplier is required."
    if not form.get("invoice_date", "").strip():
        errors["invoice_date"] = "Invoice date is required."
    return errors