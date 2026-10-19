import json

import pandas as pd


# The card templates index rows by position, so the DataFrame columns must stay in this order.
REQUIRED_DATA_COLUMNS = ["Workshop", "Description", "Days", "Level", "Category", "Location", "Calendar"]

# List internal names (permanent; display names can be renamed freely) -> DataFrame column.
DATA_FIELDS = {
    "Title": "Workshop",
    "field_1": "Description",
    "field_2": "Days",
    "field_3": "Level",
    "field_4": "Category",
    "field_5": "Location",
    "field_6": "Calendar",
}
IMAGE_FIELD = "IMG"
ACTIVE_FIELD = "Active"
DATA_LIST_FIELDS = [*DATA_FIELDS, IMAGE_FIELD, ACTIVE_FIELD]
LINK_URL_FIELD = "field_1"  # display name "URL"
LINK_LIST_FIELDS = ["Title", LINK_URL_FIELD]


def strip_list(items):
    return [str(item).strip().capitalize() for item in items if str(item).strip()]


def strip_list_title(items):
    return [str(item).strip() for item in items if str(item).strip()]


def to_int_list(items):
    return [int(str(item).strip()) for item in items if str(item).strip().isdigit()]


def _as_list(value):
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def _as_text(value):
    return str(value).strip() if value is not None else ""


def _image_file_name(value):
    """IMG holds JSON pointing to the attachment; Graph returns it as a string."""
    if not value:
        return None
    try:
        image = value if isinstance(value, dict) else json.loads(value)
    except ValueError:
        return None
    return image.get("fileName")


def build_dataframe(items):
    """Returns (dataframe indexed by list item id, sorted categories, {item id: image file name})."""
    rows = {}
    image_files = {}
    for item in items:
        if item.get(ACTIVE_FIELD) is False:
            continue
        workshop = _as_text(item.get("Title"))
        location = _as_text(item.get("field_5"))
        if not workshop or not location:
            continue
        rows[item["id"]] = {
            "Workshop": workshop,
            "Description": _as_text(item.get("field_1")),
            "Days": strip_list(_as_list(item.get("field_2"))),
            "Level": to_int_list(_as_list(item.get("field_3"))),
            "Category": strip_list(_as_list(item.get("field_4"))),
            "Location": location,
            "Calendar": strip_list_title(_as_list(item.get("field_6"))),
        }
        file_name = _image_file_name(item.get(IMAGE_FIELD))
        if file_name:
            image_files[item["id"]] = file_name

    dataframe = pd.DataFrame.from_dict(rows, orient="index", columns=REQUIRED_DATA_COLUMNS)
    dataframe.index.name = "Id"
    categories = sorted({category for values in dataframe["Category"] for category in values})
    return dataframe, pd.Series(categories, dtype=object), image_files


def build_links(items):
    """Returns the links list as a {calendar name: URL} dict."""
    links = {}
    for item in items:
        calendar = _as_text(item.get("Title"))
        url = item.get(LINK_URL_FIELD)
        # A Hyperlink column comes back as {"Url": ..., "Description": ...}.
        if isinstance(url, dict):
            url = url.get("Url")
        if calendar and url:
            links[calendar] = url.strip()
    return links
