"""
Test file with intentional syntax errors
This file will be auto-fixed by the LLM
"""

# Error 1: Missing closing parenthesis
def calculate_total(items
    total = 0
    for item in items:
        total += item.price
    return total

# Error 2: Missing colon
def get_user(user_id)
    user = db.query(user_id)
    return user

# Error 3: Mixing tabs and spaces (indentation error)
def process_order(order):
	total = calculate_total(order.items)
    tax = total * 0.1  # This line uses spaces
	return total + tax

# Error 4: Missing closing bracket
def format_data(data):
    result = {
        "id": data.id,
        "name": data.name
    return result

# Error 5: Invalid syntax in expression
def compute(x, y):
    return x + + y  # Double plus
