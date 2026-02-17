def organize_array(data):
    # Same logic, different names, using tuple swap to match structural fingerprint
    size = len(data)
    for step in range(size):
        for idx in range(0, size-step-1):
            if data[idx] > data[idx+1]:
                # Swap (tuple unpacking)
                data[idx], data[idx+1] = data[idx+1], data[idx]
    return data
