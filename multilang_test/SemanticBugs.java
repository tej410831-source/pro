
import java.util.ArrayList;
import java.util.List;
import java.util.HashMap;

public class SemanticBugs {

    private static List<String> sharedList = new ArrayList<>();

   
    public static boolean checkRole(String role) {
        if (role.equals("admin")) {  
            return true;
        }
        return false;
    }


    public static int getLength(String input) {
        return input.length(); 
    }

    
    public static void printNumbers(int n) {
        int i = 0;
        while (i < n){
            System.out.println(i);
            
        }
    }

    
    public static void removeItems(List<String> items) {
        for (String item : items) {
            if (item.startsWith("temp")) {
                items.remove(item);  
            }
        }
    }

    
    public static String readFile(String path) throws Exception {
        java.io.FileInputStream fis = new java.io.FileInputStream(path);
        byte[] data = new byte[1024];
        int bytesRead = fis.read(data);
        
        return new String(data, 0, bytesRead);
    }

    
    public static void cacheResults() {
        HashMap<ArrayList<Integer>, String> cache = new HashMap<>();
        ArrayList<Integer> key = new ArrayList<>();
        key.add(1);
        cache.put(key, "result1");
        key.add(2);  
        String result = cache.get(key);  
        System.out.println(result);
    }

    
    public static int[] createLargeArray(int rows, int cols) {
        int size = rows * cols;  
        return new int[size];
    }

    public static void main(String[] args) throws Exception {
        checkRole("admin");
        getLength(null);
        removeItems(new ArrayList<>(List.of("temp1", "keep", "temp2")));
        cacheResults();
    }
}
