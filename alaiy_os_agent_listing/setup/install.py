"""
Install / migrate plumbing for the listing agent:

  sync_agent_registry  -> (re)register it in OS Agent Registry
  unregister           -> remove its registry row on uninstall

You should not need to edit this to add a customer, or to add a channel. A
customer app overrides the prompt by dropping a markdown file at
`<app>/agents/listing.md` (see agent_meta.py); a channel arrives through the
`listing_channels` hook at run time (see channels.py) and does not touch the
registry row at all.

It runs from this app's after_install/after_migrate, which a plain `bench migrate`
reaches on every pass — so editing the prompt or a customer's override and
migrating is enough to reconcile it onto the site.

The agent engine, run history (OS Agent Run) and the LLM-tool loop all live in
alaiy_os; this app owns one agent definition and its generic tools, so there is no
client, scheduler or sync log here.
"""

import json

import frappe

# Fields written from the manifest on every reconcile. is_enabled is deliberately
# excluded: it is admin-controlled (toggled in the Desk form) and must survive
# migrates, so it is only ever set by the DocType default on the first insert.
_RUNTIME_FIELDS = {"is_enabled"}

# Manifest keys consumed by the desk surfaces, not by the registry.
_NON_REGISTRY_FIELDS = {"agent_id", "tools", "input_options", "override_app"}

# Manifest values that are dicts here and Code fields on the DocType. Without the
# dump they reach `doc.set` as a dict and are stored as a Python repr — which
# `json.loads` then refuses, so `chat/skills.py` logs the pack and treats the
# skill as taking no arguments. Silent, and only visible as a skill that rejects
# every argument you give it.
_JSON_FIELDS = ("output_schema", "input_schema")


def sync_agent_registry():
	"""
	Reconcile alaiy_os's OS Agent Registry: upsert the one `listing` row. Called on
	install and every migrate. Idempotent.

	No pruning pass here, unlike the channel-specific agents this supersedes. Those
	each deleted rows they recognised as their own, which was how a rename
	converged; there is only one listing agent now and its id is fixed, so there is
	nothing to converge. The superseded `amazon_listing` / `shopify_listing` rows
	are removed by their own apps' patches, which is where the ownership sits.
	"""
	# alaiy_os may not be migrated yet on a fresh bench; bail and let our own next
	# migrate catch it.
	if not frappe.db.exists("DocType", "OS Agent Registry"):
		return

	from alaiy_os_agent_listing.agent_meta import build_agent_meta

	_upsert_agent(build_agent_meta())
	frappe.db.commit()


def _upsert_agent(agent_meta):
	agent_id = agent_meta["agent_id"]

	if frappe.db.exists("OS Agent Registry", agent_id):
		doc = frappe.get_doc("OS Agent Registry", agent_id)
	else:
		doc = frappe.new_doc("OS Agent Registry")
		doc.agent_id = agent_id

	for key, val in agent_meta.items():
		if key in _NON_REGISTRY_FIELDS or key in _RUNTIME_FIELDS:
			continue
		if key in _JSON_FIELDS and isinstance(val, dict):
			val = json.dumps(val, indent=1)
		doc.set(key, val)

	doc.set(
		"tools",
		[
			{
				"tool_id": tool["tool_id"],
				"description": tool["description"],
				"handler": tool["handler"],
				"parameters_schema": (
					json.dumps(tool["parameters_schema"], indent=1)
					if isinstance(tool.get("parameters_schema"), dict)
					else tool.get("parameters_schema")
				),
				"connector": tool.get("connector"),
				# Everything but save_listing reads. Marking the writer is what keeps
				# it out of Ask Alaiy's directly-callable tool surface, so a listing is
				# only ever written by a run that went through the channel's rules —
				# see chat/tools.py:_pack_tools.
				"effect": "write" if tool["tool_id"] == "save_listing" else "read",
			}
			for tool in agent_meta.get("tools", [])
		],
	)

	# save() inserts when new. The OS Agent Tool child controller validates each
	# handler dotted path here, so a broken tool fails at migrate, not mid-run.
	doc.save(ignore_permissions=True)


def unregister():
	"""
	Remove the listing agent's OS Agent Registry row on uninstall. OS Agent Run
	history is intentionally left intact for audit.

	force=True is what makes that possible: every past OS Agent Run links to the
	agent, so the default link check refuses the delete and the whole uninstall
	dies on LinkExistsError the moment the agent has ever been run. The runs keep
	their agent id as recorded history; they simply no longer point at a live row.
	"""
	from alaiy_os_agent_listing.agent_meta import AGENT_ID

	if frappe.db.exists("OS Agent Registry", AGENT_ID):
		frappe.delete_doc("OS Agent Registry", AGENT_ID, force=True, ignore_permissions=True)
	frappe.db.commit()
