# Copyright 2026 Gray Matter Logic
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

from datetime import date, datetime, timedelta

from lxml import etree

from odoo.tests import tagged
from odoo.tests.common import TransactionCase

from ..services.sat_helpers import (
    SAFE_XML_PARSER,
    mx_day_end,
    mx_day_start,
    mx_naive_to_utc_naive,
    normalize_sat_request_range_to_utc,
    sat_int,
    sat_request_datetimes_for_send,
    sat_str,
    split_sat_request_range_by_days,
    split_sat_request_range_single_day,
    utc_naive_to_mx_naive,
)


@tagged("post_install", "-at_install")
class TestSatHelpers(TransactionCase):
    """Unit tests for SAT helper functions executed by Odoo."""

    def test_sat_str_none_returns_empty(self):
        self.assertEqual(sat_str(None), "")

    def test_sat_str_int_coerced_to_str(self):
        self.assertEqual(sat_str(5000), "5000")

    def test_sat_str_whitespace_stripped(self):
        self.assertEqual(sat_str("  5004  "), "5004")

    def test_sat_str_normal_passthrough(self):
        self.assertEqual(sat_str("abc"), "abc")

    def test_sat_int_none_returns_default(self):
        self.assertEqual(sat_int(None), 0)

    def test_sat_int_empty_returns_default(self):
        self.assertEqual(sat_int(""), 0)

    def test_sat_int_string_number(self):
        self.assertEqual(sat_int("3"), 3)

    def test_sat_int_passthrough(self):
        self.assertEqual(sat_int(3), 3)

    def test_sat_int_invalid_returns_default(self):
        self.assertEqual(sat_int("abc"), 0)

    def test_sat_int_custom_default(self):
        self.assertEqual(sat_int(None, -1), -1)

    def test_sat_int_whitespace_stripped(self):
        self.assertEqual(sat_int("  42  "), 42)

    def test_safe_xml_parser_parses_valid_xml(self):
        xml = b"<root><child>text</child></root>"
        tree = etree.fromstring(xml, SAFE_XML_PARSER)
        self.assertEqual(tree.tag, "root")

    def test_safe_xml_parser_does_not_resolve_xxe_entity(self):
        xxe = (
            b'<?xml version="1.0"?>'
            b"<!DOCTYPE foo ["
            b'  <!ENTITY xxe SYSTEM "file:///etc/passwd">'
            b"]>"
            b"<root>&xxe;</root>"
        )
        root = etree.fromstring(xxe, SAFE_XML_PARSER)
        self.assertIsNone(root.text)

    def test_normalize_sat_request_range_to_utc_expands_mx_days(self):
        date_from = datetime(2026, 2, 15, 14, 30, 0)
        date_to = datetime(2026, 2, 20, 10, 0, 0)
        norm_from, norm_to = normalize_sat_request_range_to_utc(date_from, date_to)
        self.assertEqual(
            utc_naive_to_mx_naive(norm_from),
            mx_day_start(date(2026, 2, 15)),
        )
        self.assertEqual(
            utc_naive_to_mx_naive(norm_to),
            mx_day_end(date(2026, 2, 20)),
        )

    def test_sat_request_datetimes_for_send_returns_mx_boundaries(self):
        norm_from, norm_to = normalize_sat_request_range_to_utc(
            datetime(2026, 2, 15, 14, 30, 0),
            datetime(2026, 2, 20, 10, 0, 0),
        )
        send_from, send_to = sat_request_datetimes_for_send(norm_from, norm_to)
        self.assertEqual(send_from, datetime(2026, 2, 15, 0, 0, 0))
        self.assertEqual(send_to, datetime(2026, 2, 20, 23, 59, 59))

    def test_sat_request_datetimes_for_send_keeps_same_day_partial_range(self):
        date_from = mx_naive_to_utc_naive(datetime(2026, 2, 1, 0, 0, 0))
        date_to = mx_naive_to_utc_naive(datetime(2026, 2, 1, 11, 59, 59))
        send_from, send_to = sat_request_datetimes_for_send(date_from, date_to)
        self.assertEqual(send_from, datetime(2026, 2, 1, 0, 0, 0))
        self.assertEqual(send_to, datetime(2026, 2, 1, 11, 59, 59))

    def test_split_sat_request_range_by_days_returns_contiguous_ranges(self):
        date_from = mx_naive_to_utc_naive(mx_day_start(date(2026, 2, 1)))
        date_to = mx_naive_to_utc_naive(mx_day_end(date(2026, 2, 10)))
        split_ranges = split_sat_request_range_by_days(date_from, date_to)
        self.assertIsNotNone(split_ranges)
        (first_from, first_to), (second_from, second_to) = split_ranges
        self.assertEqual(utc_naive_to_mx_naive(first_from).date(), date(2026, 2, 1))
        self.assertEqual(utc_naive_to_mx_naive(first_to).date(), date(2026, 2, 5))
        self.assertEqual(
            utc_naive_to_mx_naive(second_from).date(),
            date(2026, 2, 6),
        )
        self.assertEqual(utc_naive_to_mx_naive(second_to).date(), date(2026, 2, 10))

    def test_split_sat_request_range_by_days_rejects_single_day(self):
        date_from = mx_naive_to_utc_naive(mx_day_start(date(2026, 2, 1)))
        date_to = mx_naive_to_utc_naive(mx_day_end(date(2026, 2, 1)))
        self.assertIsNone(split_sat_request_range_by_days(date_from, date_to))

    def test_split_sat_request_range_single_day_returns_partial_ranges(self):
        date_from = mx_naive_to_utc_naive(mx_day_start(date(2026, 2, 1)))
        date_to = mx_naive_to_utc_naive(mx_day_end(date(2026, 2, 1)))
        split_ranges = split_sat_request_range_single_day(date_from, date_to)
        self.assertIsNotNone(split_ranges)
        (first_from, first_to), (second_from, second_to) = split_ranges
        self.assertEqual(utc_naive_to_mx_naive(first_from).date(), date(2026, 2, 1))
        self.assertEqual(utc_naive_to_mx_naive(first_to).date(), date(2026, 2, 1))
        self.assertEqual(
            utc_naive_to_mx_naive(second_from).date(),
            date(2026, 2, 1),
        )
        self.assertEqual(utc_naive_to_mx_naive(second_to).date(), date(2026, 2, 1))
        self.assertGreater(
            utc_naive_to_mx_naive(second_from),
            utc_naive_to_mx_naive(first_to),
        )

    def test_split_sat_request_range_single_day_rejects_min_window(self):
        date_from = mx_naive_to_utc_naive(datetime(2026, 2, 1, 0, 0, 0))
        date_to = mx_naive_to_utc_naive(datetime(2026, 2, 1, 0, 30, 0))
        self.assertIsNone(split_sat_request_range_single_day(date_from, date_to))
