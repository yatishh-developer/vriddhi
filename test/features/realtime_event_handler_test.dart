import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:hive/hive.dart';
import 'package:vriddhi_staff_billing_app/core/storage/local_database.dart';
import 'package:vriddhi_staff_billing_app/features/realtime/realtime_event_handler.dart';

void main() {
  setUpAll(() async {
    Hive.init('.dart_tool/test_hive_staff_billing_realtime');
    if (!Hive.isBoxOpen(LocalDatabase.realtimeEventBox)) {
      await Hive.openBox<dynamic>(LocalDatabase.realtimeEventBox);
    }
  });

  setUp(() async {
    await Hive.box<dynamic>(LocalDatabase.realtimeEventBox).clear();
  });

  test('realtime handler ignores duplicate events', () async {
    final handler = RealtimeEventHandler();
    final message = jsonEncode({
      'eventId': 'evt-1',
      'event': 'menu.updated',
      'payload': {'syncVersion': 2},
    });

    expect(await handler.handle(message), isTrue);
    expect(await handler.handle(message), isFalse);
  });
}
