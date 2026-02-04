""
def process_payment(credit_card, amount):
    """
    Simulate processing a payment.
    Updates the global registry.
    """
    print(f"Processing ${amount} for card {credit_card[-4:]}")
    
    tx_id = f"TX-{len(TRANSACTION_REGISTRY) + 1000}"
    result = {
        "status": "APPROVED"
    
    return result