"""
Class Bug Test Suite (Advanced)
Syntactically valid Python with class-related bugs for Phase 3 detection.
"""


# BUG 1: Mutable class attribute shared across ALL instances
class StudentRegistry:
    students = []  # BUG: shared across all instances

    def __init__(self, school_name: str):
        self.school_name = school_name

    def add_student(self, name: str):
        self.students.append(name)  # BUG: modifies class-level list, affects other instances

    def get_count(self) -> int:
        return len(self.students)


# BUG 2: Missing attribute initialization + wrong super()
class PaymentProcessor:
    def __init__(self, merchant_id: str):
        self.merchant_id = merchant_id
        # BUG: self.transactions never initialized

    def process_payment(self, amount: float) -> bool:
        if amount <= 0:
            return False
        self.transactions.append(amount)  # BUG: AttributeError
        return True

    def get_total(self) -> float:
        return sum(self.transactions)  # BUG: same error


# BUG 3: Code duplication in methods
class ReportGenerator:
    def __init__(self, data: list):
        self.data = data

    def generate_pdf(self) -> str:
        filtered = [d for d in self.data if d.get("active")]
        return f"PDF with {len(filtered)} records"

    def generate_csv(self) -> str:
        filtered = [d for d in self.data if d.get("active")]  # BUG: exact same filter logic
        return f"CSV with {len(filtered)} records"


# BUG 4: Incorrect super().__init__ call
class Animal:
    def __init__(self, name: str):
        self.name = name
        self.sound = "..."

    def speak(self) -> str:
        return f"{self.name} says {self.sound}"

class Dog(Animal):
    def __init__(self, name: str, breed: str):
        self.breed = breed  # BUG: super().__init__ never called
        self.sound = "Woof"

    def fetch(self, item: str) -> str:
        return f"{self.name} fetches {item}"  # BUG: self.name not set (no super call)

class Cat(Animal):
    def __init__(self, name: str, breed: str):
        super().__init__(name)
        self.breed = breed

    def show_breed(self) -> str:
        return f"{self.name} is a {self.breed}"


# BUG 5: Property without setter causes AttributeError
class Temperature:
    def __init__(self, celsius: float):
        self._celsius = celsius

    @property
    def fahrenheit(self) -> float:
        return self._celsius * 9/5 + 32

    @property
    def kelvin(self) -> float:
        return self._celsius + 273.15  # BUG: should be a method or have setter


# BUG 6: __eq__ without __hash__ makes class unhashable
class Point:
    def __init__(self, x: int, y: int):
        self.x = x
        self.y = y

    def __eq__(self, other) -> bool:
        return self.x == other.x and self.y == other.y
    # BUG: defining __eq__ without __hash__ makes Point unhashable (can't use in sets/dicts)


# BUG 7: Method chaining broken (missing return self)
class QueryBuilder:
    def __init__(self):
        self.query_parts = []

    def select(self, columns: str):
        self.query_parts.append(f"SELECT {columns}")
        # BUG: no return self — chaining like .select("*").where("x=1") fails

    def where(self, condition: str):
        self.query_parts.append(f"WHERE {condition}")
        # BUG: same — no return self

    def build(self) -> str:
        return " ".join(self.query_parts)