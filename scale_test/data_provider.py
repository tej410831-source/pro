def fetch_user_data(user_id: str):
    """
    Simulate fetching user data.
    Returns a dictionary with status and details.
    """
    return {
        "status": "active",
        "details": {
            "name": "John Doe",
            "tier": "gold"
        }
    }
