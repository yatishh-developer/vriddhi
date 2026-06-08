import 'dart:convert';

import 'package:hive/hive.dart';
import 'package:uuid/uuid.dart';

import '../../core/network/api_client.dart';
import '../../core/storage/local_database.dart';
import 'sync_models.dart';

class SyncQueueService {
  SyncQueueService({LocalDatabase? database, Uuid? uuid})
    : _database = database ?? LocalDatabase.instance,
      _uuid = uuid ?? const Uuid();

  final LocalDatabase _database;
  final Uuid _uuid;

  Future<LocalSyncQueueItem> enqueue({
    required String entityType,
    required String entityId,
    required String action,
    required Map<String, dynamic> payload,
    String? idempotencyKey,
  }) async {
    final key = idempotencyKey ?? _uuid.v4();
    final duplicate = items().where(
      (item) =>
          item.idempotencyKey == key &&
          item.status != LocalSyncStatus.synced &&
          item.status != LocalSyncStatus.conflict,
    );
    if (duplicate.isNotEmpty) return duplicate.first;

    final now = DateTime.now();
    final item = LocalSyncQueueItem(
      id: _uuid.v4(),
      idempotencyKey: key,
      entityType: entityType,
      entityId: entityId,
      action: action,
      payloadJson: jsonEncode(payload),
      status: LocalSyncStatus.pending,
      retryCount: 0,
      createdAt: now,
      updatedAt: now,
    );
    await _box.put(item.id, item.toJson());
    return item;
  }

  List<LocalSyncQueueItem> items() {
    return _box.values
        .whereType<Map>()
        .map(
          (value) =>
              LocalSyncQueueItem.fromJson(Map<String, dynamic>.from(value)),
        )
        .toList()
      ..sort((a, b) => b.createdAt.compareTo(a.createdAt));
  }

  int get pendingCount => items()
      .where(
        (item) =>
            item.status == LocalSyncStatus.pending ||
            item.status == LocalSyncStatus.failed,
      )
      .length;

  Future<void> flush(ApiClient apiClient) async {
    final pending = items()
        .where(
          (item) =>
              item.status == LocalSyncStatus.pending ||
              item.status == LocalSyncStatus.failed,
        )
        .toList();
    for (final item in pending) {
      await _syncOne(apiClient, item);
    }
  }

  Future<void> _syncOne(ApiClient apiClient, LocalSyncQueueItem item) async {
    item.status = LocalSyncStatus.syncing;
    item.updatedAt = DateTime.now();
    await _box.put(item.id, item.toJson());
    try {
      final payload = Map<String, dynamic>.from(
        jsonDecode(item.payloadJson) as Map,
      );
      await _postForItem(apiClient, item, payload);
      item.status = LocalSyncStatus.synced;
      item.syncedAt = DateTime.now();
      item.lastError = null;
    } catch (error) {
      item.status = LocalSyncStatus.failed;
      item.retryCount += 1;
      item.lastError = error.toString();
    } finally {
      item.updatedAt = DateTime.now();
      await _box.put(item.id, item.toJson());
    }
  }

  Future<void> _postForItem(
    ApiClient apiClient,
    LocalSyncQueueItem item,
    Map<String, dynamic> payload,
  ) async {
    if (item.entityType == 'kot' && item.action == 'create') {
      await apiClient.post('/staff/kots', data: payload);
      return;
    }
    if (item.entityType == 'kot' && item.action == 'convert') {
      final kot = Map<String, dynamic>.from(payload['kot'] as Map);
      final bill = Map<String, dynamic>.from(payload['bill'] as Map);
      await apiClient.post(
        '/staff/kots/${kot['id']}/convert-to-bill',
        data: bill,
      );
      return;
    }
    if (item.entityType == 'bill' && item.action == 'create') {
      await apiClient.post('/staff/bills', data: payload);
      return;
    }
    if (item.entityType == 'held_bill' && item.action == 'create') {
      await apiClient.post('/staff/held-bills', data: payload);
      return;
    }
    throw StateError(
      'Unsupported sync item: ${item.entityType}/${item.action}',
    );
  }

  Box<dynamic> get _box => _database.box(LocalDatabase.syncQueueBox);
}
