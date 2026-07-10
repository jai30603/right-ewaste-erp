from services.invoice_service import create_sales_invoice

items = [

    {
        "material_id": 1,
        "quantity": 1900,
        "rate": 26
    }

]

invoice = create_sales_invoice(

    party_id=1,

    payment_mode="NEFT",

    transporter="Self",

    vehicle_number="MH01AB1234",

    items=items,

    remarks="Testing Invoice"

)

print(invoice)