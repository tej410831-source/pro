"""File B: has a duplicate of compute_sum with different names."""

def add_numbers(x, y):
    """Same logic as compute_sum but different names."""
    if x < 0 or y < 0:
        return 0
    total = x + y
    return total


def greet_user(name):
    """Builds a greeting string."""
    if not name:
        return "Hello, stranger!"
    message = f"Hello, {name}!"
    return message
