# Copyright (c) 2026, Alaiy and contributors
# For license information, please see license.txt
"""The chat tool that turns an attached sheet into a batch.

The bug this closes is not an exception anywhere — it is a model that previews ten
rows of a fifty-row file, invents the other forty by cycling those ten, and reports a
complete enrichment. So the property under test is that the rows never pass through
the model: `run` reads the file itself and hands identifiers straight to
`api.bulk_enrich`.

What matters here is therefore the reading, the gating and the reporting — not the
fan-out. `api.bulk_enrich` is patched out in `TestRun`; what it does with a list of
identifiers belongs to its own tests.

The parsing tests touch nothing. The rest need a site.
"""

import unittest
from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase

from alaiy_os_agents.agents.listing import chat_tools

BULK = "alaiy_os_agents.agents.listing.api.bulk_enrich"

# The shape that broke: headers padded by the export, ids long enough that a float
# round-trip would corrupt them, and a trailing comment column that is entirely empty.
SHEET = (
	"Offer id , Variant id ,commets \n"
	"750113457575180,4457730620593,\n"
	"750113457575180,4457730620594,\n"
	"750113457575180,4457730620595,\n"
)


class TestColumnResolution(unittest.TestCase):
	headers = ["Offer id ", " Variant id ", "commets "]

	def test_a_padded_header_is_matched_on_its_stripped_form(self):
		self.assertEqual(chat_tools._resolve_column(self.headers, "Variant id"), " Variant id ")

	def test_the_match_ignores_case(self):
		self.assertEqual(chat_tools._resolve_column(self.headers, "VARIANT ID"), " Variant id ")

	def test_omitting_the_column_names_the_ones_there_are(self):
		with self.assertRaises(frappe.ValidationError) as caught:
			chat_tools._resolve_column(self.headers, None)
		# The model's next move has to be in the error, or it guesses.
		self.assertIn("Variant id", str(caught.exception))
		self.assertIn("Offer id", str(caught.exception))

	def test_an_unknown_column_names_them_too(self):
		with self.assertRaises(frappe.ValidationError) as caught:
			chat_tools._resolve_column(self.headers, "Nonsense")
		self.assertIn("Offer id", str(caught.exception))


class TestIdentifiers(unittest.TestCase):
	def test_values_are_read_in_file_order_without_repeats(self):
		rows = [{"id": "A"}, {"id": "B"}, {"id": "A"}, {"id": "C"}]
		self.assertEqual(chat_tools._identifiers(rows, "id"), ["A", "B", "C"])

	def test_blank_and_whitespace_cells_are_dropped_not_counted(self):
		rows = [{"id": "A"}, {"id": ""}, {"id": "   "}, {"id": None}, {"id": " B "}]
		self.assertEqual(chat_tools._identifiers(rows, "id"), ["A", "B"])

	def test_long_numeric_ids_stay_strings(self):
		# pandas would make this column float the moment one cell is empty, and
		# 4457730620593.0 resolves to nothing. See _read_csv.
		rows = [{"id": "4457730620593"}, {"id": "4457730620594"}]
		self.assertEqual(chat_tools._identifiers(rows, "id"), ["4457730620593", "4457730620594"])


class TestSourceGate(IntegrationTestCase):
	"""A `chat_tool_sources` contribution is not gated on `is_enabled` by core —
	`_surface` takes tenant tools straight through `_provided`. The source has to
	do it, or disabling the listing agent stops being a complete off switch."""

	def enabled(self, flag):
		frappe.db.set_value("OS Agent Registry", chat_tools.AGENT_ID, "is_enabled", flag)

	def test_a_disabled_agent_offers_no_bulk_tool(self):
		if not frappe.db.exists("OS Agent Registry", chat_tools.AGENT_ID):
			self.skipTest("the listing agent is not registered on this site")
		self.enabled(0)
		self.assertIsNone(chat_tools.source())

	def test_an_enabled_agent_offers_it(self):
		if not frappe.db.exists("OS Agent Registry", chat_tools.AGENT_ID):
			self.skipTest("the listing agent is not registered on this site")
		self.enabled(1)
		source = chat_tools.source()
		self.assertEqual([tool["name"] for tool in source["tools"]], [chat_tools.TOOL])


class TestRun(IntegrationTestCase):
	def setUp(self):
		if frappe.db.exists("OS Agent Registry", chat_tools.AGENT_ID):
			frappe.db.set_value("OS Agent Registry", chat_tools.AGENT_ID, "is_enabled", 1)

	def sheet(self, content=SHEET, file_name="products.csv"):
		"""A private, unattached File — what a chat attachment is."""
		doc = frappe.get_doc(
			{
				"doctype": "File",
				"file_name": f"{frappe.generate_hash(length=6)}-{file_name}",
				"is_private": 1,
				"content": content,
			}
		).insert(ignore_permissions=True)
		return doc.file_url

	def test_every_row_reaches_the_batch_not_just_the_previewed_ones(self):
		file_url = self.sheet()
		with patch(BULK) as bulk:
			bulk.return_value = {"batch": "B1", "resolved": ["a", "b", "c"], "errors": {}}
			result = chat_tools.run({"file_url": file_url, "column": "Variant id"})

		self.assertEqual(
			bulk.call_args[0][0],
			["4457730620593", "4457730620594", "4457730620595"],
		)
		self.assertEqual(result["identifiers_read"], 3)

	def test_the_result_says_started_rather_than_finished(self):
		# The model reported a queued batch as an enriched catalogue. The payload has
		# to make that distinction unavailable.
		file_url = self.sheet()
		with patch(BULK) as bulk:
			bulk.return_value = {"batch": "B1", "resolved": ["a"], "errors": {}}
			result = chat_tools.run({"file_url": file_url, "column": "Variant id"})

		self.assertEqual(result["state"], "started")
		self.assertEqual(result["link"], "/app/listing-bulk-enrich/B1")
		self.assertIn("NOT finished", result["note"])

	def test_unresolvable_identifiers_are_reported_beside_the_ones_that_ran(self):
		file_url = self.sheet()
		with patch(BULK) as bulk:
			bulk.return_value = {
				"batch": "B1",
				"resolved": ["4457730620593"],
				"errors": {"4457730620594": "not found", "4457730620595": "not found"},
			}
			result = chat_tools.run({"file_url": file_url, "column": "Variant id"})

		self.assertEqual(len(result["errors"]), 2)
		self.assertIn("1 of 3", result["note"])

	def test_registering_is_off_unless_asked_for(self):
		# It writes a listing record per product. A model enriching a sheet must not
		# create records as a side effect of not passing an argument.
		file_url = self.sheet()
		with patch(BULK) as bulk:
			bulk.return_value = {"batch": "B1", "resolved": ["a"], "errors": {}}
			chat_tools.run({"file_url": file_url, "column": "Variant id"})
		self.assertFalse(bulk.call_args.kwargs["register"])

	def test_a_missing_file_says_so_rather_than_starting_an_empty_batch(self):
		with patch(BULK) as bulk:
			with self.assertRaises(frappe.ValidationError):
				chat_tools.run({"file_url": "/private/files/nope.csv", "column": "Variant id"})
		bulk.assert_not_called()

	def test_a_column_of_empty_cells_starts_nothing(self):
		file_url = self.sheet()
		with patch(BULK) as bulk:
			with self.assertRaises(frappe.ValidationError):
				chat_tools.run({"file_url": file_url, "column": "commets"})
		bulk.assert_not_called()

	def test_a_sheet_past_the_cap_starts_nothing(self):
		rows = "\n".join(str(n) for n in range(chat_tools.MAX_ROWS + 1))
		file_url = self.sheet(content=f"id\n{rows}\n")
		with patch(BULK) as bulk:
			with self.assertRaises(frappe.ValidationError) as caught:
				chat_tools.run({"file_url": file_url, "column": "id"})
		self.assertIn(str(chat_tools.MAX_ROWS), str(caught.exception))
		bulk.assert_not_called()
