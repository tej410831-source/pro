int calculate_fact(int number) {
    if (number == 0) {
        return 1;
    }
    return number * calculate_fact(number - 1);
}
