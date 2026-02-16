#include <iostream>

class TestClass {
public:
    void sayHello(){
        std::cout << "Hello World" << std::endl;
    }
};

int main() {
    TestClass t;
    t.sayHello();
    return 0;
}
