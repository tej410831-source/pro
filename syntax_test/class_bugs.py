class Config:
    # Bug 1: Type error - should be int
    MAX_CONNECTIONS = "100"
    
    # Bug 2: Mutable default - dangerous!
    DEFAULT_SETTINGS = {}
    ALLOWED_USERS = []
    
    # Bug 3: Incorrect constant naming
    timeout = 30  # Should be UPPERCASE

class User:
    # Bug 4: Mutable class attribute shared across instances
    permissions = []
    
    def __init__(self, name):
        self.name = name
        # Bug 5: This modifies the class attribute!
        self.permissions.append("read")

class Database:
    # Bug 6: Missing type hint where needed
    connection_pool = None
    
    def __init__(self):
        # Bug 7: Accessing undefined class variable
        self.timeout = self.DEFAULT_TIMEOUT  # Not defined!
