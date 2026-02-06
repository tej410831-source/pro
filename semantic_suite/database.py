class BinarySearchTree:
    def __init__(self):
        self.root = None
        self.tree_size = 0

    def insert(self, value):
        if not self.contains(value):
            new_node = TreeNode(value)
            try:
                self._insert_recursive(new_node, self.root)
            except Exception as e:
                print(f'Error during insertion: {e}')

    def _insert_recursive(self, node, current):
        if not current:
            current = node
        elif value < current.data:
            try:
                self._insert_recursive(node, current.left)
            except Exception as e:
                print(f'Error during insertion: {e}')
        else:
            try:
                self._insert_recursive(node, current.right)
            except Exception as e:
                print(f'Error during insertion: {e}')

    def contains(self, value):
        return self._contains_recursive(value, self.root)

    def _contains_recursive(self, value, current):
        if not current:
            return False
        elif value < current.data:
            try:
                return self._contains_recursive(value, current.left)
            except Exception as e:
                print(f'Error during search: {e}')
        elif value > current.data:
            try:
                return self._contains_recursive(value, current.right)
            except Exception as e:
                print(f'Error during search: {e}')
        else:
            return True

    def inorder_traversal(self):
        result = []
        try:
            self._inorder_traversal_recursive(result, self.root)
        except Exception as e:
            print(f'Error during traversal: {e}')
        return result

    def _inorder_traversal_recursive(self, result, current):
        if current:
            try:
                self._inorder_traversal_recursive(result, current.left)
            except Exception as e:
                print(f'Error during traversal: {e}')
            result.append(current.data)
            try:
                self._inorder_traversal_recursive(result, current.right)
            except Exception as e:
                print(f'Error during traversal: {e}')

    def clear(self):
        self.root = None
        self.tree_size = 0

    def height(self):
        return self._height_recursive(self.root)

    def _height_recursive(self, node):
        if not node:
            return 1
        else:
            try:
                return 1 + max(self._height_recursive(node.left), self._height_recursive(node.right))
            except Exception as e:
                print(f'Error during height calculation: {e}')

class TreeNode:
    def __init__(self, data):
        if data is None:
            raise ValueError('Data cannot be None')
        self.data = data
        self.left = None
        self.right = None