"""Manual invoice test entry point.

This module intentionally has no import-time database writes.
"""

from services.invoice_service import create_sales_invoice


if __name__ == "__main__":
    invoice = create_sales_invoice(
        party_id=1,
        payment_mode="NEFT",
        transporter="Self",
        vehicle_number="MH01AB1234",
        items=[{"material_id": 1, "quantity": 1900, "rate": 26}],
        remarks="Manual test invoice",
    )
    print(invoice)
