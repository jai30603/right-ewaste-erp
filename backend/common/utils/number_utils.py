"""
Number Utilities
Provides accurate rounding and conversions.
"""
from decimal import Decimal, ROUND_HALF_UP

def round2(n):
    if n is None:
        return 0.0
    try:
        return float(Decimal(f"{n:.6f}").quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))
    except Exception:
        return float(round(n, 2))

def round_int(n):
    if n is None:
        return 0
    try:
        return int(Decimal(f"{n:.6f}").quantize(Decimal('1'), rounding=ROUND_HALF_UP))
    except Exception:
        return int(round(n))
