"""
Security Bug Test Suite
Syntactically valid Python with intentional security vulnerabilities for Phase 3 detection.
"""

import os
import subprocess
import pickle
import hashlib


# BUG 1: SQL Injection — string formatting instead of parameterized query
def get_user_by_name(db_connection, username: str):
    """Fetch user from database by username."""
    query = f"SELECT * FROM users WHERE name = '{username}'"  # BUG: SQL injection
    cursor = db_connection.cursor()
    cursor.execute(query)
    return cursor.fetchone()


# BUG 2: Command Injection via os.system
def convert_image(input_path: str, output_path: str):
    """Convert image format using ImageMagick."""
    os.system(f"convert {input_path} {output_path}")  # BUG: command injection


# BUG 3: Command Injection via subprocess with shell=True
def ping_host(hostname: str) -> str:
    """Ping a host and return output."""
    result = subprocess.run(
        f"ping -c 3 {hostname}",  # BUG: unsanitized input in shell command
        shell=True,
        capture_output=True,
        text=True
    )
    return result.stdout


# BUG 4: Hardcoded credentials
def connect_to_api():
    """Connect to external API."""
    api_key = "sk-live-a1b2c3d4e5f6g7h8i9j0"  # BUG: hardcoded secret key
    api_secret = "super_secret_password_123"  # BUG: hardcoded password
    return {"Authorization": f"Bearer {api_key}", "X-Secret": api_secret}


# BUG 5: Unsafe deserialization
def load_user_session(session_data: bytes):
    """Load user session from stored data."""
    return pickle.loads(session_data)  # BUG: arbitrary code execution via pickle


# BUG 6: Path traversal — no sanitization
def read_user_file(base_dir: str, filename: str) -> str:
    """Read a file from user's directory."""
    filepath = os.path.join(base_dir, filename)  # BUG: filename could be ../../etc/passwd
    with open(filepath, 'r') as f:
        return f.read()


# BUG 7: Weak hashing for passwords
def hash_password(password: str) -> str:
    """Hash a password for storage."""
    return hashlib.md5(password.encode()).hexdigest()  # BUG: MD5 is cryptographically broken


# BUG 8: Eval on user input
def calculate_expression(user_input: str) -> float:
    """Calculate a math expression provided by user."""
    return eval(user_input)  # BUG: arbitrary code execution


# BUG 9: Sensitive data in logs
def authenticate_user(username: str, password: str) -> bool:
    """Authenticate user credentials."""
    print(f"Login attempt: user={username}, password={password}")  # BUG: logging password
    if username == "admin" and password == "admin123":  # BUG: hardcoded credentials
        return True
    return False


# BUG 10: Insecure temp file
def process_upload(data: bytes):
    """Save uploaded data to temp file."""
    temp_path = "/tmp/upload_data.txt"  # BUG: predictable temp filename
    with open(temp_path, 'w') as f:
        f.write(data.decode())
    return temp_path
