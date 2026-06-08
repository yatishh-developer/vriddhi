import 'package:flutter_test/flutter_test.dart';
import 'package:vriddhi_staff_billing_app/core/models/business_sector.dart';
import 'package:vriddhi_staff_billing_app/features/auth/auth_models.dart';

void main() {
  test('auth session parses backend staff invite response', () {
    final session = AuthSession.fromJson({
      'staff_id': 'staff_1',
      'staff_name': 'Amit',
      'business_id': 'biz_1',
      'business_name': 'VRIDDHI Cafe',
      'business_type': 'Restaurant / Cafe',
      'branch_id': 'main',
      'role': 'cashier',
      'permissions': {
        'create_bill': true,
        'create_kot': true,
        'convert_kot_to_bill': true,
        'collect_payment': true,
      },
      'feature_flags': {
        'kot': true,
        'pending_kot': true,
        'table_token': true,
        'barcode_scan': false,
      },
      'access_token': 'access',
      'refresh_token': 'refresh',
    });

    expect(session.accessToken, 'access');
    expect(session.refreshToken, 'refresh');
    expect(session.profile.staffId, 'staff_1');
    expect(session.profile.businessName, 'VRIDDHI Cafe');
    expect(session.profile.sector, BusinessSector.restaurantCafe);
    expect(session.profile.permissions.canCreateKot, isTrue);
    expect(session.profile.resolvedFeatureFlags.kotEnabled, isTrue);
  });

  test('retail backend flags hide KOT and show barcode', () {
    final flags = BusinessFeatureFlags.fromJson({
      'kot': false,
      'barcode_scan': true,
      'hold_bill': true,
    });

    expect(flags.kotEnabled, isFalse);
    expect(flags.barcodeEnabled, isTrue);
    expect(flags.holdBillEnabled, isTrue);
  });
}
