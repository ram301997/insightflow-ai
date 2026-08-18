REPORT_PAGES = {
    "overview": "Sales Overview",
    "product": "Product Analysis",
    "regional": "Regional Performance",
    "customer": "Customer Analysis",
}


def get_dashboard_metadata():
    return {
        "pages": REPORT_PAGES,
        "supportedFilters": ["State", "Category", "Segment", "Date"],
        "defaultPage": REPORT_PAGES["overview"],
    }


def build_dashboard_action(
    page: str = "overview",
    state: str | None = None,
    days: int | None = None,
    category: str | None = None,
    segment: str | None = None,
):
    filters = []
    if state:
        filters.append({"table": "DimStore", "column": "State", "operator": "In", "values": [state]})
    if category:
        filters.append({"table": "DimProduct", "column": "Category", "operator": "In", "values": [category]})
    if segment:
        filters.append({"table": "DimCustomer", "column": "Segment", "operator": "In", "values": [segment]})

    return {
        "page": REPORT_PAGES.get(page, REPORT_PAGES["overview"]),
        "filters": filters,
        "relativeDate": {"days": int(days)} if days else None,
    }
