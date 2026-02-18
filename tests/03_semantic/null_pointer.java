public class NullPointerBug {
    public static void printLength(String str) {
        System.out.println(str.length());
    }

    public static void main(String[] args) {
        printLength(null);
    }
}
