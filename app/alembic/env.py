import sys
from pathlib import Path

# Ensure the app directory is on the path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from database.database import Base

from models.product_model import Product
from models.user_model import User
from models.business_model import Business
from models.customer_model import Customer
from models.transaction_model import Transaction
from models.transaction_item_model import TransactionItem
from models.inventory_movement_model import InventoryMovement
from models.subscription_model import Subscription


target_metadata = Base.metadata
