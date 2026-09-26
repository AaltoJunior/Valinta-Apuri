import numpy as np
import pandas as pd


def strip_list(items):
    return [str(item).strip().capitalize() if str(item).strip() else "" for item in items]


def strip_list_title(items):
    return [str(item).strip() if str(item).strip() else "" for item in items]


def to_int_list(items):
    return [int(item.strip()) for item in items if item.strip().isdigit()]


def load_and_process_excel(file_path):
    dataframe = pd.read_excel(file_path, header=0)

    for column in ["Days", "Category"]:
        if column in dataframe.columns:
            dataframe[column] = dataframe[column].astype(str).str.split(",")
            dataframe[column] = dataframe[column].apply(strip_list)

    if "Level" in dataframe.columns:
        dataframe["Level"] = dataframe["Level"].astype(str).str.split(",")
        dataframe["Level"] = dataframe["Level"].apply(to_int_list)

    if "Calendar" in dataframe.columns:
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
    dataframe = pd.read_excel(file_path, header=0)
    if "Calendar" in dataframe.columns:
        dataframe["Calendar"] = dataframe["Calendar"].apply(
            lambda value: value.strip() if isinstance(value, str) else value
        )
    return dataframe
