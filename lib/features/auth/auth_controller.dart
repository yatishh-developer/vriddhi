import 'package:flutter/foundation.dart';
import 'package:dio/dio.dart';

import '../../core/storage/secure_token_storage.dart';
import 'auth_models.dart';
import 'auth_service.dart';
import 'firebase_auth_service.dart';

class AuthController extends ChangeNotifier {
  AuthController(this._authService, this._tokenStorage, this._firebaseAuth);

  final AuthService _authService;
  final SecureTokenStorage _tokenStorage;
  final FirebaseAuthService _firebaseAuth;

  bool isBootstrapping = true;
  bool isAuthenticated = false;
  bool isLoading = false;
  String? errorMessage;
  LocalStaffProfile? profile;
  FirebaseIdentity? pendingFirebaseIdentity;

  Future<void> bootstrap() async {
    final token = await _tokenStorage.readAccessToken();
    isAuthenticated = token != null && token.isNotEmpty;
    profile = await _tokenStorage.readStaffProfile();
    isBootstrapping = false;
    notifyListeners();
  }

  Future<bool> login(String loginId, String password) async {
    return _completeAuthAction(
      () => _authService.login(loginId: loginId, password: password),
      fallbackMessage:
          'Login failed. Check credentials, backend URL, or network connection.',
    );
  }

  Future<bool> verifyInviteCode(String inviteCode) async {
    final trimmed = inviteCode.trim();
    if (!RegExp(r'^\d{6}(\d{2})?$').hasMatch(trimmed)) {
      errorMessage = 'Enter the 6 or 8 digit invite code from admin.';
      notifyListeners();
      return false;
    }
    return _completeAuthAction(
      () => _authService.verifyInviteCode(
        inviteCode: trimmed,
        deviceId: 'staff_mobile',
      ),
      fallbackMessage: 'Invite code is invalid, expired, revoked, or used.',
    );
  }

  Future<bool> createAccount({
    required String name,
    required String email,
    required String password,
  }) async {
    return _completeAuthAction(
      () => _authService.createAccount(
        name: name,
        email: email,
        password: password,
      ),
      fallbackMessage:
          'Create account failed. Check backend database and routes.',
    );
  }

  Future<bool> signInWithGoogle() async {
    return _completeFirebaseAction(
      _firebaseAuth.signInWithGoogleIdentity,
      fallbackMessage: 'Google sign-in failed. Check Firebase configuration.',
    );
  }

  Future<bool> signInWithApple() async {
    return _completeFirebaseAction(
      _firebaseAuth.signInWithAppleIdentity,
      fallbackMessage: 'Apple sign-in failed. Check Firebase configuration.',
    );
  }

  Future<bool> acceptInvite(String inviteCode) async {
    final identity = pendingFirebaseIdentity;
    if (identity == null) {
      return verifyInviteCode(inviteCode);
    }
    return _completeAuthAction(
      () => _authService.acceptInvite(
        identity: identity,
        inviteCode: inviteCode.trim(),
      ),
      fallbackMessage: 'Invite code is invalid, expired, or already used.',
    );
  }

  Future<bool> sendPhoneOtp(String phoneNumber) async {
    isLoading = true;
    errorMessage = null;
    notifyListeners();
    try {
      await _firebaseAuth.sendPhoneOtp(phoneNumber);
      return true;
    } catch (error) {
      errorMessage = _messageFrom(
        error,
        'OTP send failed. Check Firebase configuration.',
      );
      return false;
    } finally {
      isLoading = false;
      notifyListeners();
    }
  }

  Future<bool> verifyPhoneOtp(String smsCode) async {
    return _completeAuthAction(
      () => _firebaseAuth.verifyPhoneOtp(smsCode),
      fallbackMessage: 'OTP verification failed.',
    );
  }

  Future<void> logout() async {
    try {
      await _authService.logout();
    } catch (_) {
      // The session is cleared locally even if the network is unavailable.
    }
    await _tokenStorage.clear();
    isAuthenticated = false;
    profile = null;
    pendingFirebaseIdentity = null;
    notifyListeners();
  }

  Future<bool> _completeFirebaseAction(
    Future<FirebaseIdentity> Function() action, {
    required String fallbackMessage,
  }) async {
    isLoading = true;
    errorMessage = null;
    pendingFirebaseIdentity = null;
    notifyListeners();
    try {
      final identity = await action();
      pendingFirebaseIdentity = identity;
      final session = await _authService.firebaseLogin(identity);
      if (session == null) {
        isAuthenticated = false;
        return true;
      }
      await _tokenStorage.saveSession(session);
      profile = session.profile;
      pendingFirebaseIdentity = null;
      isAuthenticated = true;
      return true;
    } catch (error) {
      errorMessage = _messageFrom(error, fallbackMessage);
      return false;
    } finally {
      isLoading = false;
      notifyListeners();
    }
  }

  Future<bool> _completeAuthAction(
    Future<AuthSession> Function() action, {
    required String fallbackMessage,
  }) async {
    isLoading = true;
    errorMessage = null;
    notifyListeners();
    try {
      final session = await action();
      await _tokenStorage.saveSession(session);
      profile = session.profile;
      pendingFirebaseIdentity = null;
      isAuthenticated = true;
      return true;
    } catch (error) {
      errorMessage = _messageFrom(error, fallbackMessage);
      return false;
    } finally {
      isLoading = false;
      notifyListeners();
    }
  }

  String _messageFrom(Object error, String fallbackMessage) {
    if (error is DioException) {
      final statusCode = error.response?.statusCode;
      final serverMessage = _serverMessage(error.response?.data);
      if (statusCode == 401) {
        return serverMessage ?? 'Login expired. Ask admin for a new code.';
      }
      if (statusCode == 400) {
        return serverMessage ??
            'Invite code is invalid, expired, revoked, or used.';
      }
      if (statusCode == 404) {
        return 'Backend route is missing. Redeploy the latest backend.';
      }
      if (statusCode == 409) {
        return serverMessage ?? 'Account already exists.';
      }
      if (statusCode == 422) {
        return serverMessage ?? 'Enter a valid 6 or 8 digit invite code.';
      }
      if (statusCode != null && statusCode >= 500) {
        return 'Backend server error. Check database configuration on Render.';
      }
      if (error.type == DioExceptionType.connectionError) {
        return 'Cannot reach backend. Check the live API URL and network.';
      }
    }
    final text = error.toString();
    if (text.startsWith('Bad state: ')) {
      return text.replaceFirst('Bad state: ', '');
    }
    return fallbackMessage;
  }

  String? _serverMessage(Object? data) {
    if (data is Map<String, dynamic>) {
      final value = data['detail'] ?? data['message'] ?? data['error'];
      if (value is String && value.trim().isNotEmpty) return value;
    }
    return null;
  }
}
