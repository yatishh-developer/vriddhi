class LocalCategory {
  const LocalCategory({
    required this.id,
    required this.businessId,
    required this.branchId,
    required this.name,
    required this.updatedAt,
  });

  final String id;
  final String businessId;
  final String branchId;
  final String name;
  final DateTime updatedAt;
}

class LocalProduct {
  const LocalProduct({
    required this.id,
    required this.businessId,
    required this.branchId,
    required this.name,
    required this.categoryId,
    required this.categoryName,
    required this.price,
    required this.taxRate,
    required this.unit,
    this.barcode,
    required this.isAvailable,
    required this.updatedAt,
    required this.syncVersion,
  });

  final String id;
  final String businessId;
  final String branchId;
  final String name;
  final String categoryId;
  final String categoryName;
  final double price;
  final double taxRate;
  final String unit;
  final String? barcode;
  final bool isAvailable;
  final DateTime updatedAt;
  final int syncVersion;

  factory LocalProduct.fromBackendJson(Map<String, dynamic> json) {
    final category = json['category']?.toString() ?? '';
    final now = DateTime.now();
    return LocalProduct(
      id: json['id']?.toString() ?? '',
      businessId: json['business_id']?.toString() ?? '',
      branchId: json['branch_id']?.toString() ?? 'main',
      name: json['name']?.toString() ?? 'Item',
      categoryId: category.isEmpty ? 'uncategorized' : category,
      categoryName: category.isEmpty ? 'Uncategorized' : category,
      price: (json['price'] as num?)?.toDouble() ?? 0,
      taxRate: (json['gst_percentage'] as num?)?.toDouble() ?? 0,
      unit: json['unit']?.toString() ?? 'unit',
      barcode: json['barcode']?.toString(),
      isAvailable: json['in_stock'] as bool? ?? true,
      updatedAt: DateTime.tryParse(json['updated_at']?.toString() ?? '') ?? now,
      syncVersion: 1,
    );
  }

  factory LocalProduct.fromJson(Map<String, dynamic> json) {
    return LocalProduct(
      id: json['id'] as String,
      businessId: json['businessId'] as String? ?? '',
      branchId: json['branchId'] as String? ?? '',
      name: json['name'] as String,
      categoryId: json['categoryId'] as String? ?? 'uncategorized',
      categoryName: json['categoryName'] as String? ?? 'Uncategorized',
      price: (json['price'] as num).toDouble(),
      taxRate: (json['taxRate'] as num? ?? 0).toDouble(),
      unit: json['unit'] as String? ?? 'unit',
      barcode: json['barcode'] as String?,
      isAvailable: json['isAvailable'] as bool? ?? true,
      updatedAt: DateTime.parse(json['updatedAt'] as String),
      syncVersion: json['syncVersion'] as int? ?? 1,
    );
  }

  Map<String, dynamic> toJson() => {
    'id': id,
    'businessId': businessId,
    'branchId': branchId,
    'name': name,
    'categoryId': categoryId,
    'categoryName': categoryName,
    'price': price,
    'taxRate': taxRate,
    'unit': unit,
    'barcode': barcode,
    'isAvailable': isAvailable,
    'updatedAt': updatedAt.toIso8601String(),
    'syncVersion': syncVersion,
  };
}
