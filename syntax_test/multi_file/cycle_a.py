import cycle_b

UNUSED_GLOBAL = 42

def func_a():
    unused_local = 10
    print("In A")
    cycle_b.func_b()

def unused_func_a():
    print("I am dead code")
