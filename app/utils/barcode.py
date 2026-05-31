import random


def generate_barcode():

    return ''.join(
        str(random.randint(0, 9))
        for _ in range(13)
    )