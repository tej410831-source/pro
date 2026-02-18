"""
Test cases for redundancy detection.

Expected results:
  ✅ calculate_area ↔ get_rect_size → DUPLICATE (same math, different vars)
  ❌ distinct_function              → NOT matched (different logic: addition vs multiplication)
  ❌ fetch_user_query               → NOT matched (SQL string, not math)
"""


def calculate_area(width, height):
    """Calculate the area of a rectangle."""
    if width < 0 or height < 0:
        return 0
    area = width * height
    return area


def get_rect_size(w, h):
    """Same logic as calculate_area but with different variable names
    and slightly different guard structure."""
    if w < 0:
        return 0
    if h < 0:
        return 0
    result = w * h
    return result


def distinct_function(a, b):
    """Completely different — addition, not multiplication."""
    if a < 0 or b < 0:
        return 0
    return a + b


def fetch_user_query(user_id):
    """SQL query builder — unrelated to math functions."""
    if user_id < 0:
        return ""
    query = f"SELECT * FROM users WHERE id = {user_id}"
    return query
