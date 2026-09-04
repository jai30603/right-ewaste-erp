import logging
from decimal import Decimal, ROUND_HALF_UP

logger = logging.getLogger(__name__)

def determine_tax_treatment(company_state_code, billing_state_code, shipping_state_code=None):
    """
    Returns True if transaction is Intra-State (CGST + SGST), False if Inter-State (IGST).
    The place of supply is shipping_state_code if present and non-empty, otherwise billing_state_code.
    """
    comp = str(company_state_code or "").strip()
    bill = str(billing_state_code or "").strip()
    ship = str(shipping_state_code or "").strip()
    
    place_of_supply = ship if ship else bill
    if not comp or not place_of_supply:
        # Default fallback to intra-state
        return True
    return comp == place_of_supply

def number_to_inr_words(amount):
    """Convert amount to standard Indian Rupee words (e.g. RUPEES SEVENTY-SIX THOUSAND SEVEN HUNDRED ONLY)."""
    try:
        amount = float(amount or 0)
        rupees = int(round(amount, 2))
        paise = int(round((round(amount, 2) - rupees) * 100))
        if paise < 0:
            paise = 0

        ones = ['', 'One', 'Two', 'Three', 'Four', 'Five', 'Six', 'Seven',
                'Eight', 'Nine', 'Ten', 'Eleven', 'Twelve', 'Thirteen',
                'Fourteen', 'Fifteen', 'Sixteen', 'Seventeen', 'Eighteen', 'Nineteen']
        tens_w = ['', '', 'Twenty', 'Thirty', 'Forty', 'Fifty',
                  'Sixty', 'Seventy', 'Eighty', 'Ninety']

        def two_dig(n):
            if n < 20:
                return ones[n]
            t = tens_w[n // 10]
            o = ones[n % 10]
            return f"{t}-{o}" if o else t

        def conv(n):
            if n == 0:        return ''
            if n < 20:        return ones[n]
            if n < 100:       return two_dig(n)
            if n < 1_000:     return ones[n // 100] + ' Hundred' + (' ' + conv(n % 100) if n % 100 else '')
            if n < 1_00_000:  return conv(n // 1_000) + ' Thousand' + (' ' + conv(n % 1_000) if n % 1_000 else '')
            if n < 1_00_00_000: return conv(n // 1_00_000) + ' Lakh' + (' ' + conv(n % 1_00_000) if n % 1_00_000 else '')
            return conv(n // 1_00_00_000) + ' Crore' + (' ' + conv(n % 1_00_00_000) if n % 1_00_00_000 else '')

        rup_words = conv(rupees).strip()
        if not rup_words:
            rup_words = 'Zero'

        result = 'RUPEES ' + rup_words.upper()
        if paise:
            result += ' AND ' + two_dig(paise).upper() + ' PAISE'
        return result + ' ONLY'
    except Exception:
        return ''

def calculate_invoice_result(items, company_state_code, billing_state_code, shipping_state_code=None, tcs_applicable=False, tcs_rate=0.0):
    """
    Computes all line-level taxes and aggregates invoice totals using precise Decimal arithmetic.
    """
    is_intra = determine_tax_treatment(company_state_code, billing_state_code, shipping_state_code)
    
    decimals_lines = []
    taxable_total = Decimal('0.00')
    cgst_total = Decimal('0.00')
    sgst_total = Decimal('0.00')
    igst_total = Decimal('0.00')
    
    for item in items:
        qty = Decimal(str(item.get("qty") or 0.0))
        rate = Decimal(str(item.get("rate") or 0.0))
        
        # Calculate taxable value: Qty * Rate
        taxable_val = (qty * rate).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        
        # GST Calculations
        gst_pct = Decimal(str(item.get("gst_percentage") if item.get("gst_percentage") is not None else 18.0))
        total_gst = (taxable_val * gst_pct / Decimal('100.00')).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        
        if is_intra:
            cgst = (total_gst / Decimal('2.0')).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            sgst = (total_gst / Decimal('2.0')).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            igst = Decimal('0.00')
        else:
            cgst = Decimal('0.00')
            sgst = Decimal('0.00')
            igst = total_gst
            
        line_total = taxable_val + cgst + sgst + igst
        
        decimals_lines.append({
            "taxable_amount": taxable_val,
            "gst_rate": gst_pct,
            "cgst": cgst,
            "sgst": sgst,
            "igst": igst,
            "total": line_total
        })
        
        taxable_total += taxable_val
        cgst_total += cgst
        sgst_total += sgst
        igst_total += igst

    # TCS calculation
    if tcs_applicable:
        tcs_base_amount = taxable_total + cgst_total + sgst_total + igst_total
        tcs_rate_dec = Decimal(str(tcs_rate or 0.0))
        tcs_amount = (tcs_base_amount * tcs_rate_dec / Decimal('100.00')).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    else:
        tcs_base_amount = Decimal('0.00')
        tcs_amount = Decimal('0.00')

    # Grand total and Round-off
    raw_grand_total = taxable_total + cgst_total + sgst_total + igst_total + tcs_amount
    grand_total = raw_grand_total.quantize(Decimal('1'), rounding=ROUND_HALF_UP)
    round_off = grand_total - raw_grand_total

    # Build response with float conversions
    lines_output = []
    for line in decimals_lines:
        lines_output.append({
            "taxable_amount": float(line["taxable_amount"]),
            "gst_rate": float(line["gst_rate"]),
            "cgst": float(line["cgst"]),
            "sgst": float(line["sgst"]),
            "igst": float(line["igst"]),
            "total": float(line["total"])
        })

    result = {
        "is_intra": is_intra,
        "lines": lines_output,
        "taxable_total": float(taxable_total),
        "cgst_total": float(cgst_total),
        "sgst_total": float(sgst_total),
        "igst_total": float(igst_total),
        "tcs_base_amount": float(tcs_base_amount),
        "tcs_amount": float(tcs_amount),
        "tcs_rate": float(tcs_rate),
        "round_off": float(round_off),
        "grand_total": float(grand_total),
        "amount_in_words": number_to_inr_words(float(grand_total))
    }
    return result
