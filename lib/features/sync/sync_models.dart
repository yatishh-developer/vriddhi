enum LocalSyncStatus { pending, syncing, synced, failed, conflict }

class LocalSyncQueueItem {
  LocalSyncQueueItem({
    required this.id,
    required this.idempotencyKey,
    required this.entityType,
    required this.entityId,
    required this.action,
    required this.payloadJson,
    required this.status,
    required this.retryCount,
    this.lastError,
    required this.createdAt,
    required this.updatedAt,
    this.syncedAt,
  });

  final String id;
  final String idempotencyKey;
  final String entityType;
  final String entityId;
  final String action;
  final String payloadJson;
  LocalSyncStatus status;
  int retryCount;
  String? lastError;
  final DateTime createdAt;
  DateTime updatedAt;
  DateTime? syncedAt;

  factory LocalSyncQueueItem.fromJson(Map<String, dynamic> json) {
    return LocalSyncQueueItem(
      id: json['id'] as String,
      idempotencyKey: json['idempotencyKey'] as String,
      entityType: json['entityType'] as String,
      entityId: json['entityId'] as String,
      action: json['action'] as String,
      payloadJson: json['payloadJson'] as String,
      status: LocalSyncStatus.values.firstWhere(
        (status) => status.name == json['status'],
        orElse: () => LocalSyncStatus.pending,
      ),
      retryCount: json['retryCount'] as int? ?? 0,
      lastError: json['lastError'] as String?,
      createdAt: DateTime.parse(json['createdAt'] as String),
      updatedAt: DateTime.parse(json['updatedAt'] as String),
      syncedAt: DateTime.tryParse(json['syncedAt'] as String? ?? ''),
    );
  }

  Map<String, dynamic> toJson() => {
    'id': id,
    'idempotencyKey': idempotencyKey,
    'entityType': entityType,
    'entityId': entityId,
    'action': action,
    'payloadJson': payloadJson,
    'status': status.name,
    'retryCount': retryCount,
    'lastError': lastError,
    'createdAt': createdAt.toIso8601String(),
    'updatedAt': updatedAt.toIso8601String(),
    'syncedAt': syncedAt?.toIso8601String(),
  };
}

class LocalRealtimeEvent {
  const LocalRealtimeEvent({
    required this.id,
    required this.name,
    required this.payloadJson,
    required this.receivedAt,
  });

  final String id;
  final String name;
  final String payloadJson;
  final DateTime receivedAt;
}
