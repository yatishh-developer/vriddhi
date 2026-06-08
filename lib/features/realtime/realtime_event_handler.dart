import 'dart:convert';

import 'package:hive/hive.dart';

import '../../core/storage/local_database.dart';

class RealtimeEventHandler {
  RealtimeEventHandler({LocalDatabase? database})
    : _database = database ?? LocalDatabase.instance;

  final LocalDatabase _database;

  Future<bool> handle(String message) async {
    final data = jsonDecode(message);
    if (data is! Map<String, dynamic>) return false;
    final eventId = data['event_id'] as String? ?? data['eventId'] as String?;
    if (eventId == null || eventId.isEmpty) return false;
    if (_box.containsKey(eventId)) return false;
    await _box.put(eventId, {
      'id': eventId,
      'name': data['event_type'] ?? data['event'] ?? data['type'],
      'payloadJson': jsonEncode(data['payload'] ?? {}),
      'receivedAt': DateTime.now().toIso8601String(),
    });
    return true;
  }

  Box<dynamic> get _box => _database.box(LocalDatabase.realtimeEventBox);
}
