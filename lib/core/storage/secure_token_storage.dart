import 'dart:convert';

import 'package:flutter_secure_storage/flutter_secure_storage.dart';

import '../../features/auth/auth_models.dart';

class SecureTokenStorage {
  const SecureTokenStorage({FlutterSecureStorage? storage})
    : _storage = storage ?? const FlutterSecureStorage();

  final FlutterSecureStorage _storage;

  Future<String?> readAccessToken() => _storage.read(key: 'access_token');

  Future<String?> readRefreshToken() => _storage.read(key: 'refresh_token');

  Future<LocalStaffProfile?> readStaffProfile() async {
    final value = await _storage.read(key: 'staff_profile');
    if (value == null || value.isEmpty) return null;
    return LocalStaffProfile.fromJson(
      Map<String, dynamic>.from(jsonDecode(value) as Map),
    );
  }

  Future<void> saveTokens(String accessToken, String refreshToken) async {
    await _storage.write(key: 'access_token', value: accessToken);
    await _storage.write(key: 'refresh_token', value: refreshToken);
  }

  Future<void> saveSession(AuthSession session) async {
    await saveTokens(session.accessToken, session.refreshToken);
    await _storage.write(
      key: 'staff_profile',
      value: jsonEncode(session.profile.toJson()),
    );
  }

  Future<void> clear() async {
    await _storage.delete(key: 'access_token');
    await _storage.delete(key: 'refresh_token');
    await _storage.delete(key: 'staff_profile');
  }
}
