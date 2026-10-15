(function () {
	if (window.tally_master_sync_log_action_registered) return;
	window.tally_master_sync_log_action_registered = true;

	const MASTER_DOCTYPES = [
		"Customer",
		"Supplier",
		"Item",
		"Account",
		"Item Group",
		"Warehouse",
	];

	function attach(listview) {
		if (frappe.session.user !== "Administrator") return;

		listview.page.add_actions_menu_item(
			__("Set Manual Tally Sync Log"),
			function () {
				const selected = listview.get_checked_items();
				if (!selected || !selected.length) {
					frappe.msgprint(__("Please select at least one record"));
					return;
				}
				const names = selected.map((d) => d.name);

				frappe.prompt(
					[
						{
							fieldname: "company",
							fieldtype: "Link",
							label: __("Company"),
							options: "Company",
							reqd: 1,
						},
					],
					function (values) {
						frappe.confirm(
							__(
								"Mark {0} selected {1} as synced to Tally for company {2}?",
								[names.length, __(listview.doctype), values.company]
							),
							function () {
								frappe.call({
									method:
										"ts_tally_integration.tally_integration.utils.py.remove_master_sync_log.bulk_manual_master_sync_log",
									args: {
										doctype: listview.doctype,
										names: names,
										company: values.company,
									},
									freeze: true,
									freeze_message: __("Setting Tally sync log..."),
									callback: function (r) {
										const msg = r.message || {};
										const updated = (msg.updated || []).length;
										const failed = (msg.failed || []).length;
										if (updated) {
											frappe.show_alert({
												message: __(
													"Set manual sync log on {0} record(s)",
													[updated]
												),
												indicator: "green",
											});
										}
										if (failed) {
											frappe.show_alert({
												message: __("Failed for {0} record(s)", [failed]),
												indicator: "red",
											});
										}
										listview.refresh();
									},
								});
							}
						);
					},
					__("Select Company"),
					__("Set")
				);
			},
			false
		);

		listview.page.add_actions_menu_item(
			__("Clear Tally Sync Log"),
			function () {
				const selected = listview.get_checked_items();
				if (!selected || !selected.length) {
					frappe.msgprint(__("Please select at least one record"));
					return;
				}
				const names = selected.map((d) => d.name);

				frappe.prompt(
					[
						{
							fieldname: "company",
							fieldtype: "Link",
							label: __("Company"),
							options: "Company",
							reqd: 1,
						},
					],
					function (values) {
						frappe.confirm(
							__(
								"Clear Tally Sync Log for company {0} from {1} selected {2}?",
								[values.company, names.length, __(listview.doctype)]
							),
							function () {
								frappe.call({
									method:
										"ts_tally_integration.tally_integration.utils.py.remove_master_sync_log.bulk_remove_master_sync_log",
									args: {
										doctype: listview.doctype,
										names: names,
										company: values.company,
									},
									freeze: true,
									freeze_message: __("Clearing Tally sync log..."),
									callback: function (r) {
										const msg = r.message || {};
										const cleared = (msg.cleared || []).length;
										const failed = (msg.failed || []).length;
										if (cleared) {
											frappe.show_alert({
												message: __(
													"Cleared sync log on {0} record(s)",
													[cleared]
												),
												indicator: "green",
											});
										}
										if (failed) {
											frappe.show_alert({
												message: __("Failed for {0} record(s)", [failed]),
												indicator: "red",
											});
										}
										listview.refresh();
									},
								});
							}
						);
					},
					__("Select Company"),
					__("Clear")
				);
			},
			false
		);
	}

	MASTER_DOCTYPES.forEach(function (dt) {
		frappe.listview_settings[dt] = frappe.listview_settings[dt] || {};
		const original_onload = frappe.listview_settings[dt].onload;
		frappe.listview_settings[dt].onload = function (listview) {
			if (typeof original_onload === "function") {
				original_onload(listview);
			}
			attach(listview);
		};
	});
})();
