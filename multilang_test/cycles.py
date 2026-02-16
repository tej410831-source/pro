def a():
    b()
    
def b():
    a()
    
def unused_func():
    pass

def used_func():
    print("used")

def main():
    used_func()
    a() # Start cycle
    
    unused_var = 10
    used_var = 20
    print(used_var)
    
if __name__ == "__main__":
    main()
