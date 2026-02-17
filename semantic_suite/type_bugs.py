"""
Type Mismatch Bug Test Suite
Syntactically valid Python with intentional type-related bugs for Phase 3 detection.
"""

from typing import List, Dict, Optional


# BUG 1: Passing string to function expecting int
def add_numbers(a: int, b: int) -> int:
    return a + b

def caller_type_mismatch():
    result = add_numbers("10", "20")  # BUG: string concatenation instead of addition
    print(f"Sum: {result}")  # Prints "1020" not 30


# BUG 2: Return type doesn't match annotation
def get_user_age(user: dict) -> int:
    """Get user's age."""
    return user.get("age", "unknown")  # BUG: returns string "unknown" not int


# BUG 3: Integer division where float expected
def calculate_percentage(part: int, total: int) -> float:
    """Calculate percentage."""
    return part / total * 100  # Works in Python 3, but...

def calculate_ratio(numerator: int, denominator: int) -> float:
    """Calculate ratio as string for display."""
    return str(numerator // denominator)  # BUG: returns str, annotated as float


# BUG 4: Comparing incompatible types
def find_item(items: list, target_id: int) -> dict:
    """Find item by ID."""
    for item in items:
        if item["id"] == str(target_id):  # BUG: comparing int with str, never matches
            return item
    return None  # BUG: returns None but annotation says dict


# BUG 5: Mutable default argument
def add_to_cart(item: str, cart: list = []) -> list:
    """Add item to shopping cart."""
    cart.append(item)  # BUG: shared mutable default across all calls
    return cart


# BUG 6: Wrong format specifier
def format_price(price: float) -> str:
    """Format price for display."""
    return f"${price:d}"  # BUG: :d is for integers, will crash on float


# BUG 7: Implicit None return vs expected type
def find_maximum(numbers: List[int]) -> int:
    """Find the maximum number."""
    if not numbers:
        return  # BUG: returns None implicitly, should return int or raise
    return max(numbers)


# BUG 8: Dict key type mismatch
def merge_configs(default: Dict[str, int], override: Dict[str, int]) -> Dict[str, int]:
    """Merge two config dictionaries."""
    result = default.copy()
    for key, value in override.items():
        result[key] = str(value)  # BUG: converts int to str, violating Dict[str, int]
    return result


# BUG 9: Boolean vs int confusion
def count_active_users(users: List[dict]) -> int:
    """Count active users."""
    count = True  # BUG: initialized as bool instead of int
    for user in users:
        if user.get("active"):
            count += 1  # Works but starts from 1 (True=1), off by one
    return count


# BUG 10: Concatenating None with string
def build_greeting(first_name: Optional[str], last_name: Optional[str]) -> str:
    """Build full greeting message."""
    full_name = first_name + " " + last_name  # BUG: crashes if either is None
    return f"Hello, {full_name}!"
