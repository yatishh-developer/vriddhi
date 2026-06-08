import 'package:flutter_test/flutter_test.dart';
import 'package:hive/hive.dart';
import 'package:vriddhi_staff_billing_app/core/storage/local_database.dart';
import 'package:vriddhi_staff_billing_app/features/sync/sync_queue_service.dart';

void main() {
  setUpAll(() async {
    Hive.init('.dart_tool/test_hive_staff_billing');
    if (!Hive.isBoxOpen(LocalDatabase.syncQueueBox)) {
      await Hive.openBox<dynamic>(LocalDatabase.syncQueueBox);
    }
  });

  setUp(() async {
    await Hive.box<dynamic>(LocalDatabase.syncQueueBox).clear();
  });

  test('sync queue deduplicates idempotency keys', () async {
    final service = SyncQueueService();
    final first = await service.enqueue(
      entityType: 'kot',
      entityId: 'kot-1',
      action: 'create',
      idempotencyKey: 'same-key',
      payload: {'id': 'kot-1'},
    );
    final second = await service.enqueue(
      entityType: 'kot',
      entityId: 'kot-1',
      action: 'create',
      idempotencyKey: 'same-key',
      payload: {'id': 'kot-1'},
    );

    expect(first.id, second.id);
    expect(service.items(), hasLength(1));
  });
}
