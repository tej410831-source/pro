import tree_sitter_languages
from tree_sitter import Parser

def check(code):
    parser = tree_sitter_languages.get_parser('c')
    tree = parser.parse(bytes(code, 'utf-8'))
    
    print(f"Root type: {tree.root_node.type}")
    print(f"Has error: {tree.root_node.has_error}")
    
    def walk(node, depth=0):
        if node.type == 'ERROR' or node.is_missing:
            print(f"{'  '*depth}Found Error Node: Type={node.type}, Missing={node.is_missing}, Text={node.text}")
        
        for child in node.children:
            walk(child, depth+1)

    walk(tree.root_node)

code = """
int factorial(int n) {
    if(n<0)return -1
    if (n == 0) return 1;
    return n * factorial(n - 1);
}
"""
check(code)
