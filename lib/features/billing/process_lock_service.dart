import 'dart:async';

import '../../core/network/api_client.dart';

class ProcessLockService {
  ProcessLockService(this._apiClient);

  final ApiClient _apiClient;
  Timer? _heartbeat;
  String? _activeProcessId;

  Future<Map<String, dynamic>> claim({
    required String processType,
    required String entityId,
    int ttlSeconds = 120,
  }) async {
    final response = await _apiClient.post(
      '/staff/processes/claim',
      data: {
        'process_type': processType,
        'entity_id': entityId,
        'ttl_seconds': ttlSeconds,
      },
    );
    final data = Map<String, dynamic>.from(response.data as Map);
    _activeProcessId = data['process_id']?.toString();
    _heartbeat?.cancel();
    _heartbeat = Timer.periodic(const Duration(seconds: 30), (_) {
      final id = _activeProcessId;
      if (id == null) return;
      heartbeat(id);
    });
    return data;
  }

  Future<void> heartbeat(String processId, {int ttlSeconds = 120}) async {
    await _apiClient.post(
      '/staff/processes/heartbeat',
      data: {'process_id': processId, 'ttl_seconds': ttlSeconds},
    );
  }

  Future<void> release(String processId, {String status = 'released'}) async {
    _heartbeat?.cancel();
    _activeProcessId = null;
    await _apiClient.post(
      '/staff/processes/release',
      data: {'process_id': processId, 'status': status},
    );
  }

  Future<List<Map<String, dynamic>>> active() async {
    final response = await _apiClient.get('/staff/processes/active');
    return (response.data as List)
        .whereType<Map>()
        .map((item) => Map<String, dynamic>.from(item))
        .toList();
  }

  void dispose() {
    _heartbeat?.cancel();
  }
}
