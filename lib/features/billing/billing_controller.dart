import 'package:flutter/foundation.dart';

import '../menu/menu_models.dart';
import 'billing_models.dart';
import 'billing_repository.dart';

class BillingController extends ChangeNotifier {
  BillingController.empty();

  BillingRepository? _repository;
  final List<LocalKotItem> cart = [];
  String? lastError;

  void attach(BillingRepository repository) {
    _repository = repository;
  }

  List<LocalKot> get pendingKots =>
      _repository
          ?.kots()
          .where(
            (kot) =>
                kot.status != KotStatus.convertedToBill &&
                kot.status != KotStatus.cancelled,
          )
          .toList() ??
      [];

  List<LocalBill> get bills => _repository?.bills() ?? [];
  List<LocalBill> get heldBills =>
      bills.where((bill) => bill.status == BillStatus.held).toList();

  double get subtotal =>
      cart.fold<double>(0, (sum, item) => sum + item.subtotal);
  double get tax => cart.fold<double>(0, (sum, item) => sum + item.taxAmount);
  double get total => subtotal + tax;

  void addProduct(LocalProduct product) {
    final index = cart.indexWhere((item) => item.productId == product.id);
    if (index == -1) {
      cart.add(LocalKotItem.fromProduct(product, 1));
    } else {
      final existing = cart[index];
      cart[index] = LocalKotItem(
        productId: existing.productId,
        name: existing.name,
        quantity: existing.quantity + 1,
        price: existing.price,
        taxRate: existing.taxRate,
        notes: existing.notes,
      );
    }
    notifyListeners();
  }

  void decrement(String productId) {
    final index = cart.indexWhere((item) => item.productId == productId);
    if (index == -1) return;
    final existing = cart[index];
    if (existing.quantity <= 1) {
      cart.removeAt(index);
    } else {
      cart[index] = LocalKotItem(
        productId: existing.productId,
        name: existing.name,
        quantity: existing.quantity - 1,
        price: existing.price,
        taxRate: existing.taxRate,
        notes: existing.notes,
      );
    }
    notifyListeners();
  }

  void remove(String productId) {
    cart.removeWhere((item) => item.productId == productId);
    notifyListeners();
  }

  void clearCart() {
    cart.clear();
    notifyListeners();
  }

  Future<void> createKot({
    required String businessId,
    required String branchId,
    required String staffId,
  }) async {
    final repository = _repository;
    if (repository == null || cart.isEmpty) return;
    await repository.createKot(
      businessId: businessId,
      branchId: branchId,
      staffId: staffId,
      orderType: OrderType.dineIn,
      items: List<LocalKotItem>.from(cart),
    );
    clearCart();
  }

  Future<void> createBill({
    required String businessId,
    required String branchId,
    required String staffId,
    required LocalPayment payment,
    bool hold = false,
  }) async {
    final repository = _repository;
    if (repository == null || cart.isEmpty) return;
    lastError = null;
    try {
      await repository.createBill(
        businessId: businessId,
        branchId: branchId,
        staffId: staffId,
        items: List<LocalKotItem>.from(cart),
        payment: payment,
        hold: hold,
      );
      clearCart();
    } on StateError catch (error) {
      lastError = error.message;
      notifyListeners();
    }
  }

  Future<void> convertKot(LocalKot kot) async {
    final repository = _repository;
    if (repository == null) return;
    lastError = null;
    try {
      await repository.convertKotToBill(
        kot: kot,
        payment: LocalPayment(cash: kot.total),
      );
    } on StateError catch (error) {
      lastError = error.message;
    }
    notifyListeners();
  }
}
