"""
Edge Cases Test Suite
Syntactically valid Python with edge-case bugs for Phase 3 detection.
"""


def calculate_average_score(scores):
    if not scores:
        raise ValueError("The list is empty")

    total = sum(scores)
    count = len(scores)
    average = total / count

    return average

# Example usage:
try:
    print(calculate_average_score([10, 20, 30]))  # Output: 20.0
    print(calculate_average_score([]))            # Raises ValueError
    print(calculate_average_score([5, 5, 5]))     # Output: 5.0
    print(calculate_average_score([10, 20, 30, 40]))  # Output: 25.0
except ValueError as e:
    print(e)
