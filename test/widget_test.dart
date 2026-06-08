import 'package:flutter_test/flutter_test.dart';
import 'package:vriddhi_staff_billing_app/core/utils/validators.dart';

void main() {
  test('login validation accepts practical staff login IDs', () {
    expect(Validators.loginId('cashier@example.com'), isNull);
    expect(Validators.loginId('9876543210'), isNull);
    expect(Validators.loginId('AB'), isNotNull);
    expect(Validators.password('short'), isNotNull);
    expect(Validators.password('staffpass1'), isNull);
  });
}
