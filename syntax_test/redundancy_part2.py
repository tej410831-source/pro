
def compute_field_size(r):
    # This logic is identical to calculate_area_circle but uses different names
    constant_val = 3.14159
    result = constant_val * (r ** 2)
    return result

def get_combinations_count(x):
    # Identical recursive structure to factorial
    if x == 1:
        return 1
    else:
        return x * get_combinations_count(x-1)
