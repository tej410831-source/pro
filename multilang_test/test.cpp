#include <iostream>

class TestClass {
public:
    void sayHello() {
        std::cout << "Hello World" << std::endl; // Added semicolon
    }
};

int main() {
    TestClass t;
    t.sayHello();
    return 0;
}
