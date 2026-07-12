def calculate_running_balance(ledger_rows):
    """
    Given a list of ledger dicts ordered chronologically,
    calculates the running balance of stock.
    """
    balance = 0.0
    ledger = []
    for row in ledger_rows:
        item = dict(row)
        qty = float(item["qty"] or 0.0)
        if item["type"] == "Purchase":
            balance += qty
        else:
            balance -= qty
        item["balance"] = balance
        ledger.append(item)
    return ledger
