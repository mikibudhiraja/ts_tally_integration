import frappe
from ts_tally_integration.tally_integration.utils.api.sync_settings import company_filters, company_sync_required
from ts_tally_integration.tally_integration.utils.api.sync_settings import get_master_sync_limit
import json
from datetime import datetime
from werkzeug.wrappers import Response

@frappe.whitelist()
@company_sync_required("GODOWNS")
def get_warehouse(company_id = None):
    if company_id == None:
        return Response(json.dumps("Company number not found!", default=str), content_type='application/json')


    enable_sync = frappe.get_value('Voucher Sync Control', {'voucher_name': 'Warehouse'}, ['enable_sync'])

    if not enable_sync:
        final_voucher = {
            "status": True,
            "VOUCHERDETAILS": {
                "GODOWNS": []
                }
            }
        return Response(json.dumps(final_voucher, default=str), content_type='application/json')

    company_name = frappe.get_value('TS Tally Company', company_filters(company_id), ['company_name'])

    synced_warehouses = frappe.get_all('Tally Master Sync Log',
        filters={'parenttype': 'Warehouse', 'company_number': company_id, 'status': 'SUCCESS'},
        pluck='parent')

    group_warehouse = []
    nongroup = []

    warehouses = frappe.get_all('Warehouse',
                                filters={'company': company_name, 'name': ['not in', synced_warehouses]},
                                fields=['*'], limit=get_master_sync_limit())

    for warehouse in warehouses:
        if warehouse.is_group:
            warehouse_dict = {
                    "Autoid": warehouse.warehouse_name,
                    "CompanyNumber": str(company_id),
                    "Name": warehouse.warehouse_name,
                    "Parent": frappe.get_value('Warehouse', {'name': warehouse.parent_warehouse}, 'warehouse_name') if warehouse.parent_warehouse else "Primary",
                    "ADDRESS1": "",
                    "ADDRESS2": "",
                    "ADDRESS3": "",
                    "ADDRESS4": ""
                }

            group_warehouse.append(warehouse_dict)

        if not warehouse.is_group:
            warehouse_dict = {
                    "Autoid": warehouse.warehouse_name,
                    "CompanyNumber": str(company_id),
                    "Name": warehouse.warehouse_name,
                    "Parent": frappe.get_value('Warehouse', {'name': warehouse.parent_warehouse}, 'warehouse_name') if warehouse.parent_warehouse else "Primary",
                    "ADDRESS1": "",
                    "ADDRESS2": "",
                    "ADDRESS3": "",
                    "ADDRESS4": ""
                }

            nongroup.append(warehouse_dict)

    final_voucher = ({
        "status": True,
        "VOUCHERDETAILS": {
            "GODOWNS": group_warehouse + nongroup
        }
    })

    final_voucher = Response(json.dumps(final_voucher, default=str), content_type='application/json')
    final_voucher.status_code = 200

    return final_voucher


@frappe.whitelist()
def fetch_response(response, company_id=None):
    data = json.loads(response) if isinstance(response, str) else response
    warehouse_response = data.get("GODOWN RESPONSE", [])

    company_name = frappe.get_value('TS Tally Company', {'company_number': company_id}, 'company_name') if company_id else None

    for warehouse in warehouse_response:
        warehouse_name = warehouse.get("AUTOID")
        status = warehouse.get("STATUS")
        import_date = warehouse.get("IMPORTDATE")
        import_time = warehouse.get("IMPORTTIME")

        if not warehouse_name:
            continue

        existing_warehouse = frappe.db.get_value("Warehouse", {"warehouse_name": warehouse_name}, "name")
        if existing_warehouse:
            import_date = datetime.strptime(import_date, "%Y%m%d").date()
            import_time = datetime.strptime(import_time, "%H:%M:%S").time()
            sync_time = datetime.combine(import_date, import_time)

            existing = frappe.db.get_value('Tally Master Sync Log', {
                'parent': existing_warehouse,
                'parenttype': 'Warehouse',
                'company_number': company_id
            }, 'name')

            if existing:
                frappe.db.set_value('Tally Master Sync Log', existing, {
                    'tally_auto_id': warehouse_name,
                    'status': status,
                    'sync_time': sync_time
                })
            else:
                max_idx = frappe.db.count('Tally Master Sync Log', {
                    'parent': existing_warehouse,
                    'parenttype': 'Warehouse'
                })

                sync_log = frappe.new_doc('Tally Master Sync Log')
                sync_log.parent = existing_warehouse
                sync_log.parenttype = 'Warehouse'
                sync_log.parentfield = 'custom_tally_sync_log'
                sync_log.idx = max_idx + 1
                sync_log.company_number = company_id
                sync_log.company_name = company_name
                sync_log.tally_auto_id = warehouse_name
                sync_log.status = status
                sync_log.sync_time = sync_time
                sync_log.db_insert()

            frappe.db.set_value('Warehouse', existing_warehouse, 'modified', frappe.utils.now())

    frappe.db.commit()

    response =  {
        "status":True,
        "message":"Updated successfully"
        }
    return Response(json.dumps(response, default=str), content_type='application/json')
