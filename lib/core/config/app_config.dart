class AppConfig {
  const AppConfig._();

  static const brandName = 'VRIDDHI';
  static const ecosystem = 'VABOS';
  static const appName = 'VRIDDHI Staff Billing';
  static const productFamily = 'Vriddhi AI Billing Operating System';

  static const productionBaseUrl = 'https://vriddhi-p7ax.onrender.com';
  static const apiBaseUrl = String.fromEnvironment(
    'VABOS_API_BASE_URL',
    defaultValue: productionBaseUrl,
  );
  static const websocketBaseUrl = String.fromEnvironment(
    'VABOS_WEBSOCKET_BASE_URL',
    defaultValue: '',
  );
  static const enableFirebaseAuth = bool.fromEnvironment(
    'ENABLE_FIREBASE_AUTH',
    defaultValue: true,
  );
  static const firebaseApiKey = String.fromEnvironment('FIREBASE_API_KEY');
  static const firebaseAppId = String.fromEnvironment('FIREBASE_APP_ID');
  static const firebaseMessagingSenderId = String.fromEnvironment(
    'FIREBASE_MESSAGING_SENDER_ID',
  );
  static const firebaseProjectId = String.fromEnvironment(
    'FIREBASE_PROJECT_ID',
  );
  static const firebaseAuthDomain = String.fromEnvironment(
    'FIREBASE_AUTH_DOMAIN',
  );
  static const firebaseStorageBucket = String.fromEnvironment(
    'FIREBASE_STORAGE_BUCKET',
  );
  static const activeEnvironment = 'production';

  static String websocketBaseUrlFor(String restBaseUrl) {
    if (websocketBaseUrl.isNotEmpty) return websocketBaseUrl;
    return restBaseUrl
        .replaceFirst('https://', 'wss://')
        .replaceFirst('http://', 'ws://');
  }

  static String get activeBaseUrl => apiBaseUrl;
  static String get activeEnvironmentLabel => 'Production';

  static bool get hasFirebaseOptions {
    return firebaseApiKey.isNotEmpty &&
        firebaseAppId.isNotEmpty &&
        firebaseMessagingSenderId.isNotEmpty &&
        firebaseProjectId.isNotEmpty &&
        firebaseAuthDomain.isNotEmpty;
  }
}
