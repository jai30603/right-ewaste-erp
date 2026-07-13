import logging
from repositories import sales_repository

logger = logging.getLogger(__name__)

def generate_sales_invoice_number():
    from database import get_connection
    conn = get_connection()
    cursor = conn.cursor()
    inv_num = sales_repository._generate_invoice_number(cursor)
    conn.close()
    return inv_num

def calculate_invoice_totals(items, company_state_code, party_state_code):
    from services.invoice_service import calculate_totals
    return calculate_totals(items, company_state_code, party_state_code)

def check_stock_available(material_id, required_qty, exclude_invoice_id=None):
    from routes.sales import check_stock_available as _check_stock_available
    return _check_stock_available(material_id, required_qty, exclude_invoice_id)

def create_sales_invoice(*args, **kwargs):
    logger.info("Service Layer: Creating sales invoice")
    return sales_repository.create_sales_invoice(*args, **kwargs)

def update_sales_invoice(*args, **kwargs):
    logger.info("Service Layer: Updating sales invoice")
    return sales_repository.update_sales_invoice(*args, **kwargs)
