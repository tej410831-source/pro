TRANSACTION_REGISTRY = {}

def process_payment(credit_card, amount):
    print(f"Processing ${amount} for card {credit_card[-4:]}")

    tx_id = f"TX-{len(TRANSACTION_REGISTRY) + 1000}"
    result = {
        "status":  "APPROVED"
    }
    return result