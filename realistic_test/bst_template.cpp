/**
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
