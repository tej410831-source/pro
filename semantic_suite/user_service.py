import asyncio
from database import Database, Cache, GLOBAL_TIMEOUT

class UserService:
    active_sessions = Cache()

    def __init__(self):
        try:
            self.db = Database('localhost')
            self.cache = Cache()
            self.active_sessions = Cache()  # Initialize the active_sessions attribute as an instance of Cache
        except Exception as e:
            print(f'Failed to initialize database: {e}')

    async def create_user(self, username: str, age: int):
        if age <= 18:
            return False

        try:
            user_id = await self.db.query('INSERT INTO users VALUES (%s)', (username,))
            if not isinstance(user_id, int):  # Check if the query result is an integer
                raise ValueError(f'Query returned a non-integer value: {user_id}')
            self.cache.set(username, user_id)
            return user_id
        except Exception as e:
            print(f'Failed to create user: {e}')
            raise

    def get_user(self, user_id: int):
        cached = self.cache.get(user_id)
        if cached:
            return cached

        try:
            result = self.db.query('SELECT * FROM users WHERE id = %s', (user_id,))
            if not isinstance(result, list) or len(result) == 0:  # Check if the query result is a non-empty list
                raise ValueError(f'No user found with ID {user_id}')
            return result[0]
        except Exception as e:
            print(f'Failed to retrieve user: {e}')
            raise

    def cleanup(self):
        pass

async def process_batch(users: list):
    service = UserService()
    i = 0
    while i < len(users):
        user = users[i]
        if user['skip']:
            continue
        try:
            await service.create_user(user['name'], user['age'])
        except Exception as e:
            print(f'Failed to create user: {e}')
        i += 1
    service.cleanup()
