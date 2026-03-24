"""Australian-specific helpers — ABN validation, timezone, etc."""

import httpx


ABR_LOOKUP_URL = "https://abr.business.gov.au/json/AbnDetails.aspx"


async def lookup_abn(abn: str, guid: str) -> dict | None:
    """Look up an ABN via the Australian Business Register API.

    Args:
        abn: The Australian Business Number to look up (11 digits).
        guid: Your ABR API GUID (register free at abr.business.gov.au).

    Returns:
        Dict with business name, status, state, postcode, etc. or None if not found.
    """
    clean_abn = abn.replace(" ", "")
    if len(clean_abn) != 11 or not clean_abn.isdigit():
        return None

    async with httpx.AsyncClient() as client:
        resp = await client.get(ABR_LOOKUP_URL, params={
            "abn": clean_abn,
            "callback": "",
            "guid": guid,
        })

    if resp.status_code != 200:
        return None

    # ABR returns JSONP — strip the callback wrapper
    text = resp.text.strip()
    if text.startswith("callback("):
        text = text[9:-1]

    import json
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return None

    if not data.get("Abn"):
        return None

    return {
        "abn": data["Abn"],
        "name": data.get("EntityName", ""),
        "status": data.get("AbnStatus", ""),
        "state": data.get("AddressState", ""),
        "postcode": data.get("AddressPostcode", ""),
        "entity_type": data.get("EntityTypeCode", ""),
        "is_active": data.get("AbnStatus", "").lower() == "active",
    }


def validate_abn_checksum(abn: str) -> bool:
    """Validate an ABN using the official checksum algorithm.

    The ABN is 11 digits. Subtract 1 from the first digit, then apply
    weights [10, 1, 3, 5, 7, 9, 11, 13, 15, 17, 19] and check if
    the weighted sum is divisible by 89.
    """
    clean = abn.replace(" ", "")
    if len(clean) != 11 or not clean.isdigit():
        return False

    digits = [int(d) for d in clean]
    digits[0] -= 1  # subtract 1 from first digit

    weights = [10, 1, 3, 5, 7, 9, 11, 13, 15, 17, 19]
    total = sum(d * w for d, w in zip(digits, weights))

    return total % 89 == 0


def aest_offset_hours() -> int:
    """Return the current UTC offset for AEST/AEDT.

    AEST = UTC+10, AEDT = UTC+11 (first Sunday in October to first Sunday in April).
    """
    from datetime import datetime, timezone, timedelta
    import calendar

    now = datetime.now(timezone.utc)
    year = now.year

    # AEDT starts: first Sunday in October
    oct_first = datetime(year, 10, 1, tzinfo=timezone.utc)
    days_until_sunday = (6 - oct_first.weekday()) % 7
    aedt_start = oct_first + timedelta(days=days_until_sunday, hours=2)  # 2am AEST

    # AEDT ends: first Sunday in April
    apr_first = datetime(year, 4, 1, tzinfo=timezone.utc)
    days_until_sunday = (6 - apr_first.weekday()) % 7
    aedt_end = apr_first + timedelta(days=days_until_sunday, hours=3)  # 3am AEDT

    if aedt_start <= now or now < aedt_end:
        return 11  # AEDT
    return 10  # AEST
