def process_data(items):
    result = []
    for item in items:
        if item > 10:
            result.append(item * 2)
    return result
