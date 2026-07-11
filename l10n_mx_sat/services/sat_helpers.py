# Copyright 2026 Gray Matter Logic
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

from datetime import datetime, time, timedelta

from lxml import etree
from pytz import UTC

from .sat_constants import MX_TZ


def sat_str(value):
    """Normalize SAT client values to str.

    XML attributes are usually text; tests may pass int. This ensures a
    consistent str regardless of source.
    """
    if value is None:
        return ""
    return str(value).strip()


def sat_int(value, default=0):
    """Safely cast a SAT numeric status to int.

    SAT SOAP responses may return raw attributes as str or None.
    """
    if value is None or value == "":
        return default
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return default


# Secure XML parser for any module that processes CFDI/SAT payloads.
# Prevents XXE attacks by disabling entity resolution and network access.
SAFE_XML_PARSER = etree.XMLParser(resolve_entities=False, no_network=True)


def utc_naive_to_mx_naive(dt):
    """Convert an Odoo UTC naive datetime to Mexico local naive."""
    if not dt:
        return dt
    return UTC.localize(dt).astimezone(MX_TZ).replace(tzinfo=None)


def mx_naive_to_utc_naive(dt):
    """Convert a Mexico local naive datetime to Odoo UTC naive."""
    if not dt:
        return dt
    return MX_TZ.localize(dt).astimezone(UTC).replace(tzinfo=None)


def mx_day_start(day):
    """Return Mexico local naive datetime at 00:00:00 for a calendar day."""
    return datetime.combine(day, time.min)


def mx_day_end(day):
    """Return Mexico local naive datetime at 23:59:59 for a calendar day."""
    return datetime.combine(day, time(23, 59, 59))


def normalize_sat_request_range_to_utc(date_from, date_to):
    """Expand a request range to full Mexico calendar days stored as UTC naive."""
    from_mx = utc_naive_to_mx_naive(date_from)
    to_mx = utc_naive_to_mx_naive(date_to)
    return (
        mx_naive_to_utc_naive(mx_day_start(from_mx.date())),
        mx_naive_to_utc_naive(mx_day_end(to_mx.date())),
    )


def sat_request_datetimes_for_send(date_from, date_to):
    """Return Mexico local naive datetimes for the SAT web service."""
    from_mx = utc_naive_to_mx_naive(date_from)
    to_mx = utc_naive_to_mx_naive(date_to)
    return mx_day_start(from_mx.date()), mx_day_end(to_mx.date())


def mx_calendar_days_between(date_from, date_to):
    """Return inclusive Mexico calendar day count for a stored UTC range."""
    from_mx = utc_naive_to_mx_naive(date_from)
    to_mx = utc_naive_to_mx_naive(date_to)
    return (to_mx.date() - from_mx.date()).days + 1


def split_sat_request_range_by_days(date_from, date_to):
    """Split a UTC range into two contiguous full-day Mexico ranges."""
    from_mx = utc_naive_to_mx_naive(date_from)
    to_mx = utc_naive_to_mx_naive(date_to)
    from_day = from_mx.date()
    to_day = to_mx.date()
    total_days = (to_day - from_day).days + 1
    if total_days <= 1:
        return None

    first_half_days = total_days // 2
    split_end_day = from_day + timedelta(days=first_half_days - 1)
    second_start_day = split_end_day + timedelta(days=1)

    first_range = (
        mx_naive_to_utc_naive(mx_day_start(from_day)),
        mx_naive_to_utc_naive(mx_day_end(split_end_day)),
    )
    second_range = (
        mx_naive_to_utc_naive(mx_day_start(second_start_day)),
        mx_naive_to_utc_naive(mx_day_end(to_day)),
    )
    return first_range, second_range
