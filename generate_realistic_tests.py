"""
Real-World Syntax Test Generator
Creates large, realistic files with intentional syntax errors across Python, C++, and Java.
"""

import os
from pathlib import Path

def create_test_directory():
    """Create the realistic_test directory."""
    test_dir = Path("./realistic_test")
    test_dir.mkdir(exist_ok=True)
    return test_dir

def generate_python_webservice():
    """Generate a large Python web service class with intentional errors."""
    code = '''"""
E-commerce Order Management Service
A realistic Flask-style web service with intentional syntax errors for testing.
"""

from flask import Flask, request, jsonify
from datetime import datetime
from typing import List, Dict, Optional
import logging
import json

app = Flask(__name__)
logger = logging.getLogger(__name__)

# ERROR 1: Missing closing quote (line 17)
DATABASE_URL = "postgresql://localhost:5432/orders

class OrderStatus:
    """Enum for order statuses."""
    PENDING = "pending"
    PROCESSING = "processing"
    SHIPPED = "shipped"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"

class Product:
    """Product model with validation."""
    
    def __init__(self, product_id: str, name: str, price: float, stock: int):
        self.product_id = product_id
        self.name = name
        self.price = price
        self.stock = stock
        self.created_at = datetime.now()
    
    def to_dict(self) -> Dict:
        return {
            "product_id": self.product_id,
            "name": self.name,
            "price": self.price,
            "stock": self.stock,
            "created_at": self.created_at.isoformat()
        }
    
    # ERROR 2: Incorrect indentation (line 51)
def validate_stock(self, quantity: int) -> bool:
        """Check if sufficient stock is available."""
        if quantity <= 0:
            raise ValueError("Quantity must be positive")
        return self.stock >= quantity
    
    def reduce_stock(self, quantity: int):
        """Reduce stock after purchase."""
        if not self.validate_stock(quantity):
            raise ValueError(f"Insufficient stock. Available: {self.stock}")
        self.stock -= quantity
        logger.info(f"Stock reduced for {self.name}: {quantity} units")

class Order:
    """Order management with business logic."""
    
    def __init__(self, order_id: str, customer_id: str):
        self.order_id = order_id
        self.customer_id = customer_id
        self.items: List[Dict] = []
        self.status = OrderStatus.PENDING
        self.total_amount = 0.0
        self.created_at = datetime.now()
        self.updated_at = datetime.now()
    
    def add_item(self, product: Product, quantity: int):
        """Add item to order with validation."""
        if not product.validate_stock(quantity):
            raise ValueError(f"Cannot add {product.name}: insufficient stock")
        
        item = {
            "product_id": product.product_id,
            "name": product.name,
            "quantity": quantity,
            "unit_price": product.price,
            "subtotal": product.price * quantity
        }
        
        self.items.append(item)
        self.total_amount += item["subtotal"]
        self.updated_at = datetime.now()
        
        logger.info(f"Item added to order {self.order_id}: {product.name} x{quantity}")
    
    def remove_item(self, product_id: str) -> bool:
        """Remove item from order."""
        for i, item in enumerate(self.items):
            if item["product_id"] == product_id:
                self.total_amount -= item["subtotal"]
                del self.items[i]
                self.updated_at = datetime.now()
                return True
        return False
    
    def calculate_shipping(self) -> float:
        """Calculate shipping cost based on total."""
        if self.total_amount >= 100.0:
            return 0.0  # Free shipping
        elif self.total_amount >= 50.0:
            return 5.0
        else:
            return 10.0
    
    # ERROR 3: Missing colon after function definition (line 126)
    def finalize_order(self) -> Dict
        """Finalize the order and return summary."""
        shipping_cost = self.calculate_shipping()
        final_total = self.total_amount + shipping_cost
        
        summary = {
            "order_id": self.order_id,
            "customer_id": self.customer_id,
            "items_count": len(self.items),
            "subtotal": self.total_amount,
            "shipping": shipping_cost,
            "total": final_total,
            "status": self.status,
            "created_at": self.created_at.isoformat()
        }
        
        self.status = OrderStatus.PROCESSING
        self.updated_at = datetime.now()
        
        return summary
    
    def cancel_order(self) -> bool:
        """Cancel the order if allowed."""
        if self.status in [OrderStatus.SHIPPED, OrderStatus.DELIVERED]:
            logger.warning(f"Cannot cancel order {self.order_id}: already {self.status}")
            return False
        
        self.status = OrderStatus.CANCELLED
        self.updated_at = datetime.now()
        logger.info(f"Order {self.order_id} cancelled")
        return True

class OrderService:
    """Service layer for order management."""
    
    def __init__(self):
        self.orders: Dict[str, Order] = {}
        self.products: Dict[str, Product] = {}
        self._initialize_sample_products()
    
    def _initialize_sample_products(self):
        """Initialize some sample products."""
        sample_products = [
            Product("P001", "Laptop", 999.99, 50),
            Product("P002", "Mouse", 29.99, 200),
            Product("P003", "Keyboard", 79.99, 150),
            Product("P004", "Monitor", 299.99, 75),
            Product("P005", "Headphones", 149.99, 100)
        ]
        
        for product in sample_products:
            self.products[product.product_id] = product
    
    def create_order(self, customer_id: str) -> str:
        """Create a new order."""
        order_id = f"ORD-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        order = Order(order_id, customer_id)
        self.orders[order_id] = order
        
        logger.info(f"Order created: {order_id} for customer {customer_id}")
        return order_id
    
    def add_product_to_order(self, order_id: str, product_id: str, quantity: int) -> bool:
        """Add product to existing order."""
        if order_id not in self.orders:
            raise ValueError(f"Order not found: {order_id}")
        
        if product_id not in self.products:
            raise ValueError(f"Product not found: {product_id}")
        
        order = self.orders[order_id]
        product = self.products[product_id]
        
        order.add_item(product, quantity)
        product.reduce_stock(quantity)
        
        return True
    
    def get_order_summary(self, order_id: str) -> Optional[Dict]:
        """Get order summary."""
        if order_id not in self.orders:
            return None
        
        return self.orders[order_id].finalize_order()
    
    def get_all_orders(self, customer_id: Optional[str] = None) -> List[Dict]:
        """Get all orders, optionally filtered by customer."""
        orders = []
        
        for order in self.orders.values():
            if customer_id is None or order.customer_id == customer_id:
                orders.append({
                    "order_id": order.order_id,
                    "customer_id": order.customer_id,
                    "status": order.status,
                    "total": order.total_amount,
                    "items_count": len(order.items),
                    "created_at": order.created_at.isoformat()
                })
        
        return orders

# Flask Routes
service = OrderService()

@app.route('/api/orders', methods=['POST'])
def create_order():
    """Create new order endpoint."""
    data = request.get_json()
    customer_id = data.get('customer_id')
    
    if not customer_id:
        return jsonify({"error": "customer_id required"}), 400
    
    order_id = service.create_order(customer_id)
    return jsonify({"order_id": order_id, "status": "created"}), 201

@app.route('/api/orders/<order_id>/items', methods=['POST'])
def add_order_item(order_id):
    """Add item to order endpoint."""
    data = request.get_json()
    product_id = data.get('product_id')
    quantity = data.get('quantity', 1)
    
    try:
        service.add_product_to_order(order_id, product_id, quantity)
        return jsonify({"status": "item_added"}), 200
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

@app.route('/api/orders/<order_id>', methods=['GET'])
def get_order(order_id):
    """Get order summary endpoint."""
    summary = service.get_order_summary(order_id)
    
    if summary is None:
        return jsonify({"error": "Order not found"}), 404
    
    return jsonify(summary), 200

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
'''
    return code

def generate_cpp_data_structure():
    """Generate a large C++ template class with errors."""
    code = '''/**
 * Advanced Binary Search Tree Template
 * A production-grade BST implementation with intentional syntax errors for testing.
 */

#include <iostream>
#include <memory>
#include <vector>
#include <algorithm>
#include <stdexcept>
#include <queue>
#include <functional>

namespace DataStructures {

// ERROR 1: Missing semicolon after template declaration (line 18)
template<typename T>
struct TreeNode {
    T data;
    std::shared_ptr<TreeNode<T>> left;
    std::shared_ptr<TreeNode<T>> right;
    int height;
    
    TreeNode(const T& value) 
        : data(value), left(nullptr), right(nullptr), height(1) {}
    
    TreeNode(T&& value)
        : data(std::move(value)), left(nullptr), right(nullptr), height(1) {}
}

template<typename T, typename Compare = std::less<T>>
class BinarySearchTree {
private:
    std::shared_ptr<TreeNode<T>> root;
    size_t tree_size;
    Compare comparator;
    
    // Helper function to get node height
    int getHeight(const std::shared_ptr<TreeNode<T>>& node) const {
        return node ? node->height : 0;
    }
    
    // Update height after insertion/deletion
    void updateHeight(std::shared_ptr<TreeNode<T>>& node) {
        if (node) {
            node->height = 1 + std::max(getHeight(node->left), getHeight(node->right));
        }
    }
    
    // Calculate balance factor
    int getBalance(const std::shared_ptr<TreeNode<T>>& node) const {
        return node ? getHeight(node->left) - getHeight(node->right) : 0;
    }
    
    // Right rotation for balancing
    std::shared_ptr<TreeNode<T>> rotateRight(std::shared_ptr<TreeNode<T>>& y) {
        auto x = y->left;
        auto T2 = x->right;
        
        x->right = y;
        y->left = T2;
        
        updateHeight(y);
        updateHeight(x);
        
        return x;
    }
    
    // Left rotation for balancing
    std::shared_ptr<TreeNode<T>> rotateLeft(std::shared_ptr<TreeNode<T>>& x) {
        auto y = x->right;
        auto T2 = y->left;
        
        y->left = x;
        x->right = T2;
        
        updateHeight(x);
        updateHeight(y);
        
        return y;
    }
    
    // ERROR 2: Missing << operator (line 86)
    std::shared_ptr<TreeNode<T>> insertHelper(std::shared_ptr<TreeNode<T>>& node, 
                                                const T& value) {
        if (!node) {
            tree_size++;
            return std::make_shared<TreeNode<T>>(value);
        }
        
        if (comparator(value, node->data)) {
            node->left = insertHelper(node->left, value);
        } else if (comparator(node->data, value)) {
            node->right = insertHelper(node->right, value);
        } else {
            std::cerr < "Duplicate value detected: " << value << std::endl;
            return node;
        }
        
        updateHeight(node);
        
        int balance = getBalance(node);
        
        // Left-Left case
        if (balance > 1 && comparator(value, node->left->data)) {
            return rotateRight(node);
        }
        
        // Right-Right case
        if (balance < -1 && comparator(node->right->data, value)) {
            return rotateLeft(node);
        }
        
        // Left-Right case
        if (balance > 1 && comparator(node->left->data, value)) {
            node->left = rotateLeft(node->left);
            return rotateRight(node);
        }
        
        // Right-Left case
        if (balance < -1 && comparator(value, node->right->data)) {
            node->right = rotateRight(node->right);
            return rotateLeft(node);
        }
        
        return node;
    }
    
    // Find minimum value node
    std::shared_ptr<TreeNode<T>> findMin(std::shared_ptr<TreeNode<T>>& node) const {
        while (node && node->left) {
            node = node->left;
        }
        return node;
    }
    
    // ERROR 3: Missing closing brace for function (line 145)
    std::shared_ptr<TreeNode<T>> deleteHelper(std::shared_ptr<TreeNode<T>>& node,
                                                const T& value) {
        if (!node) {
            return node;
        }
        
        if (comparator(value, node->data)) {
            node->left = deleteHelper(node->left, value);
        } else if (comparator(node->data, value)) {
            node->right = deleteHelper(node->right, value);
        } else {
            if (!node->left || !node->right) {
                auto temp = node->left ? node->left : node->right;
                if (!temp) {
                    node = nullptr;
                } else {
                    node = temp;
                }
                tree_size--;
            } else {
                auto temp = findMin(node->right);
                node->data = temp->data;
                node->right = deleteHelper(node->right, temp->data);
            }
        
        // Missing closing brace here
        
        if (!node) {
            return node;
        }
        
        updateHeight(node);
        
        int balance = getBalance(node);
        
        if (balance > 1 && getBalance(node->left) >= 0) {
            return rotateRight(node);
        }
        
        if (balance > 1 && getBalance(node->left) < 0) {
            node->left = rotateLeft(node->left);
            return rotateRight(node);
        }
        
        if (balance < -1 && getBalance(node->right) <= 0) {
            return rotateLeft(node);
        }
        
        if (balance < -1 && getBalance(node->right) > 0) {
            node->right = rotateRight(node->right);
            return rotateLeft(node);
        }
        
        return node;
    }
    
    bool searchHelper(const std::shared_ptr<TreeNode<T>>& node, const T& value) const {
        if (!node) {
            return false;
        }
        
        if (comparator(value, node->data)) {
            return searchHelper(node->left, value);
        } else if (comparator(node->data, value)) {
            return searchHelper(node->right, value);
        }
        
        return true;
    }
    
    void inorderHelper(const std::shared_ptr<TreeNode<T>>& node,
                      std::vector<T>& result) const {
        if (node) {
            inorderHelper(node->left, result);
            result.push_back(node->data);
            inorderHelper(node->right, result);
        }
    }

public:
    BinarySearchTree() : root(nullptr), tree_size(0), comparator(Compare()) {}
    
    explicit BinarySearchTree(const Compare& comp) 
        : root(nullptr), tree_size(0), comparator(comp) {}
    
    void insert(const T& value) {
        root = insertHelper(root, value);
    }
    
    void insert(T&& value) {
        root = insertHelper(root, std::move(value));
    }
    
    bool remove(const T& value) {
        size_t old_size = tree_size;
        root = deleteHelper(root, value);
        return old_size != tree_size;
    }
    
    bool contains(const T& value) const {
        return searchHelper(root, value);
    }
    
    size_t size() const {
        return tree_size;
    }
    
    bool empty() const {
        return tree_size == 0;
    }
    
    std::vector<T> inorderTraversal() const {
        std::vector<T> result;
        result.reserve(tree_size);
        inorderHelper(root, result);
        return result;
    }
    
    void clear() {
        root = nullptr;
        tree_size = 0;
    }
    
    int height() const {
        return getHeight(root);
    }
};

} // namespace DataStructures

// Test driver
int main() {
    using namespace DataStructures;
    
    BinarySearchTree<int> bst;
    
    std::cout << "Inserting elements: 10, 20, 30, 40, 50, 25" << std::endl;
    bst.insert(10);
    bst.insert(20);
    bst.insert(30);
    bst.insert(40);
    bst.insert(50);
    bst.insert(25);
    
    std::cout << "Tree size: " << bst.size() << std::endl;
    std::cout << "Tree height: " << bst.height() << std::endl;
    
    std::cout << "Inorder traversal: ";
    auto elements = bst.inorderTraversal();
    for (const auto& elem : elements) {
        std::cout << elem << " ";
    }
    std::cout << std::endl;
    
    std::cout << "Contains 25? " << (bst.contains(25) ? "Yes" : "No") << std::endl;
    std::cout << "Contains 15? " << (bst.contains(15) ? "Yes" : "No") << std::endl;
    
    bst.remove(20);
    std::cout << "After removing 20, size: " << bst.size() << std::endl;
    
    return 0;
}
'''
    return code

def generate_java_enterprise_service():
    """Generate a large Java enterprise service class with errors."""
    code = '''/**
 * Enterprise Customer Management Service
 * Production-grade Java service with intentional syntax errors for testing.
 */

package com.enterprise.customer;

import java.util.*;
import java.util.stream.Collectors;
import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.locks.ReadWriteLock;
import java.util.concurrent.locks.ReentrantReadWriteLock;
import javax.validation.constraints.*;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

// ERROR 1: Missing semicolon at end of enum (line 22)
enum CustomerTier {
    BRONZE("Bronze", 0.0),
    SILVER("Silver", 0.05),
    GOLD("Gold", 0.10),
    PLATINUM("Platinum", 0.15)
    
    private final String displayName;
    private final double discountRate;
    
    CustomerTier(String displayName, double discountRate) {
        this.displayName = displayName;
        this.discountRate = discountRate;
    }
    
    public String getDisplayName() {
        return displayName;
    }
    
    public double getDiscountRate() {
        return discountRate;
    }
}

class Address {
    @NotNull
    private String street;
    @NotNull
    private String city;
    @NotNull
    private String state;
    @NotNull
    @Pattern(regexp = "\\\\d{5}(-\\\\d{4})?")
    private String zipCode;
    private String country;
    
    public Address(String street, String city, String state, String zipCode, String country) {
        this.street = street;
        this.city = city;
        this.state = state;
        this.zipCode = zipCode;
        this.country = country;
    }
    
    public String getFullAddress() {
        return String.format("%s, %s, %s %s, %s", 
            street, city, state, zipCode, country);
    }
    
    // Getters and setters
    public String getStreet() { return street; }
    public void setStreet(String street) { this.street = street; }
    public String getCity() { return city; }
    public void setCity(String city) { this.city = city; }
    public String getState() { return state; }
    public void setState(String state) { this.state = state; }
    public String getZipCode() { return zipCode; }
    public void setZipCode(String zipCode) { this.zipCode = zipCode; }
}

class Customer {
    private String customerId;
    @NotNull
    @Email
    private String email;
    @NotNull
    private String firstName;
    @NotNull
    private String lastName;
    private Address address;
    private CustomerTier tier;
    private double totalSpent;
    private LocalDateTime createdAt;
    private LocalDateTime lastPurchaseAt;
    private List<String> orderHistory;
    
    public Customer(String customerId, String email, String firstName, 
                    String lastName, Address address) {
        this.customerId = customerId;
        this.email = email;
        this.firstName = firstName;
        this.lastName = lastName;
        this.address = address;
        this.tier = CustomerTier.BRONZE;
        this.totalSpent = 0.0;
        this.createdAt = LocalDateTime.now();
        this.orderHistory = new ArrayList<>();
    }
    
    // ERROR 2: Incorrect indentation in method body (line 116)
    public String getFullName() {
return firstName + " " + lastName;
    }
    
    public void addPurchase(String orderId, double amount) {
        orderHistory.add(orderId);
        totalSpent += amount;
        lastPurchaseAt = LocalDateTime.now();
        updateTier();
    }
    
    private void updateTier() {
        if (totalSpent >= 10000.0) {
            tier = CustomerTier.PLATINUM;
        } else if (totalSpent >= 5000.0) {
            tier = CustomerTier.GOLD;
        } else if (totalSpent >= 1000.0) {
            tier = CustomerTier.SILVER;
        } else {
            tier = CustomerTier.BRONZE;
        }
    }
    
    public double calculateDiscount(double amount) {
        return amount * tier.getDiscountRate();
    }
    
    public Map<String, Object> toMap() {
        Map<String, Object> map = new HashMap<>();
        map.put("customerId", customerId);
        map.put("email", email);
        map.put("fullName", getFullName());
        map.put("tier", tier.getDisplayName());
        map.put("totalSpent", totalSpent);
        map.put("orderCount", orderHistory.size());
        map.put("createdAt", createdAt);
        return map;
    }
    
    // Getters
    public String getCustomerId() { return customerId; }
    public String getEmail() { return email; }
    public CustomerTier getTier() { return tier; }
    public double getTotalSpent() { return totalSpent; }
    public List<String> getOrderHistory() { return new ArrayList<>(orderHistory); }
}

public class CustomerManagementService {
    private static final Logger logger = LoggerFactory.getLogger(CustomerManagementService.class);
    private static final DateTimeFormatter DATE_FORMATTER = 
        DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss");
    
    private final Map<String, Customer> customers;
    private final ReadWriteLock lock;
    private long customerIdCounter;
    
    public CustomerManagementService() {
        this.customers = new ConcurrentHashMap<>();
        this.lock = new ReentrantReadWriteLock();
        this.customerIdCounter = 1000;
        initializeSampleCustomers();
    }
    
    private void initializeSampleCustomers() {
        createCustomer("john.doe@example.com", "John", "Doe",
            new Address("123 Main St", "New York", "NY", "10001", "USA"));
        createCustomer("jane.smith@example.com", "Jane", "Smith",
            new Address("456 Oak Ave", "Los Angeles", "CA", "90001", "USA"));
    }
    
    // ERROR 3: Missing opening brace for method (line 195)
    public String createCustomer(String email, String firstName, String lastName, Address address) 
        lock.writeLock().lock();
        try {
            String customerId = "CUST-" + String.format("%06d", customerIdCounter++);
            Customer customer = new Customer(customerId, email, firstName, lastName, address);
            customers.put(customerId, customer);
            
            logger.info("Customer created: {} - {}", customerId, customer.getFullName());
            return customerId;
        } finally {
            lock.writeLock().unlock();
        }
    }
    
    public Optional<Customer> getCustomer(String customerId) {
        lock.readLock().lock();
        try {
            return Optional.ofNullable(customers.get(customerId));
        } finally {
            lock.readLock().unlock();
        }
    }
    
    public boolean updateCustomerAddress(String customerId, Address newAddress) {
        lock.writeLock().lock();
        try {
            Customer customer = customers.get(customerId);
            if (customer == null) {
                logger.warn("Customer not found: {}", customerId);
                return false;
            }
            
            customer.address = newAddress;
            logger.info("Address updated for customer: {}", customerId);
            return true;
        } finally {
            lock.writeLock().unlock();
        }
    }
    
    public void recordPurchase(String customerId, String orderId, double amount) {
        lock.writeLock().lock();
        try {
            Customer customer = customers.get(customerId);
            if (customer == null) {
                throw new IllegalArgumentException("Customer not found: " + customerId);
            }
            
            customer.addPurchase(orderId, amount);
            logger.info("Purchase recorded for {}: {} - ${}", 
                customerId, orderId, amount);
        } finally {
            lock.writeLock().unlock();
        }
    }
    
    public List<Customer> searchCustomersByTier(CustomerTier tier) {
        lock.readLock().lock();
        try {
            return customers.values().stream()
                .filter(c -> c.getTier() == tier)
                .collect(Collectors.toList());
        } finally {
            lock.readLock().unlock();
        }
    }
    
    public List<Customer> getTopCustomers(int limit) {
        lock.readLock().lock();
        try {
            return customers.values().stream()
                .sorted((c1, c2) -> Double.compare(c2.getTotalSpent(), c1.getTotalSpent()))
                .limit(limit)
                .collect(Collectors.toList());
        } finally {
            lock.readLock().unlock();
        }
    }
    
    public Map<String, Object> getStatistics() {
        lock.readLock().lock();
        try {
            Map<String, Object> stats = new HashMap<>();
            stats.put("totalCustomers", customers.size());
            
            long bronzeCount = customers.values().stream()
                .filter(c -> c.getTier() == CustomerTier.BRONZE).count();
            long silverCount = customers.values().stream()
                .filter(c -> c.getTier() == CustomerTier.SILVER).count();
            long goldCount = customers.values().stream()
                .filter(c -> c.getTier() == CustomerTier.GOLD).count();
            long platinumCount = customers.values().stream()
                .filter(c -> c.getTier() == CustomerTier.PLATINUM).count();
            
            stats.put("tierDistribution", Map.of(
                "bronze", bronzeCount,
                "silver", silverCount,
                "gold", goldCount,
                "platinum", platinumCount
            ));
            
            double totalRevenue = customers.values().stream()
                .mapToDouble(Customer::getTotalSpent)
                .sum();
            stats.put("totalRevenue", totalRevenue);
            
            return stats;
        } finally {
            lock.readLock().unlock();
        }
    }
    
    public static void main(String[] args) {
        CustomerManagementService service = new CustomerManagementService();
        
        System.out.println("Customer Management System Started");
        System.out.println("===================================");
        
        Map<String, Object> stats = service.getStatistics();
        System.out.println("Total Customers: " + stats.get("totalCustomers"));
        System.out.println("Total Revenue: $" + stats.get("totalRevenue"));
        
        List<Customer> topCustomers = service.getTopCustomers(5);
        System.out.println("\\nTop Customers:");
        for (Customer customer : topCustomers) {
            System.out.printf("  %s - %s (Tier: %s, Spent: $%.2f)%n",
                customer.getCustomerId(),
                customer.getFullName(),
                customer.getTier().getDisplayName(),
                customer.getTotalSpent());
        }
    }
}
'''
    return code

def main():
    """Generate all test files."""
    print("🔧 Generating real-world syntax test files...")
    
    test_dir = create_test_directory()
    print(f"✓ Created directory: {test_dir}")
    
    # Generate Python file
    py_file = test_dir / "order_service.py"
    py_file.write_text(generate_python_webservice(), encoding='utf-8')
    print(f"✓ Generated: {py_file} (Python web service, ~280 lines)")
    
    # Generate C++ file
    cpp_file = test_dir / "bst_template.cpp"
    cpp_file.write_text(generate_cpp_data_structure(), encoding='utf-8')
    print(f"✓ Generated: {cpp_file} (C++ template BST, ~300 lines)")
    
    # Generate Java file
    java_file = test_dir / "CustomerManagementService.java"
    java_file.write_text(generate_java_enterprise_service(), encoding='utf-8')
    print(f"✓ Generated: {java_file} (Java enterprise service, ~320 lines)")
    
    print("\\n✅ Real-world test suite generated!")
    print("\\nError Summary:")
    print("  Python (order_service.py):")
    print("    - Line 17: Unterminated string")
    print("    - Line 51: Incorrect indentation")
    print("    - Line 126: Missing colon")
    print("\\n  C++ (bst_template.cpp):")
    print("    - Line 18: Missing semicolon")
    print("    - Line 86: Missing << operator")
    print("    - Line 145: Missing closing brace")
    print("\\n  Java (CustomerManagementService.java):")
    print("    - Line 22: Missing semicolon in enum")
    print("    - Line 116: Incorrect indentation")
    print("    - Line 195: Missing opening brace")
    print("\\nRun: python main.py analyze ./realistic_test --vllm-url http://127.0.0.1:1234/v1")

if __name__ == "__main__":
    main()
