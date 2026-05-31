import re


def validate_barcode(barcode: str):

    if barcode is None:
        return True

    return bool(
        re.fullmatch(r"^[0-9]{8,18}$", barcode)
    )