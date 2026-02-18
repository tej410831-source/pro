import circular_dep_a

def func_b():
    return circular_dep_a.func_a()
