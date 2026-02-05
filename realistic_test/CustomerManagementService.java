/**
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
    @Pattern(regexp = "\\d{5}(-\\d{4})?")
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
        System.out.println("\nTop Customers:");
        for (Customer customer : topCustomers) {
            System.out.printf("  %s - %s (Tier: %s, Spent: $%.2f)%n",
                customer.getCustomerId(),
                customer.getFullName(),
                customer.getTier().getDisplayName(),
                customer.getTotalSpent());
        }
    }
}
