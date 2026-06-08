import '../menu/menu_models.dart';

enum OrderType { dineIn, takeaway, delivery, parcel }

enum KotStatus { pending, preparing, ready, served, convertedToBill, cancelled }

enum BillStatus { draft, held, paid, voided }

class LocalKotItem {
  const LocalKotItem({
    required this.productId,
    required this.name,
    required this.quantity,
    required this.price,
    required this.taxRate,
    this.notes,
  });

  factory LocalKotItem.fromProduct(LocalProduct product, int quantity) {
    return LocalKotItem(
      productId: product.id,
      name: product.name,
      quantity: quantity,
      price: product.price,
      taxRate: product.taxRate,
    );
  }

  factory LocalKotItem.fromJson(Map<String, dynamic> json) {
    return LocalKotItem(
      productId: json['productId'] as String,
      name: json['name'] as String,
      quantity: json['quantity'] as int,
      price: (json['price'] as num).toDouble(),
      taxRate: (json['taxRate'] as num).toDouble(),
      notes: json['notes'] as String?,
    );
  }

  final String productId;
  final String name;
  final int quantity;
  final double price;
  final double taxRate;
  final String? notes;

  double get subtotal => price * quantity;
  double get taxAmount => subtotal * taxRate / 100;
  double get total => subtotal + taxAmount;

  Map<String, dynamic> toJson() => {
    'productId': productId,
    'name': name,
    'quantity': quantity,
    'price': price,
    'taxRate': taxRate,
    'notes': notes,
  };
}

class LocalKot {
  const LocalKot({
    required this.localId,
    this.serverId,
    required this.kotNumber,
    required this.businessId,
    required this.branchId,
    required this.staffId,
    this.tableNumber,
    required this.orderType,
    required this.items,
    this.notes,
    required this.status,
    required this.idempotencyKey,
    required this.createdAt,
    required this.updatedAt,
    required this.syncStatus,
  });

  final String localId;
  final String? serverId;
  final String kotNumber;
  final String businessId;
  final String branchId;
  final String staffId;
  final String? tableNumber;
  final OrderType orderType;
  final List<LocalKotItem> items;
  final String? notes;
  final KotStatus status;
  final String idempotencyKey;
  final DateTime createdAt;
  final DateTime updatedAt;
  final String syncStatus;

  bool get canConvert =>
      status != KotStatus.convertedToBill && status != KotStatus.cancelled;

  double get total => items.fold<double>(0, (sum, item) => sum + item.total);

  factory LocalKot.fromJson(Map<String, dynamic> json) {
    return LocalKot(
      localId: json['localId'] as String,
      serverId: json['serverId'] as String?,
      kotNumber: json['kotNumber'] as String,
      businessId: json['businessId'] as String,
      branchId: json['branchId'] as String,
      staffId: json['staffId'] as String,
      tableNumber: json['tableNumber'] as String?,
      orderType: OrderType.values.firstWhere(
        (value) => value.name == json['orderType'],
        orElse: () => OrderType.dineIn,
      ),
      items: (json['items'] as List)
          .whereType<Map>()
          .map(
            (value) => LocalKotItem.fromJson(Map<String, dynamic>.from(value)),
          )
          .toList(),
      notes: json['notes'] as String?,
      status: KotStatus.values.firstWhere(
        (value) => value.name == json['status'],
        orElse: () => KotStatus.pending,
      ),
      idempotencyKey: json['idempotencyKey'] as String,
      createdAt: DateTime.parse(json['createdAt'] as String),
      updatedAt: DateTime.parse(json['updatedAt'] as String),
      syncStatus: json['syncStatus'] as String? ?? 'pending',
    );
  }

  Map<String, dynamic> toJson() => {
    'localId': localId,
    'serverId': serverId,
    'kotNumber': kotNumber,
    'businessId': businessId,
    'branchId': branchId,
    'staffId': staffId,
    'tableNumber': tableNumber,
    'orderType': orderType.name,
    'items': items.map((item) => item.toJson()).toList(),
    'notes': notes,
    'status': status.name,
    'idempotencyKey': idempotencyKey,
    'createdAt': createdAt.toIso8601String(),
    'updatedAt': updatedAt.toIso8601String(),
    'syncStatus': syncStatus,
  };
}

class LocalPayment {
  const LocalPayment({this.cash = 0, this.upi = 0, this.card = 0});

  final double cash;
  final double upi;
  final double card;

  factory LocalPayment.fromJson(Map<String, dynamic> json) {
    return LocalPayment(
      cash: (json['cash'] as num? ?? 0).toDouble(),
      upi: (json['upi'] as num? ?? 0).toDouble(),
      card: (json['card'] as num? ?? 0).toDouble(),
    );
  }

  double get paidAmount => cash + upi + card;

  String? validate(double total, {bool creditAllowed = false}) {
    if (cash < 0 || upi < 0 || card < 0) {
      return 'Payment cannot be negative.';
    }
    if (!creditAllowed && paidAmount < total) {
      return 'Paid amount is less than total.';
    }
    return null;
  }

  double changeFor(double total) => paidAmount > total ? paidAmount - total : 0;

  Map<String, dynamic> toJson() => {'cash': cash, 'upi': upi, 'card': card};
}

class LocalBill {
  const LocalBill({
    required this.localId,
    this.serverId,
    required this.billNumber,
    this.linkedKotLocalId,
    this.linkedKotServerId,
    required this.businessId,
    required this.branchId,
    required this.staffId,
    required this.items,
    required this.paymentBreakdown,
    required this.subtotal,
    required this.tax,
    required this.total,
    required this.status,
    required this.idempotencyKey,
    required this.createdAt,
    required this.updatedAt,
    required this.syncStatus,
  });

  final String localId;
  final String? serverId;
  final String billNumber;
  final String? linkedKotLocalId;
  final String? linkedKotServerId;
  final String businessId;
  final String branchId;
  final String staffId;
  final List<LocalKotItem> items;
  final LocalPayment paymentBreakdown;
  final double subtotal;
  final double tax;
  final double total;
  final BillStatus status;
  final String idempotencyKey;
  final DateTime createdAt;
  final DateTime updatedAt;
  final String syncStatus;

  factory LocalBill.fromJson(Map<String, dynamic> json) {
    return LocalBill(
      localId: json['localId'] as String,
      serverId: json['serverId'] as String?,
      billNumber: json['billNumber'] as String,
      linkedKotLocalId: json['linkedKotLocalId'] as String?,
      linkedKotServerId: json['linkedKotServerId'] as String?,
      businessId: json['businessId'] as String,
      branchId: json['branchId'] as String,
      staffId: json['staffId'] as String,
      items: (json['items'] as List)
          .whereType<Map>()
          .map(
            (value) => LocalKotItem.fromJson(Map<String, dynamic>.from(value)),
          )
          .toList(),
      paymentBreakdown: LocalPayment.fromJson(
        Map<String, dynamic>.from(json['paymentBreakdown'] as Map),
      ),
      subtotal: (json['subtotal'] as num).toDouble(),
      tax: (json['tax'] as num).toDouble(),
      total: (json['total'] as num).toDouble(),
      status: BillStatus.values.firstWhere(
        (value) => value.name == json['status'],
        orElse: () => BillStatus.paid,
      ),
      idempotencyKey: json['idempotencyKey'] as String,
      createdAt: DateTime.parse(json['createdAt'] as String),
      updatedAt: DateTime.parse(json['updatedAt'] as String),
      syncStatus: json['syncStatus'] as String? ?? 'pending',
    );
  }

  Map<String, dynamic> toJson() => {
    'localId': localId,
    'serverId': serverId,
    'billNumber': billNumber,
    'linkedKotLocalId': linkedKotLocalId,
    'linkedKotServerId': linkedKotServerId,
    'businessId': businessId,
    'branchId': branchId,
    'staffId': staffId,
    'items': items.map((item) => item.toJson()).toList(),
    'paymentBreakdown': paymentBreakdown.toJson(),
    'subtotal': subtotal,
    'tax': tax,
    'total': total,
    'status': status.name,
    'idempotencyKey': idempotencyKey,
    'createdAt': createdAt.toIso8601String(),
    'updatedAt': updatedAt.toIso8601String(),
    'syncStatus': syncStatus,
  };
}

class BillingRules {
  const BillingRules._();

  static String? canConvertKot(LocalKot kot) {
    if (kot.status == KotStatus.convertedToBill) {
      return 'KOT is already converted to a bill.';
    }
    if (kot.status == KotStatus.cancelled) {
      return 'Cancelled KOT cannot be converted.';
    }
    return null;
  }
}
