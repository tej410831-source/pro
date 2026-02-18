
import sys
import os

print(f"Python: {sys.executable}")

try:
    import tree_sitter
    from tree_sitter import Parser
    print(f"tree_sitter path: {tree_sitter.__file__}")
    print(f"Parser class: {Parser}")
    
    try:
        p = Parser()
        print("Parser() success")
    except Exception as e:
        print(f"Parser() failed: {e}")

    import tree_sitter_languages
    print(f"tree_sitter_languages path: {tree_sitter_languages.__file__}")
    
    try:
        lang = tree_sitter_languages.get_language('c')
        print(f"get_language('c') success: {lang}")
        print(f"Language type: {type(lang)}")
    except Exception as e:
        print(f"get_language('c') failed: {e}")

    try:
        # Try to use language with Parser
        p = Parser()
        # In new tree-sitter, we set language
        if hasattr(p, 'language'):
            print("Parser has .language property")
            if 'lang' in locals():
                p.language = lang
                print("p.language = lang success")
        else:
            print("Parser has NO .language property")
            if 'lang' in locals():
                p.set_language(lang)
                print("p.set_language(lang) success")

    except Exception as e:
        print(f"Parser usage failed: {e}")

    try:
        p = tree_sitter_languages.get_parser('c')
        print("get_parser('c') success")
    except Exception as e:
        print(f"get_parser('c') failed: {e}")

except Exception as e:
    print(f"Top level error: {e}")
