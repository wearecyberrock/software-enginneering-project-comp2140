"""Read photo URLs from current and legacy inventory records."""

import json


def parse_photo_urls(raw):
    """photo_urls is stored as a JSON array of URLs; bad data must not crash the page."""
    if not raw:
        return []
    if isinstance(raw, list):
        data = raw
    else:
        try:
            data = json.loads(raw)
        except (TypeError, ValueError):
            data = str(raw).split(",")
    if isinstance(data, str):
        data = [data]
    if not isinstance(data, list):
        return []
    return [item.strip() for item in data if isinstance(item, str) and item.strip()]
