import 'package:firebase_auth/firebase_auth.dart';
import 'package:firebase_core/firebase_core.dart';

import '../../core/config/app_config.dart';
import '../../firebase_options.dart';
import 'auth_models.dart';

class FirebaseAuthService {
  FirebaseAuthService();

  String? _verificationId;

  Future<AuthSession> createAccount({
    required String name,
    required String email,
    required String password,
  }) async {
    await _ensureFirebase();
    final credential = await FirebaseAuth.instance
        .createUserWithEmailAndPassword(email: email, password: password);
    await credential.user?.updateDisplayName(name);
    return _sessionFromFirebaseUser(credential.user, fallbackName: name);
  }

  Future<AuthSession> signInWithGoogle() async {
    final identity = await signInWithGoogleIdentity();
    return _sessionFromIdentity(identity);
  }

  Future<FirebaseIdentity> signInWithGoogleIdentity() async {
    await _ensureFirebase();
    final provider = GoogleAuthProvider()..addScope('email');
    final credential = await FirebaseAuth.instance.signInWithProvider(provider);
    return _identityFromFirebaseUser(credential.user, provider: 'google');
  }

  Future<AuthSession> signInWithApple() async {
    final identity = await signInWithAppleIdentity();
    return _sessionFromIdentity(identity);
  }

  Future<FirebaseIdentity> signInWithAppleIdentity() async {
    await _ensureFirebase();
    final provider = AppleAuthProvider()
      ..addScope('email')
      ..addScope('name');
    final credential = await FirebaseAuth.instance.signInWithProvider(provider);
    return _identityFromFirebaseUser(credential.user, provider: 'apple');
  }

  Future<void> sendPhoneOtp(String phoneNumber) async {
    await _ensureFirebase();
    await FirebaseAuth.instance.verifyPhoneNumber(
      phoneNumber: phoneNumber,
      verificationCompleted: (_) {},
      verificationFailed: (error) {
        throw FirebaseAuthException(code: error.code, message: error.message);
      },
      codeSent: (verificationId, _) {
        _verificationId = verificationId;
      },
      codeAutoRetrievalTimeout: (verificationId) {
        _verificationId = verificationId;
      },
    );
  }

  Future<AuthSession> verifyPhoneOtp(String smsCode) async {
    await _ensureFirebase();
    final verificationId = _verificationId;
    if (verificationId == null || verificationId.isEmpty) {
      throw FirebaseAuthException(
        code: 'missing-verification-id',
        message: 'Send OTP before verifying.',
      );
    }
    final credential = PhoneAuthProvider.credential(
      verificationId: verificationId,
      smsCode: smsCode,
    );
    final userCredential = await FirebaseAuth.instance.signInWithCredential(
      credential,
    );
    return _sessionFromFirebaseUser(userCredential.user);
  }

  Future<void> _ensureFirebase() async {
    if (Firebase.apps.isNotEmpty) return;
    try {
      if (AppConfig.hasFirebaseOptions) {
        await Firebase.initializeApp(
          options: const FirebaseOptions(
            apiKey: AppConfig.firebaseApiKey,
            appId: AppConfig.firebaseAppId,
            messagingSenderId: AppConfig.firebaseMessagingSenderId,
            projectId: AppConfig.firebaseProjectId,
            authDomain: AppConfig.firebaseAuthDomain,
            storageBucket: AppConfig.firebaseStorageBucket,
          ),
        );
      } else {
        await Firebase.initializeApp(
          options: DefaultFirebaseOptions.currentPlatform,
        );
      }
    } catch (_) {
      throw StateError(
        'Firebase is not configured. Add Firebase files or build with FIREBASE_API_KEY, FIREBASE_APP_ID, FIREBASE_MESSAGING_SENDER_ID, and FIREBASE_PROJECT_ID.',
      );
    }
  }

  Future<AuthSession> _sessionFromFirebaseUser(
    User? user, {
    String? fallbackName,
  }) async {
    if (user == null) {
      throw StateError('Firebase sign-in did not return a user.');
    }
    final token = await user.getIdToken();
    return AuthSession(
      accessToken: token ?? 'firebase-access-token',
      refreshToken: user.refreshToken ?? 'firebase-refresh-token',
      profile: LocalStaffProfile(
        staffId: user.uid,
        staffName: user.displayName ?? fallbackName ?? 'Firebase Staff',
        businessId: 'firebase_business',
        branchId: 'firebase_branch',
        role: 'staff',
        permissions: const StaffPermissions(
          canCreateKot: true,
          canConvertKotToBill: true,
          canCollectPayment: true,
          canPrintBill: true,
        ),
      ),
    );
  }

  Future<FirebaseIdentity> _identityFromFirebaseUser(
    User? user, {
    required String provider,
  }) async {
    if (user == null) {
      throw StateError('Firebase sign-in did not return a user.');
    }
    final token = await user.getIdToken();
    return FirebaseIdentity(
      idToken: token ?? '',
      uid: user.uid,
      email: user.email ?? '',
      displayName: user.displayName ?? 'Firebase Staff',
      provider: provider,
    );
  }

  AuthSession _sessionFromIdentity(FirebaseIdentity identity) {
    return AuthSession(
      accessToken: identity.idToken,
      refreshToken: identity.idToken,
      profile: LocalStaffProfile(
        staffId: identity.uid,
        staffName: identity.displayName,
        businessId: '',
        branchId: '',
        role: 'staff',
        permissions: const StaffPermissions(),
      ),
    );
  }
}
