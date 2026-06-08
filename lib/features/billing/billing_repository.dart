import 'package:hive/hive.dart';
import 'package:uuid/uuid.dart';

import '../../core/storage/local_database.dart';
import '../sync/sync_queue_service.dart';
import 'billing_models.dart';

class BillingRepository {
  BillingRepository(this._syncQueue, {LocalDatabase? database, Uuid? uuid})
    : _database = database ?? LocalDatabase.instance,
      _uuid = uuid ?? const Uuid();

  final SyncQueueService _syncQueue;
  final LocalDatabase _database;
  final Uuid _uuid;

  List<LocalKot> kots() =>
      _kotBox.values
          .whereType<Map>()
          .map((value) => LocalKot.fromJson(Map<String, dynamic>.from(value)))
          .toList()
        ..sort((a, b) => b.createdAt.compareTo(a.createdAt));

  List<LocalBill> bills() =>
      _billBox.values
          .whereType<Map>()
          .map((value) => LocalBill.fromJson(Map<String, dynamic>.from(value)))
          .toList()
        ..sort((a, b) => b.createdAt.compareTo(a.createdAt));

  Future<LocalKot> createKot({
    required String businessId,
    required String branchId,
    required String staffId,
    required OrderType orderType,
    required List<LocalKotItem> items,
    String? tableNumber,
    String? notes,
  }) async {
    final now = DateTime.now();
    final localId = _uuid.v4();
    final idempotencyKey = _uuid.v4();
    final kot = LocalKot(
      localId: localId,
      kotNumber: 'KOT-${now.millisecondsSinceEpoch}',
      businessId: businessId,
      branchId: branchId,
      staffId: staffId,
      tableNumber: tableNumber,
      orderType: orderType,
      items: items,
      notes: notes,
      status: KotStatus.pending,
      idempotencyKey: idempotencyKey,
      createdAt: now,
      updatedAt: now,
      syncStatus: 'pending',
    );
    await _kotBox.put(localId, kot.toJson());
    await _syncQueue.enqueue(
      entityType: 'kot',
      entityId: localId,
      action: 'create',
      idempotencyKey: idempotencyKey,
      payload: _kotPayload(kot),
    );
    return kot;
  }

  Future<LocalBill> convertKotToBill({
    required LocalKot kot,
    required LocalPayment payment,
    bool creditAllowed = false,
  }) async {
    final lifecycleError = BillingRules.canConvertKot(kot);
    if (lifecycleError != null) throw StateError(lifecycleError);
    final paymentError = payment.validate(
      kot.total,
      creditAllowed: creditAllowed,
    );
    if (paymentError != null) throw StateError(paymentError);

    final now = DateTime.now();
    final billId = _uuid.v4();
    final idempotencyKey = _uuid.v4();
    final subtotal = kot.items.fold<double>(
      0,
      (sum, item) => sum + item.subtotal,
    );
    final tax = kot.items.fold<double>(0, (sum, item) => sum + item.taxAmount);
    final bill = LocalBill(
      localId: billId,
      billNumber: 'BILL-${now.millisecondsSinceEpoch}',
      linkedKotLocalId: kot.localId,
      linkedKotServerId: kot.serverId,
      businessId: kot.businessId,
      branchId: kot.branchId,
      staffId: kot.staffId,
      items: kot.items,
      paymentBreakdown: payment,
      subtotal: subtotal,
      tax: tax,
      total: subtotal + tax,
      status: BillStatus.paid,
      idempotencyKey: idempotencyKey,
      createdAt: now,
      updatedAt: now,
      syncStatus: 'pending',
    );
    final convertedKot = LocalKot(
      localId: kot.localId,
      serverId: kot.serverId,
      kotNumber: kot.kotNumber,
      businessId: kot.businessId,
      branchId: kot.branchId,
      staffId: kot.staffId,
      tableNumber: kot.tableNumber,
      orderType: kot.orderType,
      items: kot.items,
      notes: kot.notes,
      status: KotStatus.convertedToBill,
      idempotencyKey: kot.idempotencyKey,
      createdAt: kot.createdAt,
      updatedAt: now,
      syncStatus: 'pending',
    );
    await _billBox.put(bill.localId, bill.toJson());
    await _kotBox.put(convertedKot.localId, convertedKot.toJson());
    await _syncQueue.enqueue(
      entityType: 'kot',
      entityId: kot.localId,
      action: 'convert',
      idempotencyKey: idempotencyKey,
      payload: {'kot': _kotPayload(convertedKot), 'bill': _billPayload(bill)},
    );
    return bill;
  }

  Future<LocalBill> createBill({
    required String businessId,
    required String branchId,
    required String staffId,
    required List<LocalKotItem> items,
    required LocalPayment payment,
    bool hold = false,
    bool creditAllowed = false,
  }) async {
    final subtotal = items.fold<double>(0, (sum, item) => sum + item.subtotal);
    final tax = items.fold<double>(0, (sum, item) => sum + item.taxAmount);
    final total = subtotal + tax;
    if (!hold) {
      final paymentError = payment.validate(
        total,
        creditAllowed: creditAllowed,
      );
      if (paymentError != null) throw StateError(paymentError);
    }

    final now = DateTime.now();
    final localId = _uuid.v4();
    final idempotencyKey = _uuid.v4();
    final bill = LocalBill(
      localId: localId,
      billNumber: '${hold ? 'HOLD' : 'BILL'}-${now.millisecondsSinceEpoch}',
      businessId: businessId,
      branchId: branchId,
      staffId: staffId,
      items: items,
      paymentBreakdown: payment,
      subtotal: subtotal,
      tax: tax,
      total: total,
      status: hold ? BillStatus.held : BillStatus.paid,
      idempotencyKey: idempotencyKey,
      createdAt: now,
      updatedAt: now,
      syncStatus: 'pending',
    );
    await _billBox.put(localId, bill.toJson());
    await _syncQueue.enqueue(
      entityType: hold ? 'held_bill' : 'bill',
      entityId: localId,
      action: 'create',
      idempotencyKey: idempotencyKey,
      payload: _billPayload(bill),
    );
    return bill;
  }

  Map<String, dynamic> _kotPayload(LocalKot kot) => {
    'id': kot.localId,
    'order_type': kot.orderType.name,
    'table_token': kot.tableNumber,
    'items': kot.items.map(_itemPayload).toList(),
    'items_json': kot.items.map(_itemPayload).toList(),
    'notes': kot.notes,
    'status': kot.status.name,
    'subtotal': kot.items.fold<double>(0, (sum, item) => sum + item.subtotal),
    'total_tax': kot.items.fold<double>(0, (sum, item) => sum + item.taxAmount),
    'total_amount': kot.total,
    'idempotency_key': kot.idempotencyKey,
    'device_id': 'staff_mobile',
  };

  Map<String, dynamic> _billPayload(LocalBill bill) => {
    'id': bill.localId,
    'bill_no': bill.billNumber,
    'bill_date': bill.createdAt.toIso8601String(),
    'bill_date_text': bill.createdAt.toLocal().toString(),
    'items': bill.items.map(_itemPayload).toList(),
    'items_json': bill.items.map(_itemPayload).toList(),
    'payment_method': 'Split',
    'payment_option': 'Split',
    'cash_amount': bill.paymentBreakdown.cash,
    'upi_amount': bill.paymentBreakdown.upi,
    'card_amount': bill.paymentBreakdown.card,
    'other_paid_amount': 0,
    'credit_amount': 0,
    'discount': 0,
    'subtotal': bill.subtotal,
    'total_tax': bill.tax,
    'total': bill.total,
    'total_cgst': bill.tax / 2,
    'total_sgst': bill.tax / 2,
    'total_igst': 0,
    'old_balance': 0,
    'is_intra_state': true,
    'status': bill.status.name,
    'idempotency_key': bill.idempotencyKey,
    'device_id': 'staff_mobile',
  };

  Map<String, dynamic> _itemPayload(LocalKotItem item) => {
    'product_id': item.productId,
    'product_name': item.name,
    'quantity': item.quantity,
    'price': item.price,
    'gst_percentage': item.taxRate,
    'subtotal': item.subtotal,
  };

  Box<dynamic> get _kotBox => _database.box(LocalDatabase.kotBox);
  Box<dynamic> get _billBox => _database.box(LocalDatabase.billBox);
}
