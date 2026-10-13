import frappe
from ts_tally_integration.tally_integration.utils.api.sync_settings import company_filters, company_sync_required
from ts_tally_integration.tally_integration.utils.api.sync_settings import get_voucher_sync_limit
import json
from datetime import datetime
from werkzeug.wrappers import Response
from frappe.utils import getdate, today


@frappe.whitelist()
@company_sync_required("VOUCHER")
def get_contra(company_id = None):
    if company_id == None:
        return Response(json.dumps("Company number not found!", default=str), content_type='application/json')

    enable_sync = frappe.get_value('Voucher Sync Control', {'voucher_name': 'Contra Entry'}, ['enable_sync'])
    if not enable_sync:
        final_voucher = {
            "status": True,
            "VOUCHERDETAILS": {
                "VOUCHER": []
                }
            }
        return Response(json.dumps(final_voucher, default=str), content_type='application/json')


    company_name = frappe.get_value('TS Tally Company', company_filters(company_id), ['company_name'])
    cost_center = frappe.get_value('TS Tally Company', company_filters(company_id), ['cost_center'])

    sync_from = frappe.get_value('TS Tally Company',company_filters(company_id),'sync_from')

    start_date = getdate(sync_from)
    sync_to = frappe.get_value('TS Tally Company', company_filters(company_id), 'sync_to')
    end_date = getdate(sync_to) if sync_to else getdate(today())

    all_vouchers = []

    contra_filters = {'company':company_name,'voucher_type':'Contra Entry',
                                            'custom_tally_guid': ['is', 'not set'], 'posting_date': ['between', [start_date, end_date]]}
    if cost_center:
        contra_filters['cost_center'] = cost_center
    journal_list = frappe.get_all('Journal Entry',
                                   filters=contra_filters,
                                   fields=['*'], order_by='posting_date asc', limit=get_voucher_sync_limit())
    for list in journal_list:
        journal_gl_entry = frappe.get_all('GL Entry', filters = {'voucher_no':list.name}, fields = ['*'])

        for entry in journal_gl_entry:
            parent_account = frappe.get_value('Account', entry['account'], 'custom_tally_parent_account')

            cr_dr = "Dr" if entry['debit_in_account_currency'] else "Cr"
            amount = entry['debit_in_account_currency'] or entry['credit_in_account_currency']

            ledger_dict = {
                "Autoid": list['name'],
                "CompanyNumber": str(company_id),
                "TallyMasterid": 1,
                "Voucherid": "",
                "VoucherNumber": list['name'],
                "VoucherDate": list['posting_date'].strftime('%d-%m-%Y'),
                "VoucherType": 'ERP Contra',
                "VoucherTypeParent": "Contra",
                "LedgerName": (entry['account']).split(" - ")[0],
                "LedgerParent": parent_account,
                "LedgerAddress": "",
                "LedgerState": "",
                "LedgerCountry": "",
                "LedgerPincode": "",
                "LedgerMobile": "",
                "LedgerGstReg": "",
                "LedgerGstin": "",
                "LedgerPan": None,
                "BillName": "",
                "BillDate": "",
                "PlaceOfSupply": "",
                "TransactionDate": list['posting_date'].strftime('%d-%m-%Y'),
                "CrDr": cr_dr,
                "Amount": amount,
                "CostCategory": "",
                "CostCentre": entry['cost_center'].split('-')[0],
                "BranchCode": "",
                "Location": "",
                "State": "",
                "Narration": None
            }
            all_vouchers.append(ledger_dict)

    final_voucher = ({
        "status": True,
        "VOUCHERDETAILS": {
            "VOUCHER": all_vouchers
        }
    })
    final_voucher = Response(json.dumps(final_voucher, default=str), content_type='application/json')
    final_voucher.status_code = 200


    return final_voucher


@frappe.whitelist()
def fetch_response(response):
    data = json.loads(response) if isinstance(response, str) else response
    contra_response = data.get("CONTRA RESPONSE", [])

    for response in contra_response:
        contra_entry = response.get("AUTOID")
        guid = response.get("GUID")
        ref_no = response.get("REFNO")
        import_date = response.get("IMPORTDATE")
        import_time = response.get("IMPORTTIME")

        if not contra_entry:
            continue

        existing_journal = frappe.db.get_value("Journal Entry", {"name": contra_entry}, "name")
        if existing_journal:
            import_date = datetime.strptime(import_date, "%Y%m%d").date()
            import_time = datetime.strptime(import_time, "%H:%M:%S").time()

            frappe.db.set_value("Journal Entry", existing_journal, {
                "custom_tally_auto_id": existing_journal,
                "custom_tally_guid": guid,
                "custom_tally_refno": ref_no,
                "custom_sync_time": datetime.combine(import_date, import_time)
            })

    frappe.db.commit()

    response =  {
        "status":True,
        "message":"Updated successfully"
        }
    return Response(json.dumps(response, default=str), content_type='application/json')
