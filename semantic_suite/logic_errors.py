"""
Logic Error Test Suite
Syntactically valid Python with intentional logic bugs for Phase 3 detection.
"""


# BUG 1: Off-by-one error — skips last element
def find_max(numbers: list) -> int:
    if not numbers:
        return 0
    max_val = numbers[0]
    for i in range(1, len(numbers) - 1):  # BUG: should be len(numbers)
        if numbers[i] > max_val:
            max_val = numbers[i]
    return max_val


# BUG 2: Infinite loop — `continue` without incrementing counter
def process_items(items: list):
    results = []
    i = 0
    while i < len(items):
        if items[i] is None:
            continue  # BUG: i never increments, infinite loop
        results.append(items[i] * 2)
        i += 1
    return results


# BUG 3: Wrong comparison operator — excludes boundary
def is_valid_age(age: int) -> bool:
    """Valid ages are 0 to 150 inclusive."""
    if age > 0 and age < 150:  # BUG: should be >= 0 and <= 150
        return True
    return False


# BUG 4: Accumulator not reset — carries over between calls 
_running_total = []

def calculate_average(values: list) -> float:
    """Calculate average of given values."""
    for v in values:
        _running_total.append(v)  # BUG: appends to module-level list, never cleared
    return sum(_running_total) / len(_running_total)


# BUG 5: Dead code after return
def validate_input(data: dict) -> bool:
    if "name" not in data:
        return False
        print("Name is missing")  # BUG: unreachable code
    if "email" not in data:
        return False
        print("Email is missing")  # BUG: unreachable code
    return True


# BUG 6: Wrong variable in condition (copy-paste error)
def compare_ranges(start1, end1, start2, end2):
    """Check if two ranges overlap."""
    if start1 <= end2 and start2 <= end1:  # Correct overlap check
        overlap_start = max(start1, start2)
        overlap_end = min(end1, end2)
        return overlap_end - overlap_start  # BUG: should be overlap_end - overlap_start + 1 for inclusive
    return 0


# BUG 7: Boolean logic error — always returns True
def has_permission(user_role: str, resource: str) -> bool:
    if user_role == "admin":
        return True
    if user_role == "editor" or resource == "public":
        return True
    if user_role == "viewer":
        return True  # BUG: viewers get access to everything, not just public
    return False


# BUG 8: Loop variable shadowing
def flatten_matrix(matrix: list) -> list:
    result = []
    for row in matrix:
        for row in row:  # BUG: shadows outer 'row' variable
            result.append(row)
    return result


# BUG 9: Wrong order of operations
def apply_discount(price: float, discount_percent: float) -> float:
    """Apply discount and add 10% tax."""
    final = price - price * discount_percent / 100 + 10  # BUG: adds flat 10, not 10% tax
    return final


# BUG 10: Modifying list while iterating
def remove_negatives(numbers: list) -> list:
    for num in numbers:
        if num < 0:
            numbers.remove(num)  # BUG: modifying list during iteration skips elements
    return numbers
