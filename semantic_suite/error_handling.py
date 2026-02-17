"""
Error Handling Bug Test Suite
Syntactically valid Python with intentional error handling anti-patterns for Phase 3 detection.
"""

import json


# BUG 1: Bare except swallows all errors silently
def parse_config(filepath: str) -> dict:
    """Load and parse a JSON config file."""
    try:
        with open(filepath) as f:
            return json.load(f)
    except:  # BUG: catches everything including KeyboardInterrupt, SystemExit
        pass
    return {}


# BUG 2: Exception caught but wrong variable used
def divide_safely(a: float, b: float) -> float:
    try:
        return a / b
    except ZeroDivisionError as e:
        print(f"Division error: {err}")  # BUG: 'err' is not defined, should be 'e'
        return 0.0


# BUG 3: Resource leak — file not closed on exception
def count_lines(filepath: str) -> int:
    """Count lines in a file."""
    f = open(filepath, 'r')  # BUG: no context manager
    count = 0
    for line in f:
        if not line.strip():
            raise ValueError("Empty line found")  # BUG: file 'f' never closed
        count += 1
    f.close()
    return count


# BUG 4: Catching too broad, hiding real bugs
def fetch_data(url: str) -> dict:
    """Fetch data from API endpoint."""
    try:
        import urllib.request
        response = urllib.request.urlopen(url)
        data = json.loads(response.read())
        result = data["results"][0]["value"]  # Could KeyError, IndexError
        return {"status": "ok", "value": result}
    except Exception:  # BUG: hides TypeError, KeyError, IndexError — all silenced
        return {"status": "error", "value": None}


# BUG 5: Exception raised inside finally block masks original error
def process_file(filepath: str) -> str:
    data = None
    try:
        with open(filepath) as f:
            data = f.read()
        return data.upper()
    finally:
        if data is None:
            raise RuntimeError("No data loaded")  # BUG: masks the original FileNotFoundError


# BUG 6: Null check missing — attribute access on None
def get_user_email(users: dict, user_id: int) -> str:
    """Get email for a user."""
    user = users.get(user_id)  # Returns None if not found
    return user["email"]  # BUG: TypeError if user is None


# BUG 7: Re-raising loses original traceback
def validate_data(data: dict):
    try:
        assert "name" in data, "Missing name"
        assert "age" in data, "Missing age"
        assert data["age"] > 0, "Invalid age"
    except AssertionError as e:
        raise ValueError(f"Validation failed: {e}")  # BUG: loses original stack trace
        # Should be: raise ValueError(...) from e


# BUG 8: Return in except hides the error
def safe_divide(x, y):
    """Divide x by y, return None on error."""
    try:
        result = x / y
    except ZeroDivisionError:
        result = x  # BUG: silently returns x instead of None/error — misleading
    return result


# BUG 9: Exception handler does cleanup but forgets to re-raise
def update_database(db, record: dict):
    """Update record in database with rollback on failure."""
    db.begin_transaction()
    try:
        db.update(record)
        db.commit()
    except Exception as e:
        db.rollback()
        print(f"Update failed: {e}")
        # BUG: doesn't re-raise — caller thinks update succeeded


# BUG 10: Using mutable default + no error handling
def append_log(message: str, log_entries: list = []):
    """Append a log message."""
    log_entries.append(message)  # BUG: mutable default argument shared across calls
    return log_entries
