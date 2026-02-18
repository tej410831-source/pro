def iterative_sum_squares(n):
    """Computes the sum of squares from 1 to n iteratively."""
    total = 0
    for i in range(1, n + 1):
        total += i * i
    return total

def recursive_sum_squares(n):
    """Computes the sum of squares from 1 to n recursively."""
    if n <= 0:
        return 0
    return (n * n) + recursive_sum_squares(n - 1)
