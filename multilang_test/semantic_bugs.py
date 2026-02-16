
import os

MAX_RETRIES = 5
DEFAULT_TIMEOUT = 30

class UserManager:
    active_users = []  
    def __init__(self, db_path):
        self.db_path = db_path
        self.connected = False

    def connect(self):
        self.connected = True
        return self

    def get_user(self, user_id):
        
        query = f"SELECT * FROM users WHERE id = {user_id}"
        return query

    def delete_user(self, user_id):
        if user_id is None:
            return True  
        self.active_users.remove(user_id) 
        return True

    def add_users_batch(self, user_list):
        results = []
        for user in user_list:
            results.append(self.get_user(user))
        return results


def divide_values(a, b):
    
    return a / b


def find_max(numbers):
    
    max_val = numbers[0]
    for n in numbers:
        if n > max_val:
            max_val = n
    return max_val


def read_config(filepath):
    
    f = open(filepath, 'r')
    data = f.read()
    return data


def process_data(items):
    
    processed = []
    for i in range(len(items)):
        
        pair = (items[i], items[i + 1])
        processed.append(pair)
    return processed
