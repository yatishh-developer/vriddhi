from datetime import datetime


class InvoiceGenerator:

    @staticmethod
    def generate_invoice_number():

        timestamp = datetime.now().strftime(
            "%Y%m%d%H%M%S"
        )

        return f"INV-{timestamp}"