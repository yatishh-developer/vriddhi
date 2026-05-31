from decimal import Decimal
from decimal import ROUND_HALF_UP


class GSTService:

    GST_TYPES = {
        "GST_0": Decimal("0"),
        "GST_5": Decimal("5"),
        "GST_12": Decimal("12"),
        "GST_18": Decimal("18"),
        "GST_28": Decimal("28"),
    }


    @staticmethod
    def round_amount(value: Decimal):

        return value.quantize(
            Decimal("0.01"),
            rounding=ROUND_HALF_UP
        )
    
    @staticmethod
    def calculate_gst(
        amount: float,
        gst_percentage: float
    ):

        amount = Decimal(str(amount))

        gst_percentage = Decimal(
            str(gst_percentage)
        )

        gst_amount = (
            amount * gst_percentage
        ) / Decimal("100")

        gst_amount = GSTService.round_amount(
            gst_amount
        )

        final_amount = GSTService.round_amount(
            amount + gst_amount
        )

        cgst = GSTService.round_amount(
            gst_amount / Decimal("2")
        )

        sgst = GSTService.round_amount(
            gst_amount / Decimal("2")
        )

        return {
            "base_amount": float(amount),

            "gst_percentage": float(
                gst_percentage
            ),

            "gst_amount": float(
                gst_amount
            ),

            "cgst": float(cgst),

            "sgst": float(sgst),

            "final_amount": float(
                final_amount
            )
        }
        
    @staticmethod
    def calculate_invoice_totals(
        items: list
    ):

        subtotal = Decimal("0")

        total_gst = Decimal("0")

        final_total = Decimal("0")

        processed_items = []

        for item in items:

            quantity = Decimal(
                str(item["quantity"])
            )

            price = Decimal(
                str(item["price"])
            )

            gst_percentage = Decimal(
                str(item["gst_percentage"])
            )

            line_subtotal = (
                quantity * price
            )

            gst_data = GSTService.calculate_gst(
                float(line_subtotal),
                float(gst_percentage)
            )

            subtotal += line_subtotal

            total_gst += Decimal(
                str(gst_data["gst_amount"])
            )

            final_total += Decimal(
                str(gst_data["final_amount"])
            )

            processed_items.append({

                "product_name": item[
                    "product_name"
                ],

                "quantity": int(quantity),

                "price": float(price),

                "subtotal": float(
                    GSTService.round_amount(
                        line_subtotal
                    )
                ),

                "gst_percentage": float(
                    gst_percentage
                ),

                "gst_amount": gst_data[
                    "gst_amount"
                ],

                "final_amount": gst_data[
                    "final_amount"
                ]
            })

        return {

            "items": processed_items,

            "subtotal": float(
                GSTService.round_amount(
                    subtotal
                )
            ),

            "total_gst": float(
                GSTService.round_amount(
                    total_gst
                )
            ),

            "grand_total": float(
                GSTService.round_amount(
                    final_total
                )
            )
        }