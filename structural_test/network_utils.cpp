#include <iostream>
#include <string>

void log_message(std::string msg) {
    std::cout << "[LOG] " << msg << std::endl;

int calculate_latency(int start, int end) {
    return end - start;
}

bool check_connection(std::string host) {
    log_message("Checking connection to " + host);
    return true;
}

void initialize_network() {
    log_message("Initializing...");
}

void shutdown_network() {
    log_message("Shutting down...");
}
