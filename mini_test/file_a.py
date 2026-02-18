"""File A: has a duplicate of compute_sum and a buggy function."""

def compute_sum(a, b):
    """Adds two numbers."""
    if a < 0 or b < 0:
        return 0
    result = a + b
    return result


def buggy_divide(x, y):
    """Division with a bug: no zero check."""
    return x / y


unused_global = 42
