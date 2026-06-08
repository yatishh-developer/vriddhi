class LocalBusinessProfile {
  const LocalBusinessProfile({
    required this.businessId,
    required this.businessName,
    required this.businessType,
    required this.branchId,
    required this.updatedAt,
  });

  final String businessId;
  final String businessName;
  final String businessType;
  final String branchId;
  final DateTime updatedAt;
}

class LocalFeatureFlags {
  const LocalFeatureFlags({
    required this.businessId,
    required this.branchId,
    required this.flagsJson,
    required this.updatedAt,
  });

  final String businessId;
  final String branchId;
  final String flagsJson;
  final DateTime updatedAt;
}

class LocalCartItem {
  const LocalCartItem({
    required this.productId,
    required this.productName,
    required this.quantity,
    required this.price,
    required this.gstPercentage,
    required this.updatedAt,
  });

  final String productId;
  final String productName;
  final int quantity;
  final double price;
  final double gstPercentage;
  final DateTime updatedAt;
}

class LocalKotItem {
  const LocalKotItem({
    required this.productId,
    required this.productName,
    required this.quantity,
    required this.price,
    required this.gstPercentage,
  });

  final String productId;
  final String productName;
  final int quantity;
  final double price;
  final double gstPercentage;
}

class LocalHeldBill {
  const LocalHeldBill({
    required this.id,
    required this.businessId,
    required this.branchId,
    required this.staffId,
    required this.itemsJson,
    required this.idempotencyKey,
    required this.status,
    required this.createdAt,
    required this.updatedAt,
  });

  final String id;
  final String businessId;
  final String branchId;
  final String staffId;
  final String itemsJson;
  final String idempotencyKey;
  final String status;
  final DateTime createdAt;
  final DateTime updatedAt;
}

class LocalBillItem {
  const LocalBillItem({
    required this.productId,
    required this.productName,
    required this.quantity,
    required this.price,
    required this.gstPercentage,
  });

  final String productId;
  final String productName;
  final int quantity;
  final double price;
  final double gstPercentage;
}

class LocalProcessLock {
  const LocalProcessLock({
    required this.processId,
    required this.processType,
    required this.entityId,
    required this.handledByStaffId,
    required this.handledByStaffName,
    required this.status,
    required this.expiresAt,
  });

  final String processId;
  final String processType;
  final String entityId;
  final String handledByStaffId;
  final String handledByStaffName;
  final String status;
  final DateTime expiresAt;
}
