
from dataclasses import dataclass
from typing import List

# 1. Global Variable (Should trigger global analysis if enabled, but we removed that specific enhancement)
GLOBAL_CONFIG = {"version": "1.0"}

# 2. Method-less Class (Should be analyzed as a whole class)
@dataclass
class Configuration:
    host: str
    port: int
    retries: int = 3
    
    # Intentionally bad validation logic to trigger a bug
    # This is code in the class body but not in a method
    if retries < 0:
        print("Invalid retries")

# 3. Normal Class with Methods (Should analyze methods individually)
class UserManager:
    def __init__(self, db_connection):
        self.db = db_connection
    
    def get_user(self, user_id: int):
        # Buggy code: potential SQL injection or logic error
        query = f"SELECT * FROM users WHERE id = {user_id}"
        return query

def standalone_function(x: int):
    # Buggy code: division by zero risk
    return 10 / x
