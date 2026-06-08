import 'package:dio/dio.dart';

import '../../core/network/api_client.dart';
import 'auth_models.dart';

class AuthService {
  const AuthService(this._apiClient);

  final ApiClient _apiClient;

  Future<AuthSession> verifyInviteCode({
    required String inviteCode,
    String? deviceId,
  }) async {
    final response = await _apiClient.post(
      '/staff/auth/verify-invite-code',
      data: {
        'invite_code': inviteCode,
        if (deviceId != null && deviceId.isNotEmpty) 'device_id': deviceId,
      },
    );
    return AuthSession.fromJson(
      Map<String, dynamic>.from(response.data as Map),
    );
  }

  Future<AuthSession> login({
    required String loginId,
    required String password,
  }) async {
    try {
      final response = await _apiClient.post(
        '/auth/staff/login',
        data: {'loginId': loginId, 'password': password},
      );
      return AuthSession.fromJson(
        Map<String, dynamic>.from(response.data as Map),
      );
    } on DioException catch (error) {
      if (error.response?.statusCode != 404) rethrow;
      final response = await _apiClient.post(
        '/auth/login',
        data: {'username': loginId, 'password': password},
      );
      return AuthSession.fromLegacyTokenJson(
        Map<String, dynamic>.from(response.data as Map),
        loginId: loginId,
      );
    }
  }

  Future<LocalStaffProfile> me() async {
    final response = await _apiClient.get('/staff/me');
    return LocalStaffProfile.fromJson(
      Map<String, dynamic>.from(response.data as Map),
    );
  }

  Future<AuthSession?> firebaseLogin(FirebaseIdentity identity) async {
    return null;
  }

  Future<AuthSession> acceptInvite({
    required FirebaseIdentity identity,
    required String inviteCode,
  }) async {
    return verifyInviteCode(inviteCode: inviteCode, deviceId: identity.uid);
  }

  Future<AuthSession> createAccount({
    required String name,
    required String email,
    required String password,
  }) async {
    try {
      final response = await _apiClient.post(
        '/auth/staff/signup',
        data: {'name': name, 'email': email, 'password': password},
      );
      return AuthSession.fromJson(
        Map<String, dynamic>.from(response.data as Map),
      );
    } on DioException catch (error) {
      if (error.response?.statusCode != 404) rethrow;
      await _apiClient.post(
        '/auth/register',
        data: {
          'business_id': 'test_business',
          'branch_id': 'test_branch',
          'name': name,
          'phone': email,
          'email': email,
          'password': password,
          'role': 'cashier',
        },
      );
      return login(loginId: email, password: password);
    }
  }

  Future<void> forgotPassword(String loginId) =>
      _apiClient.post('/auth/forgot-password', data: {'loginId': loginId});

  Future<void> resetPassword(String token, String password) => _apiClient.post(
    '/auth/reset-password',
    data: {'token': token, 'password': password},
  );

  Future<void> logout() => _apiClient.post('/staff/auth/logout');
}
