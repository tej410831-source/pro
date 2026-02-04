import os

file_path = "scale_test/heavy_processor.py"
content = """import data_provider

class HeavyProcessor:
    def __init__(self, config):
        self.config = config
        self.is_ready = True
        self.usage_count = 0

    def helper_a(self, data):
        return data.upper()

    def helper_b(self, data):
        return data.lower()
"""

# Add many dummy methods to reach >200 lines
for i in range(50):
    content += f"""
    def dummy_method_{i}(self, val):
        \"\"\"Dummy method {i}\"\"\"
        return val * {i}
"""

content += """
    def process_and_verify(self, user_id):
        \"\"\"
        This is the target method for auditing.
        It calls data_provider.fetch_user_data.
        \"\"\"
        if not self.is_ready:
            return None
            
        # Call external function
        user_info = data_provider.fetch_user_data(user_id)
        
        # LOGIC BUG: user_info is a dict, but we treat it as a string
        if user_info == "active":
            self.usage_count += 1
            return "SUCCESS"
        
        return "FAILED"
"""

with open(file_path, "w") as f:
    f.write(content)

print(f"Created {file_path} with {len(content.splitlines())} lines.")
