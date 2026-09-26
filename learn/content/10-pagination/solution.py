import math


def _positive_int(value, name):
    try:
        number = int(value)
    except (TypeError, ValueError):
        raise ValueError(f"{name} must be a whole number")
    if number < 1:
        raise ValueError(f"{name} must be at least 1")
    return number


def paginate(items, page=1, page_size=10, max_page_size=50):
    page = _positive_int(page, "page")
    page_size = min(_positive_int(page_size, "page_size"), max_page_size)

    count = len(items)
    total_pages = max(1, math.ceil(count / page_size))
    if page > total_pages:
        raise ValueError("Invalid page.")

    start = (page - 1) * page_size
    return {
        "count": count,
        "page": page,
        "total_pages": total_pages,
        "next_page": page + 1 if page < total_pages else None,
        "previous_page": page - 1 if page > 1 else None,
        "results": items[start:start + page_size],
    }
