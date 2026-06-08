import 'package:flutter/material.dart';
import 'package:package_info_plus/package_info_plus.dart';
import 'package:provider/provider.dart';

import '../../core/config/app_config.dart';
import '../../core/network/api_client.dart';
import '../auth/auth_controller.dart';
import '../auth/invite_code_login_screen.dart';
import '../sync/sync_queue_service.dart';
import 'settings_controller.dart';

class SettingsScreen extends StatefulWidget {
  const SettingsScreen({super.key});

  @override
  State<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends State<SettingsScreen> {
  String _version = '1.0.0';

  @override
  void initState() {
    super.initState();
    PackageInfo.fromPlatform().then((info) {
      if (!mounted) return;
      setState(() => _version = '${info.version}+${info.buildNumber}');
    });
  }

  @override
  Widget build(BuildContext context) {
    final settings = context.watch<SettingsController>();
    final auth = context.watch<AuthController>();
    final profile = auth.profile;
    return Scaffold(
      appBar: AppBar(title: const Text('Settings')),
      body: SafeArea(
        child: ListView(
          padding: const EdgeInsets.all(16),
          children: [
            Card(
              child: Padding(
                padding: const EdgeInsets.all(16),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    Text(
                      'API URL',
                      style: Theme.of(context).textTheme.titleMedium?.copyWith(
                        fontWeight: FontWeight.w800,
                      ),
                    ),
                    const SizedBox(height: 12),
                    ListTile(
                      contentPadding: EdgeInsets.zero,
                      leading: const Icon(Icons.cloud_done_outlined),
                      title: Text(AppConfig.activeEnvironmentLabel),
                      subtitle: Text(settings.activeBaseUrl),
                    ),
                  ],
                ),
              ),
            ),
            const SizedBox(height: 12),
            Card(
              child: Column(
                children: [
                  ListTile(
                    leading: const Icon(Icons.storefront_outlined),
                    title: Text(profile?.businessName ?? 'Business'),
                    subtitle: Text(
                      '${profile?.staffName ?? 'Staff'} • ${profile?.role ?? 'staff'}',
                    ),
                  ),
                  ListTile(
                    leading: const Icon(Icons.sync),
                    title: const Text('Manual sync'),
                    subtitle: Text(
                      '${context.read<SyncQueueService>().pendingCount} pending / failed',
                    ),
                    onTap: () async {
                      await context.read<SyncQueueService>().flush(
                        context.read<ApiClient>(),
                      );
                      if (!context.mounted) return;
                      ScaffoldMessenger.of(context).showSnackBar(
                        const SnackBar(content: Text('Sync attempted')),
                      );
                    },
                  ),
                  ListTile(
                    leading: const Icon(Icons.info_outline),
                    title: const Text('About VRIDDHI'),
                    subtitle: Text(
                      '${AppConfig.productFamily}\nVersion $_version',
                    ),
                  ),
                  ListTile(
                    leading: const Icon(Icons.logout),
                    title: const Text('Logout'),
                    onTap: () async {
                      await context.read<AuthController>().logout();
                      if (!context.mounted) return;
                      Navigator.of(context).pushAndRemoveUntil(
                        MaterialPageRoute(
                          builder: (_) => const InviteCodeLoginScreen(),
                        ),
                        (_) => false,
                      );
                    },
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}
