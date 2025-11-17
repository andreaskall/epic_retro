"""
Code snippets database for the typing game.
Organized by difficulty with exponentially increasing point values.
Multiple variations per round for replayability.
"""

import random

SNIPPET_VARIATIONS = {
    # Round 1 - Easy C (10 points) - Variable declarations and simple operations
    1: {
        "language": "c",
        "points": 10,
        "variations": [
            """int x = 5;
int y = 10;
int sum = x + y;""",
            """float a = 3.14;
float b = 2.0;
float result = a * b;""",
            """char letter = 'A';
int code = (int)letter;
printf("%c = %d", letter, code);""",
            """int width = 8;
int height = 12;
int area = width * height;""",
            """double pi = 3.14159;
double radius = 5.0;
double circumference = 2 * pi * radius;"""
        ]
    },

    # Round 2 - Easy Python (20 points) - Simple functions and string formatting
    2: {
        "language": "python",
        "points": 20,
        "variations": [
            """def greet(name):
    return f"Hello, {name}!"
print(greet("World"))""",
            """def add(a, b):
    return a + b
result = add(5, 3)""",
            """name = "Alice"
age = 25
message = f"{name} is {age} years old" """,
            """def square(n):
    return n * n
print(square(4))""",
            """temperature = 20
fahrenheit = (temperature * 9/5) + 32
print(f"{temperature}°C = {fahrenheit}°F")"""
        ]
    },

    # Round 3 - Simple loops (40 points)
    3: {
        "language": "c",
        "points": 40,
        "variations": [
            """for (int i = 0; i < 10; i++) {
    printf("%d\\n", i);
}""",
            """int count = 0;
while (count < 5) {
    printf("Count: %d\\n", count);
    count++;
}""",
            """for (int j = 1; j <= 5; j++) {
    printf("Square of %d is %d\\n", j, j*j);
}""",
            """int sum = 0;
for (int k = 1; k <= 10; k++) {
    sum += k;
}""",
            """for (int n = 10; n >= 1; n--) {
    printf("Countdown: %d\\n", n);
}"""
        ]
    },

    # Round 4 - Python collections (80 points)
    4: {
        "language": "python",
        "points": 80,
        "variations": [
            """numbers = [1, 2, 3, 4, 5]
squared = [n**2 for n in numbers]
print(squared)""",
            """fruits = ["apple", "banana", "cherry"]
lengths = [len(fruit) for fruit in fruits]
print(lengths)""",
            """data = {"name": "John", "age": 30}
for key, value in data.items():
    print(f"{key}: {value}")""",
            """temperatures = [20, 25, 18, 22, 19]
average = sum(temperatures) / len(temperatures)
print(f"Average: {average:.1f}°C")""",
            """words = ["hello", "world", "python"]
upper_words = [word.upper() for word in words]
print(" ".join(upper_words))"""
        ]
    },

    # Round 5 - C structures and pointers (150 points)
    5: {
        "language": "c",
        "points": 150,
        "variations": [
            """struct Point {
    int x, y;
};
struct Point p = {10, 20};
printf("Point: (%d, %d)", p.x, p.y);""",
            """typedef struct {
    char name[50];
    int age;
} Person;
Person student = {"Alice", 20};""",
            """int arr[5] = {1, 2, 3, 4, 5};
int *ptr = arr;
for (int i = 0; i < 5; i++) {
    printf("%d ", *(ptr + i));
}""",
            """struct Rectangle {
    float width, height;
} rect = {5.0, 3.0};
float area = rect.width * rect.height;""",
            """int value = 42;
int *pointer = &value;
printf("Value: %d, Address: %p", *pointer, pointer);"""
        ]
    },

    # Round 6 - Python classes (300 points)
    6: {
        "language": "python",
        "points": 300,
        "variations": [
            """class Car:
    def __init__(self, brand, model):
        self.brand = brand
        self.model = model
    
    def start(self):
        return f"{self.brand} {self.model} is starting"
        
car = Car("Toyota", "Camry")""",
            """class Calculator:
    @staticmethod
    def add(a, b):
        return a + b
    
    @staticmethod
    def multiply(a, b):
        return a * b
        
result = Calculator.add(5, 3)""",
            """class Student:
    def __init__(self, name, grades):
        self.name = name
        self.grades = grades
    
    def get_average(self):
        return sum(self.grades) / len(self.grades)
        
student = Student("Bob", [85, 92, 78])""",
            """class Counter:
    def __init__(self):
        self.count = 0
    
    def increment(self):
        self.count += 1
        return self.count
        
counter = Counter()
print(counter.increment())""",
            """class Circle:
    def __init__(self, radius):
        self.radius = radius
    
    @property
    def area(self):
        return 3.14159 * self.radius ** 2
        
circle = Circle(5)"""
        ]
    },

    # Round 7 - C memory management (500 points)
    7: {
        "language": "c",
        "points": 500,
        "variations": [
            """int *ptr = (int*)malloc(5 * sizeof(int));
if (ptr != NULL) {
    for (int i = 0; i < 5; i++) {
        ptr[i] = i * 2;
    }
    free(ptr);
}""",
            """char *str = (char*)calloc(20, sizeof(char));
strcpy(str, "Hello World");
printf("%s", str);
free(str);""",
            """int **matrix = (int**)malloc(3 * sizeof(int*));
for (int i = 0; i < 3; i++) {
    matrix[i] = (int*)malloc(3 * sizeof(int));
}
// Use matrix...
free(matrix);""",
            """void *data = realloc(NULL, 10 * sizeof(double));
double *numbers = (double*)data;
for (int i = 0; i < 10; i++) {
    numbers[i] = i * 1.5;
}""",
            """size_t buffer_size = 256;
char *buffer = (char*)aligned_alloc(16, buffer_size);
memset(buffer, 0, buffer_size);
free(buffer);"""
        ]
    },

    # Round 8 - Python advanced features (750 points)
    8: {
        "language": "python",
        "points": 750,
        "variations": [
            """from functools import reduce
numbers = [1, 2, 3, 4, 5]
product = reduce(lambda x, y: x * y, numbers)
print(f"Product: {product}")""",
            """def fibonacci():
    a, b = 0, 1
    while True:
        yield a
        a, b = b, a + b

fib = fibonacci()
first_10 = [next(fib) for _ in range(10)]""",
            """import itertools
data = [1, 2, 3]
permutations = list(itertools.permutations(data))
combinations = list(itertools.combinations(data, 2))""",
            """class ContextManager:
    def __enter__(self):
        print("Entering context")
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        print("Exiting context")
        
with ContextManager() as cm:
    print("Inside context")""",
            """@property
def temperature(self):
    return self._temp

@temperature.setter  
def temperature(self, value):
    if value < -273.15:
        raise ValueError("Too cold!")
    self._temp = value"""
        ]
    },

    # Round 9 - Embedded C (1000 points)
    9: {
        "language": "c",
        "points": 1000,
        "variations": [
            """#define SET_BIT(reg, bit) ((reg) |= (1 << (bit)))
#define CLR_BIT(reg, bit) ((reg) &= ~(1 << (bit)))
#define TOG_BIT(reg, bit) ((reg) ^= (1 << (bit)))""",
            """volatile uint8_t *GPIO_PORT = (uint8_t*)0x4000F000;
*GPIO_PORT |= (1 << 3);  // Set pin 3 high
*GPIO_PORT &= ~(1 << 2); // Set pin 2 low""",
            """typedef union {
    uint16_t word;
    struct {
        uint8_t low_byte;
        uint8_t high_byte;
    } bytes;
} Register;""",
            """#define TIMER_CTRL_REG  (*((volatile uint32_t*)0x40000000))
#define TIMER_EN_BIT    0
#define TIMER_RST_BIT   1

TIMER_CTRL_REG |= (1 << TIMER_EN_BIT);""",
            """ISR(TIMER0_OVF_vect) {
    static uint8_t counter = 0;
    if (++counter >= 100) {
        PORTB ^= (1 << PB0);
        counter = 0;
    }
}"""
        ]
    },

    # Round 10 - Python metaprogramming (2000 points)
    10: {
        "language": "python",
        "points": 2000,
        "variations": [
            """def timer_decorator(func):
    def wrapper(*args, **kwargs):
        start = time.time()
        result = func(*args, **kwargs)
        print(f"Time: {time.time() - start:.2f}s")
        return result
    return wrapper""",
            """class MetaSingleton(type):
    _instances = {}
    
    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super().__call__(*args, **kwargs)
        return cls._instances[cls]""",
            """def validate_types(**types):
    def decorator(func):
        def wrapper(*args, **kwargs):
            for name, expected_type in types.items():
                if name in kwargs:
                    if not isinstance(kwargs[name], expected_type):
                        raise TypeError(f"{name} must be {expected_type}")
            return func(*args, **kwargs)
        return wrapper
    return decorator""",
            """import inspect
def auto_repr(cls):
    def __repr__(self):
        args = inspect.signature(cls.__init__).parameters
        values = [f"{k}={getattr(self, k)}" for k in args if k != 'self']
        return f"{cls.__name__}({', '.join(values)})"
    cls.__repr__ = __repr__
    return cls""",
            """from functools import wraps
def memoize(func):
    cache = {}
    @wraps(func)
    def wrapper(*args, **kwargs):
        key = str(args) + str(sorted(kwargs.items()))
        if key not in cache:
            cache[key] = func(*args, **kwargs)
        return cache[key]
    return wrapper"""
        ]
    }
}

def get_snippet(round_num):
    """Get a random code snippet variation for a specific round."""
    if round_num not in SNIPPET_VARIATIONS:
        return None
    
    round_data = SNIPPET_VARIATIONS[round_num]
    random_variation = random.choice(round_data["variations"])
    
    return {
        "round": round_num,
        "language": round_data["language"],
        "points": round_data["points"],
        "code": random_variation
    }

def get_total_rounds():
    """Get the total number of rounds."""
    return len(SNIPPET_VARIATIONS)