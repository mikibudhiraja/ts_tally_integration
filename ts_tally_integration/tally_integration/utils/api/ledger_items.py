import frappe


def items_without_own_ledger(items, account_field, own_ledger_types):
    """Drop the items whose account the voucher already sends as its own ledger
    line (an account type in `own_ledger_types`), so the item lines built from
    the stock / income GL row do not count them a second time."""
    account_types = {}
    out = []
    for item in items:
        account = item.get(account_field)
        if account and account not in account_types:
            account_types[account] = frappe.db.get_value('Account', account, 'account_type')
        if account and account_types[account] in own_ledger_types:
            continue
        out.append(item)
    return out
