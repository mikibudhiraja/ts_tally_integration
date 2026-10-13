import functools
import json

import frappe
from frappe.utils import cint
from werkzeug.wrappers import Response


def get_master_sync_limit(default=10):
    return _get_settings_limit("master_limit", default)


def get_voucher_sync_limit(default=10):
    return _get_settings_limit("voucher_limit", default)


def _get_settings_limit(fieldname, default):
    sync_limit = frappe.db.get_single_value("TS Tally Settings", fieldname)
    if sync_limit is None:
        return default

    return cint(sync_limit)


def company_filters(company_id):
    """Filters for the TS Tally Settings company row that is allowed to sync."""
    return {
        "parent": "TS Tally Settings",
        "parentfield": "company_table",
        "company_number": company_id,
        "sync": 1,
    }


def is_company_sync_enabled(company_id):
    return bool(frappe.db.exists("TS Tally Company", company_filters(company_id)))


def company_sync_required(detail_key="VOUCHER"):
    """Send no data for a company number unless its company row has Sync ticked.

    `detail_key` is the list Tally expects inside VOUCHERDETAILS for this
    endpoint, so an unsynced company gets the endpoint's usual empty reply.
    """

    def decorator(fn):
        @functools.wraps(fn)
        def wrapper(company_id=None, *args, **kwargs):
            if company_id and not is_company_sync_enabled(company_id):
                empty = {"status": True, "VOUCHERDETAILS": {detail_key: []}}
                return Response(json.dumps(empty, default=str), content_type="application/json")
            return fn(company_id, *args, **kwargs)

        return wrapper

    return decorator
