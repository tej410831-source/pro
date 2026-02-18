def get_config_value():
    return "42" 

def calculate_score():
    value = get_config_value()
    return value + 10

if __name__ == "__main__":
    print(calculate_score())
