from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from typing import Iterable

from auth.errors import DomainError


MONEY = Decimal("0.01")


def as_decimal(value: object) -> Decimal:
    try:
        return Decimal(str(value if value is not None else "0"))
    except Exception as exc:
        raise DomainError(400, "PAYMENT_INVALID", "A monetary value is invalid.") from exc


def money(value: Decimal) -> Decimal:
    return value.quantize(MONEY, rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class CalculatedLine:
    product: object
    quantity: int
    unit_price: Decimal
    gst_percentage: Decimal
    subtotal: Decimal
    tax: Decimal
    cgst: Decimal
    sgst: Decimal
    igst: Decimal


@dataclass(frozen=True)
class BillingTotals:
    lines: tuple[CalculatedLine, ...]
    subtotal: Decimal
    total_tax: Decimal
    total_cgst: Decimal
    total_sgst: Decimal
    total_igst: Decimal
    discount: Decimal
    previous_balance: Decimal
    payable: Decimal


class BillingEngine:
    """The sole authoritative calculation path for a product checkout."""

    @staticmethod
    def calculate(
        *,
        product_lines: Iterable[tuple[object, int]],
        discount: object = Decimal("0"),
        previous_balance: object = Decimal("0"),
        is_intra_state: bool = True,
    ) -> BillingTotals:
        lines: list[CalculatedLine] = []
        subtotal = Decimal("0")
        total_tax = Decimal("0")
        total_cgst = Decimal("0")
        total_sgst = Decimal("0")
        total_igst = Decimal("0")
        for product, quantity in product_lines:
            if quantity <= 0:
                raise DomainError(400, "INVALID_QUANTITY", "Item quantity must be positive.")
            # A zero stock quantity is handled by InventoryService so callers
            # receive the actionable INSUFFICIENT_STOCK error instead of an
            # ambiguous availability failure.
            if getattr(product, "is_deleted", False):
                raise DomainError(409, "PRODUCT_INACTIVE", "A product is not available for sale.")
            unit_price = money(as_decimal(product.price))
            gst_percentage = as_decimal(product.gst_percentage)
            line_subtotal = money(unit_price * quantity)
            line_tax = money(line_subtotal * gst_percentage / Decimal("100"))
            cgst = money(line_tax / Decimal("2")) if is_intra_state else Decimal("0")
            sgst = money(line_tax - cgst) if is_intra_state else Decimal("0")
            igst = line_tax if not is_intra_state else Decimal("0")
            lines.append(CalculatedLine(product, quantity, unit_price, gst_percentage, line_subtotal, line_tax, cgst, sgst, igst))
            subtotal += line_subtotal
            total_tax += line_tax
            total_cgst += cgst
            total_sgst += sgst
            total_igst += igst
        discount_value = money(as_decimal(discount))
        if discount_value < 0 or discount_value > subtotal:
            raise DomainError(400, "INVALID_DISCOUNT", "Discount must be between zero and the subtotal.")
        previous = money(as_decimal(previous_balance))
        if previous < 0:
            raise DomainError(400, "PAYMENT_INVALID", "Previous balance is invalid.")
        return BillingTotals(
            lines=tuple(lines),
            subtotal=money(subtotal),
            total_tax=money(total_tax),
            total_cgst=money(total_cgst),
            total_sgst=money(total_sgst),
            total_igst=money(total_igst),
            discount=discount_value,
            previous_balance=previous,
            payable=money(subtotal + total_tax - discount_value + previous),
        )
