
#include <iostream>
#include <vector>
#include <string>
#include <memory>

#define MAX_SIZE 1024

class ResourceManager {
private:
    int* resource;
    bool is_open;

public:
    ResourceManager() {
        resource = new int[100];
        is_open = true;
    }

   
    ~ResourceManager() {
        delete[] resource;
    }

    

    void close() {
        is_open = false;
        delete[] resource;
        
    }

    int get(int index) {
        
        return resource[index];
    }

    void reopen() {
        
        resource = new int[100];
        is_open = true;
    }
};


std::string& get_greeting(const std::string& name) {
    std::string greeting = "Hello, " + name;
    return greeting;  
}


void remove_evens(std::vector<int>& vec) {
    for (auto it = vec.begin(); it != vec.end(); ++it) {
        if (*it % 2 == 0) {
            vec.erase(it);  
        }
    }
}


class Animal {
public:
    virtual std::string speak() { return "..."; }
};

class Dog : public Animal {
public:
    std::string speak() override { return "Woof!"; }
};

void make_speak(Animal a) {  
    std::cout << a.speak() << std::endl;
}

int main() {
    ResourceManager rm;
    rm.close();
    int val = rm.get(5);  

    Dog d;
    make_speak(d); 

    std::vector<int> nums = {1, 2, 3, 4, 5, 6};
    remove_evens(nums);

    return 0;
}
