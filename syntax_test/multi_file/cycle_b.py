import cycle_a

def func_b():
    print("In B")
    cycle_a.func_a()

def main():
    func_b()

if __name__ == "__main__":
    main()
