
def calculate_area_circle(radius):
    pi = 3.14159
    area = pi * (radius ** 2)
    return area

def factorial_recursive(n):
    if n == 1:
        return 1
    else:
        return n * factorial_recursive(n-1)
