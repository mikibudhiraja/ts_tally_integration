import frappe
from frappe import _


ALLOWED_DOCTYPES = {
    "Customer",
    "Supplier",
    "Item",
    "Account",
    "Item Group",
    "Warehouse",
}

CHILD_DOCTYPE = "Tally Master Sync Log"
PARENTFIELD = "custom_tally_sync_log"


def _ensure_administrator():
    if frappe.session.user != "Administrator":
        frappe.throw(_("Only Administrator can remove Tally sync log"), frappe.PermissionError)


def _validate_doctype(doctype):
    if doctype not in ALLOWED_DOCTYPES:
        frappe.throw(_("Remove Tally Sync Log is not supported for {0}").format(doctype))


def _clear_sync_log_for_record(doctype, name, company):
    frappe.db.delete(
        CHILD_DOCTYPE,
        {
            "parenttype": doctype,
            "parentfield": PARENTFIELD,
            "parent": name,
            "company_name": company,
        },
    )
    frappe.db.set_value(doctype, name, "modified", frappe.utils.now())


@frappe.whitelist()
def bulk_remove_master_sync_log(doctype, names, company):
    _ensure_administrator()
    _validate_doctype(doctype)

    if isinstance(names, str):
        names = frappe.parse_json(names)

    if not names:
        frappe.throw(_("No records selected"))

    if not company:
        frappe.throw(_("Company is required"))

    if not frappe.db.exists("Company", company):
        frappe.throw(_("Company {0} does not exist").format(company))

    cleared = []
    failed = []
    for name in names:
        try:
            _clear_sync_log_for_record(doctype, name, company)
            cleared.append(name)
        except Exception:
            frappe.log_error(
                frappe.get_traceback(),
                f"Tally Remove Master Sync Log failed for {doctype} {name}",
            )
            failed.append(name)

    frappe.db.commit()
    return {"cleared": cleared, "failed": failed}


def _get_tally_company_number(company):
    company_number = frappe.db.get_value(
        "TS Tally Company",
        {"parent": "TS Tally Settings", "parentfield": "company_table", "company_name": company},
        "company_number",
    )
    if company_number is None:
        frappe.throw(_("Company {0} is not configured in TS Tally Settings").format(company))
    return company_number


def _set_manual_sync_log_for_record(doctype, name, company, company_number, sync_time):
    """Mark the record as synced to Tally the same way a real sync does, so
    the master is skipped on the next pull for this Tally company."""
    existing = frappe.db.get_value(
        CHILD_DOCTYPE,
        {"parent": name, "parenttype": doctype, "company_number": company_number},
        "name",
    )
    if existing:
        frappe.db.set_value(
            CHILD_DOCTYPE,
            existing,
            {"tally_auto_id": name, "status": "SUCCESS", "sync_time": sync_time},
        )
    else:
        max_idx = frappe.db.count(CHILD_DOCTYPE, {"parent": name, "parenttype": doctype})
        sync_log = frappe.new_doc(CHILD_DOCTYPE)
        sync_log.parent = name
        sync_log.parenttype = doctype
        sync_log.parentfield = PARENTFIELD
        sync_log.idx = max_idx + 1
        sync_log.company_number = company_number
        sync_log.company_name = company
        sync_log.tally_auto_id = name
        sync_log.status = "SUCCESS"
        sync_log.sync_time = sync_time
        sync_log.db_insert()

    frappe.db.set_value(doctype, name, "modified", frappe.utils.now())


@frappe.whitelist()
def bulk_manual_master_sync_log(doctype, names, company):
    _ensure_administrator()
    _validate_doctype(doctype)

    if isinstance(names, str):
        names = frappe.parse_json(names)

    if not names:
        frappe.throw(_("No records selected"))

    if not company:
        frappe.throw(_("Company is required"))

    company_number = _get_tally_company_number(company)
    sync_time = frappe.utils.now_datetime()

    updated = []
    failed = []
    for name in names:
        try:
            _set_manual_sync_log_for_record(doctype, name, company, company_number, sync_time)
            updated.append(name)
        except Exception:
            frappe.log_error(
                frappe.get_traceback(),
                f"Tally Manual Master Sync Log failed for {doctype} {name}",
            )
            failed.append(name)

    frappe.db.commit()
    return {"updated": updated, "failed": failed}
