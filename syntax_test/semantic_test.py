def process_items(items):
    # Logic Error: Infinite Loop
    i = 0
    while i < len(items):
        item = items[i]
        if item == "skip":
            continue # Forgot to increment i -> Infinite Loop
        print(item)
        i += 1

def helper_add(a: int, b: int) -> int:
    return a + b

def logic_mismatch():
    # Context Error: Passing string to int function
    # Syntax is valid, but logic is wrong.
    result = helper_add("10", "20") 
    print(f"Result is {result}")

class ResourceHandler:
    def process_file(self, filename):
        # Resource Leak: File opened but not closed
        f = open(filename, 'r')
        data = f.read()
        if "error" in data:
            return False # Returns without closing
        return True
