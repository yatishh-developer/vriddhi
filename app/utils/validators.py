import re


# Sentinel used by the Flutter client for products that have no barcode.
# Stored verbatim so the per-product value stays unique (the barcode column
# has a unique index) without colliding with real numeric barcodes.
NO_BARCODE_PREFIX = "__no_barcode__"


def validate_barcode(barcode: str):
    """Validate a product barcode.

    Accepts:
      • None / empty string        → product simply has no barcode
      • the no-barcode sentinel    → client-side placeholder for "no barcode"
      • 8–18 digit numeric strings → real EAN/UPC/etc. barcodes
    """
    if barcode is None:
        return True

    if barcode == "" or barcode.startswith(NO_BARCODE_PREFIX):
        return True

    return bool(re.fullmatch(r"^[0-9]{8,18}$", barcode))
