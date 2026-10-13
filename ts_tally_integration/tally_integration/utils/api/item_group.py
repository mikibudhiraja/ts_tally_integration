import frappe
from ts_tally_integration.tally_integration.utils.api.sync_settings import company_filters, company_sync_required
from ts_tally_integration.tally_integration.utils.api.sync_settings import get_master_sync_limit
import json
from werkzeug.wrappers import Response
from datetime import datetime


@frappe.whitelist()
@company_sync_required("STOCKGROUPS")
def get_itemgroup(company_id=None):
    if not company_id:
        return Response(json.dumps({"status": False, "message": "Company ID not found"}), content_type="application/json")

    enable_sync = frappe.get_value('Voucher Sync Control', {'voucher_name': 'Item Group'}, ['enable_sync'])
    if not enable_sync:
        final_voucher = {
            "status": True,
            "VOUCHERDETAILS": {
                "STOCKGROUPS": []
                }
            }
        return Response(json.dumps(final_voucher, default=str), content_type='application/json')

    synced_groups = frappe.get_all('Tally Master Sync Log',
        filters={'parenttype': 'Item Group', 'company_number': company_id, 'status': 'SUCCESS'},
        pluck='parent')

    # 1. Fetch ALL groups (we need the full tree to find children of synced parents)
    item_groups = frappe.get_all(
        "Item Group",
        fields=["name", "parent_item_group", "is_group"],
        limit=get_master_sync_limit()
    )

    def clean_tally_text(text):
        if not text: return text
        text = text.replace("&", "and").replace('"', "").replace("'", "")
        return " ".join(text.split())

    # 2. Build the tree using ALL items
    tree = {}
    for ig in item_groups:
        parent = clean_tally_text(ig.parent_item_group) if ig.parent_item_group else "ROOT"
        ig.name = clean_tally_text(ig.name)
        tree.setdefault(parent, []).append(ig)

    final_list = []
    seen_names = set()

    # 3. Recursive builder
    def add_to_list(parent_key, tally_parent_label):
        children = tree.get(parent_key, [])
        for child in children:
            if child.name in seen_names:
                continue

            # 4. ONLY ADD TO JSON IF IT IS NOT SYNCED for this company
            if child.name not in synced_groups:
                final_list.append({
                    "Autoid": child.name,
                    "CompanyNumber": company_id,
                    "Name": child.name,
                    "Parent": tally_parent_label,
                    "IsGroup": "Yes" if child.is_group else "No"
                })

            seen_names.add(child.name)

            # Keep recursing even if parent was already synced
            # so we can find unsynced children further down
            if child.name in tree:
                add_to_list(child.name, child.name)

    add_to_list("ROOT", "Primary")

    return Response(json.dumps({
        "status": True,
        "VOUCHERDETAILS": {
            "STOCKGROUPS": final_list
            }
    }, default=str), content_type="application/json")





@frappe.whitelist()
def fetch_response(response, company_id=None):

    data = json.loads(response) if isinstance(response, str) else response
    item_group_list = data.get("STOCKGROUP RESPONSE", [])

    company_name = frappe.get_value('TS Tally Company', {'company_number': company_id}, 'company_name') if company_id else None

    for item in item_group_list:
        item_group_name = item.get("AUTOID")
        status = item.get("STATUS")
        import_date = item.get("IMPORTDATE")
        import_time = item.get("IMPORTTIME")

        if not item_group_name:
            continue

        existing_item_group = frappe.db.get_value("Item Group", {"name": item_group_name}, "name")
        if existing_item_group:
            import_date_obj = datetime.strptime(import_date, "%Y%m%d").date()
            import_time_obj = datetime.strptime(import_time, "%H:%M:%S").time()
            sync_datetime = datetime.combine(import_date_obj, import_time_obj)

            existing = frappe.db.get_value('Tally Master Sync Log', {
                'parent': existing_item_group,
                'parenttype': 'Item Group',
                'company_number': company_id
            }, 'name')

            if existing:
                frappe.db.set_value('Tally Master Sync Log', existing, {
                    'tally_auto_id': item_group_name,
                    'status': status,
                    'sync_time': sync_datetime
                })
            else:
                max_idx = frappe.db.count('Tally Master Sync Log', {
                    'parent': existing_item_group,
                    'parenttype': 'Item Group'
                })

                sync_log = frappe.new_doc('Tally Master Sync Log')
                sync_log.parent = existing_item_group
                sync_log.parenttype = 'Item Group'
                sync_log.parentfield = 'custom_tally_sync_log'
                sync_log.idx = max_idx + 1
                sync_log.company_number = company_id
                sync_log.company_name = company_name
                sync_log.tally_auto_id = item_group_name
                sync_log.status = status
                sync_log.sync_time = sync_datetime
                sync_log.db_insert()

            frappe.db.set_value('Item Group', existing_item_group, 'modified', frappe.utils.now())

    frappe.db.commit()

    return Response(json.dumps({
        "status":True,
        "message":"Updated successfully"
    }, default=str), content_type='application/json')
