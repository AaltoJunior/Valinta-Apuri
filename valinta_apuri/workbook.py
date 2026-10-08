import numpy as np
import pandas as pd


# The card templates index rows by position, so these must also stay in this
# order as the first columns of the workbook.
REQUIRED_DATA_COLUMNS = ["Workshop", "Description", "Days", "Level", "Category", "Location", "Calendar"]
REQUIRED_LINK_COLUMNS = ["Calendar", "URL"]


def strip_list(items):
    return [str(item).strip().capitalize() if str(item).strip() else "" for item in items]


def strip_list_title(items):
    return [str(item).strip() if str(item).strip() else "" for item in items]


def to_int_list(items):
    return [int(item.strip()) for item in items if item.strip().isdigit()]


def _require_columns(dataframe, required, file_path):
    missing = [column for column in required if column not in dataframe.columns]
    if missing:
        raise ValueError(
            f"'{file_path}' is missing columns: {', '.join(missing)} "
            f"(expected {', '.join(required)})"
        )


def load_and_process_excel(file_path):
    dataframe = pd.read_excel(file_path, header=0)
    _require_columns(dataframe, REQUIRED_DATA_COLUMNS, file_path)

    for column in ["Days", "Category"]:
        dataframe[column] = dataframe[column].astype(str).str.split(",")
        dataframe[column] = dataframe[column].apply(strip_list)

    dataframe["Level"] = dataframe["Level"].astype(str).str.split(",")
    dataframe["Level"] = dataframe["Level"].apply(to_int_list)

    dataframe["Calendar"] = dataframe["Calendar"].astype(str).str.split(",")
    dataframe["Calendar"] = dataframe["Calendar"].apply(strip_list_title)

    dataframe["Category"] = dataframe["Category"].replace("", np.nan)
    dataframe["Location"] = dataframe["Location"].replace("", np.nan)
    dataframe = dataframe.dropna(subset=["Workshop", "Location"])
    category_dataframe = dataframe.dropna(subset=["Category"])
    categories = (
        category_dataframe["Category"]
        .explode()
        .map(lambda value: value.strip())
        .dropna()
        .loc[lambda series: (series != "") & (series.str.lower() != "nan")]
        .unique()
        .tolist()
    )
    return dataframe, pd.Series(sorted(categories))


def load_and_process_links(file_path):
    """Returns the links workbook as a {calendar name: URL} dict."""
    dataframe = pd.read_excel(file_path, header=0)
    _require_columns(dataframe, REQUIRED_LINK_COLUMNS, file_path)
    dataframe["Calendar"] = dataframe["Calendar"].apply(
        lambda value: value.strip() if isinstance(value, str) else value
    )
    dataframe = dataframe.dropna(subset=["Calendar"])
    return dataframe.set_index("Calendar")["URL"].to_dict()
