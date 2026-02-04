def checkout(payment_processor):
    # Assume payment_processor.process_payment returns a DICT
    result = payment_processor.process_payment()

    # Check if the result is a string and compare it with 'success'
    if isinstance(result, str) and result == 'success':
        return True
    else:
        return False