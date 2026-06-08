import 'package:flutter_test/flutter_test.dart';
import 'package:vriddhi_staff_billing_app/core/models/business_sector.dart';
import 'package:vriddhi_staff_billing_app/features/auth/auth_models.dart';
import 'package:vriddhi_staff_billing_app/features/billing/staff_feature_gate.dart';

void main() {
  test('restaurant sector enables KOT defaults', () {
    final flags = BusinessFeatureFlags.defaultsFor(
      BusinessSector.restaurantCafe,
    );

    expect(flags.kotEnabled, isTrue);
    expect(flags.tableEnabled, isTrue);
    expect(flags.barcodeEnabled, isFalse);
  });

  test('retail sector hides KOT and enables barcode', () {
    final flags = BusinessFeatureFlags.defaultsFor(BusinessSector.retailKirana);
    final gate = StaffFeatureGate(
      flags: flags,
      permissions: const StaffPermissions(
        canCreateKot: true,
        canUseBarcode: true,
      ),
    );

    expect(gate.canShowKot, isFalse);
    expect(gate.canShowBarcode, isTrue);
  });

  test('hold bill requires flag and staff permission', () {
    final flags = BusinessFeatureFlags.defaultsFor(BusinessSector.retailKirana);

    expect(
      StaffFeatureGate(
        flags: flags,
        permissions: const StaffPermissions(canHoldBill: false),
      ).canHoldBill,
      isFalse,
    );
    expect(
      StaffFeatureGate(
        flags: flags,
        permissions: const StaffPermissions(canHoldBill: true),
      ).canHoldBill,
      isTrue,
    );
  });
}
