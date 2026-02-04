public class Greeter {
    public void sayHello(String name) {
        System.out.println("Hello, " + name);
    }

    public static void main(String[] args) {
        Greeter g = new Greeter();
        g.sayHello("User");
    }
}
