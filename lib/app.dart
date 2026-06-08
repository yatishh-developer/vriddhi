import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import 'core/network/api_client.dart';
import 'core/storage/secure_token_storage.dart';
import 'core/theme/app_theme.dart';
import 'features/auth/auth_controller.dart';
import 'features/auth/auth_service.dart';
import 'features/auth/firebase_auth_service.dart';
import 'features/auth/splash_screen.dart';
import 'features/billing/billing_controller.dart';
import 'features/billing/billing_repository.dart';
import 'features/billing/process_lock_service.dart';
import 'features/menu/menu_repository.dart';
import 'features/realtime/websocket_service.dart';
import 'features/settings/settings_controller.dart';
import 'features/sync/sync_queue_service.dart';

class VriddhiStaffBillingApp extends StatelessWidget {
  const VriddhiStaffBillingApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MultiProvider(
      providers: [
        ChangeNotifierProvider(create: (_) => SettingsController()..load()),
        Provider(create: (_) => const SecureTokenStorage()),
        ProxyProvider2<SettingsController, SecureTokenStorage, ApiClient>(
          update: (_, settings, tokenStorage, previous) {
            previous?.dispose();
            return ApiClient(
              baseUrl: settings.activeBaseUrl,
              tokenStorage: tokenStorage,
            );
          },
        ),
        ProxyProvider<ApiClient, AuthService>(
          update: (_, apiClient, previous) => AuthService(apiClient),
        ),
        Provider(create: (_) => FirebaseAuthService()),
        ChangeNotifierProxyProvider3<
          AuthService,
          SecureTokenStorage,
          FirebaseAuthService,
          AuthController
        >(
          create: (context) => AuthController(
            context.read<AuthService>(),
            context.read<SecureTokenStorage>(),
            context.read<FirebaseAuthService>(),
          )..bootstrap(),
          update: (_, authService, tokenStorage, firebaseAuth, previous) =>
              previous ??
                    AuthController(authService, tokenStorage, firebaseAuth)
                ..bootstrap(),
        ),
        Provider(create: (_) => SyncQueueService()),
        ProxyProvider<ApiClient, MenuRepository>(
          update: (_, apiClient, previous) => MenuRepository(apiClient),
        ),
        ProxyProvider<SyncQueueService, BillingRepository>(
          update: (_, syncQueue, previous) => BillingRepository(syncQueue),
        ),
        ProxyProvider<ApiClient, ProcessLockService>(
          update: (_, apiClient, previous) {
            previous?.dispose();
            return ProcessLockService(apiClient);
          },
        ),
        ChangeNotifierProxyProvider<BillingRepository, BillingController>(
          create: (_) => BillingController.empty(),
          update: (_, repository, previous) =>
              (previous ?? BillingController.empty())..attach(repository),
        ),
        ProxyProvider2<ApiClient, SecureTokenStorage, WebSocketService>(
          update: (_, apiClient, tokenStorage, previous) {
            previous?.dispose();
            return WebSocketService(
              apiClient: apiClient,
              tokenStorage: tokenStorage,
            );
          },
        ),
      ],
      child: MaterialApp(
        debugShowCheckedModeBanner: false,
        title: 'VRIDDHI Staff Billing',
        theme: AppTheme.light,
        home: const SplashScreen(),
      ),
    );
  }
}
