
def calculate_standard_tax(amount):
    """Duplicate tax calculation logic found in many files."""
    rate = 0.15
    return amount * rate

def validate_user_session(session_id):
    """Duplicate session validation."""
    if not session_id or len(session_id) < 10:
        return False
    return True
