from dataclasses import dataclass


DAYS = ["Ma", "Ti", "Ke", "To", "Pe"]


@dataclass
class FilterSelection:
    days: list[str]
    levels: list[int]
    locations: list
    categories: list[str]


def parse_filters(form, dataframe, categories):
    selected_days = [day for day in DAYS if form.get(day) == "True"]
    selected_levels = {
        int(key.removeprefix("lvl"))
        for key in form
        if key.startswith("lvl") and form.get(key) == "True"
    }

    for group_value in form.getlist("lvl_group"):
        selected_levels.update(
            int(value.strip())
            for value in group_value.split(",")
            if value.strip().isdigit()
        )

    return FilterSelection(
        days=selected_days,
        levels=sorted(selected_levels),
        locations=[
            location
            for location in dataframe["Location"].unique()
            if form.get(location) == "True"
        ],
        categories=[category for category in categories if form.get(category) == "True"],
    )


def filter_workshops(dataframe, selection):
    if not (selection.levels or selection.days or selection.categories):
        return dataframe.copy()

    filtered = dataframe.copy()
    if selection.categories and not filtered.empty:
        filtered = filtered[
            filtered["Category"].apply(
                lambda values: any(category in values for category in selection.categories)
            )
        ]
    if selection.levels and not filtered.empty:
        filtered = filtered[
            filtered["Level"].apply(
                lambda values: any(level in values for level in selection.levels)
            )
        ]
    if selection.days and not filtered.empty:
        filtered = filtered[
            filtered["Days"].apply(
                lambda values: any(day in values for day in selection.days)
            )
        ]
    if selection.locations and not filtered.empty:
        filtered = filtered[
            filtered["Location"].apply(
                lambda values: any(location in str(values) for location in selection.locations)
            )
        ]
    return filtered
