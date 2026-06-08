import 'package:flutter_test/flutter_test.dart';
import 'package:vriddhi_staff_billing_app/features/billing/billing_models.dart';

void main() {
  LocalKot kot(KotStatus status) {
    return LocalKot(
      localId: 'kot-local',
      kotNumber: 'KOT-1',
      businessId: 'biz',
      branchId: 'branch',
      staffId: 'staff',
      orderType: OrderType.dineIn,
      items: const [
        LocalKotItem(
          productId: 'tea',
          name: 'Tea',
          quantity: 2,
          price: 20,
          taxRate: 0,
        ),
      ],
      status: status,
      idempotencyKey: 'key',
      createdAt: DateTime(2026, 6, 6),
      updatedAt: DateTime(2026, 6, 6),
      syncStatus: 'pending',
    );
  }

  test('KOT cannot convert twice', () {
    expect(
      BillingRules.canConvertKot(kot(KotStatus.convertedToBill)),
      'KOT is already converted to a bill.',
    );
  });

  test('cancelled KOT cannot convert', () {
    expect(
      BillingRules.canConvertKot(kot(KotStatus.cancelled)),
      'Cancelled KOT cannot be converted.',
    );
  });

  test('payment validation blocks negative and underpaid values', () {
    expect(
      const LocalPayment(cash: -1).validate(10),
      'Payment cannot be negative.',
    );
    expect(
      const LocalPayment(cash: 5).validate(10),
      'Paid amount is less than total.',
    );
    expect(const LocalPayment(cash: 12).validate(10), isNull);
    expect(const LocalPayment(cash: 12).changeFor(10), 2);
  });
}
