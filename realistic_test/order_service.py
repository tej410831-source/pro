"""
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
