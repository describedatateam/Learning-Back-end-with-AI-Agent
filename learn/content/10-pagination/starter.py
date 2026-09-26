import math


def paginate(items, page=1, page_size=10, max_page_size=50):
    # `items`, `page` and `page_size` are passed in by the tests when they call
    # your function. `page` and `page_size` may be strings like "2".
    # TODO 1: turn page into an int; raise ValueError if that fails or it's below 1
    # TODO 2: do the same for page_size
    # TODO 3: clamp page_size so it's never above max_page_size
    # TODO 4: work out count and total_pages (at least 1)
    # TODO 5: raise ValueError("Invalid page.") if page is past total_pages
    # TODO 6: slice out this page's items
    # TODO 7: work out next_page and previous_page (None at the ends)
    # TODO 8: return the dict below, filled in with your values
    return {
        "count": len(items),
        "page": page,
        "total_pages": 1,
        "next_page": None,
        "previous_page": None,
        "results": items,
    }
