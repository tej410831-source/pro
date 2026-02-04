import config

def allocate_buffer(size):
    # BUG: Should be >= MIN but uses >. If size is exactly 64, it fails incorrectly.
    if size > config.MIN_BUFFER_SIZE and size < config.MAX_BUFFER_SIZE:
        return f"Allocated {size}"
    return "Error: Invalid size"

def reset_manager():
    # Calling internal state without init
    return clear_cache() # Undefined variable/function in same file
