def calculate_mortgage_payment(principal, rate, years):
    """Calculate monthly mortgage payment."""
    monthly_rate = rate / 100 / 12
    num_payments = years * 12
    payment = (principal * monthly_rate) / (1 - (1 + monthly_rate)**-num_payments)
    return round(payment, 2)

def calculate_sales_tax(total):
    return total * TAX_RATE

# Shared constants
TAX_RATE = 0.12

def validate_and_calculate_payment(principal, rate, years):
    """Validate and calculate monthly mortgage payment."""
    if principal < 0:
        raise ValueError("Principal cannot be negative.")
    return calculate_mortgage_payment(principal, rate, years)

# Example usage
try:
    total_sales = calculate_sales_tax(10000)
    print(f"Total Sales Tax: ${total_sales:.2f}")
except ValueError as e:
    print(e)