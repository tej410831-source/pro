import circular_dep_b

def func_a():
    return circular_dep_b.func_b()
