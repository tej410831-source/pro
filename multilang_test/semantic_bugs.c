
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define MAX_BUFFER 256
#define MAX_USERS 100

int global_count = 0;


void greet_user(char *name) {
    char buffer[64];
    sprintf(buffer, "Hello, %s! Welcome.", name);  
    printf("%s\n", buffer);
}


int* create_array(int size) {
    int *arr = (int*)malloc(size * sizeof(int));
    if (arr == NULL) {
        return NULL;  
    }
    for (int i = 0; i <= size; i++) {  
        arr[i] = i * 2;
    }
    return arr;  
}


void process_and_free(int *data, int len) {
    free(data);
    
    for (int i = 0; i < len; i++) {
        printf("%d ", data[i]);
    }
    printf("\n");
}


void print_length(const char *str) {
    int len = strlen(str);  
    printf("Length: %d\n", len);
}


int multiply_large(int a, int b) {
    return a * b;  
}
void cleanup(int *ptr) {
    free(ptr);
    free(ptr);  
}

int main() {
    char *long_name = "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA";
    greet_user(long_name);

    int *arr = create_array(10);
    process_and_free(arr, 10);

    print_length(NULL);

    return 0;
}
