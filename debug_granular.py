
from utils.diff_analyzer import DiffAnalyzer
from analyzers.syntax_fix_generator import SyntaxFixGenerator

# 1. Broken Code (from payment_processor.py)
broken_code = """
TRANSACTION_REGISTRY = {}

def process_payment(credit_card, amount):
    print(f"Processing ${amount} for card {credit_card[-4:]}")
    
    tx_id = f"TX-{len(TRANSACTION_REGISTRY) + 1000}"
    result = {
        "status": "APPROVED
    return result
"""

# 2. Correct Code (Simulating a perfect LLM response)
fixed_code = """
TRANSACTION_REGISTRY = {}

def process_payment(credit_card, amount):
    print(f"Processing ${amount} for card {credit_card[-4:]}")
    
    tx_id = f"TX-{len(TRANSACTION_REGISTRY) + 1000}"
    result = {
        "status": "APPROVED"
    }
    return result
"""

print("--- DEBUGGING GRANULAR FIX LOGIC ---")

# 3. Compute Changes
analyzer = DiffAnalyzer()
changes = analyzer.compute_changes(broken_code, fixed_code)

print(f"\n1. Changes Detected: {len(changes)}")
for i, c in enumerate(changes):
    print(f"   Change {i+1}: {c.description}")
    print(f"   Original Lines: {c.original_lines}")
    print(f"   Fixed Lines:    {c.fixed_lines}\n")

# 4. Apply Changes
generator = SyntaxFixGenerator(None) # Mock client
merged_code = generator.apply_selective_changes(broken_code, changes)

print("2. Merged Result:")
print("-" * 20)
print(merged_code)
print("-" * 20)

# 5. Check Equality
if merged_code.strip() == fixed_code.strip():
    print("\nSUCCESS: Merging working correctly! ✅")
    print("The issue is likely the LLM output.")
else:
    print("\nFAILURE: Merging produced incorrect code! ❌")
    print("The issue is in apply_selective_changes or DiffAnalyzer.")
