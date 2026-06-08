import 'dart:async';
import 'dart:convert';

import 'package:flutter/foundation.dart';
import 'package:web_socket_channel/web_socket_channel.dart';

import '../../core/config/app_config.dart';
import '../../core/network/api_client.dart';
import '../../core/storage/secure_token_storage.dart';
import 'realtime_event_handler.dart';

enum WebSocketStatus { disconnected, connecting, connected, fallback }

class WebSocketService extends ChangeNotifier {
  WebSocketService({
    required ApiClient apiClient,
    required SecureTokenStorage tokenStorage,
    RealtimeEventHandler? handler,
  }) : _apiClient = apiClient,
       _tokenStorage = tokenStorage,
       _handler = handler ?? RealtimeEventHandler();

  final ApiClient _apiClient;
  final SecureTokenStorage _tokenStorage;
  final RealtimeEventHandler _handler;

  WebSocketChannel? _channel;
  Timer? _heartbeat;
  int _attempt = 0;

  WebSocketStatus status = WebSocketStatus.disconnected;

  Future<void> connect({
    required String businessId,
    required String branchId,
    String? counterId,
  }) async {
    final token = await _tokenStorage.readAccessToken();
    if (token == null || token.isEmpty) return;
    status = WebSocketStatus.connecting;
    notifyListeners();
    try {
      final wsBase = AppConfig.websocketBaseUrlFor(_apiClient.baseUrl);
      final query = Uri(
        queryParameters: {
          'token': token,
          'business_id': businessId,
          'branch_id': branchId,
          if (counterId != null && counterId.isNotEmpty) 'device_id': counterId,
        },
      ).query;
      _channel = WebSocketChannel.connect(Uri.parse('$wsBase/ws/staff?$query'));
      status = WebSocketStatus.connected;
      _attempt = 0;
      _heartbeat = Timer.periodic(const Duration(seconds: 25), (_) {
        _channel?.sink.add(jsonEncode({'type': 'ping'}));
      });
      _channel!.stream.listen(
        (message) => _handler.handle(message as String),
        onDone: _fallbackReconnect,
        onError: (_) => _fallbackReconnect(),
      );
      notifyListeners();
    } catch (_) {
      _fallbackReconnect();
    }
  }

  void _fallbackReconnect() {
    _heartbeat?.cancel();
    status = WebSocketStatus.fallback;
    notifyListeners();
    final delay = Duration(seconds: (2 << _attempt).clamp(2, 60));
    _attempt = (_attempt + 1).clamp(0, 5);
    Timer(delay, () {});
  }

  void disconnect() {
    _heartbeat?.cancel();
    _channel?.sink.close();
    status = WebSocketStatus.disconnected;
  }

  void send(Map<String, dynamic> event) {
    if (status != WebSocketStatus.connected || _channel == null) return;
    _channel!.sink.add(jsonEncode(event));
  }

  @override
  void dispose() {
    disconnect();
    super.dispose();
  }
}
