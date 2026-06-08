import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../core/network/api_client.dart';
import '../settings/settings_controller.dart';
import 'sync_queue_service.dart';

class SyncStatusScreen extends StatelessWidget {
  const SyncStatusScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final sync = context.read<SyncQueueService>();
    final items = sync.items();
    final settings = context.watch<SettingsController>();
    return Scaffold(
      appBar: AppBar(title: const Text('Sync status')),
      body: SafeArea(
        child: ListView(
          padding: const EdgeInsets.all(16),
          children: [
            Card(
              child: ListTile(
                leading: const Icon(Icons.link),
                title: const Text('Current API URL'),
                subtitle: Text(settings.activeBaseUrl),
              ),
            ),
            const SizedBox(height: 12),
            Card(
              child: ListTile(
                leading: const Icon(Icons.sync),
                title: Text('${sync.pendingCount} pending / failed'),
                subtitle: const Text(
                  'Sync pending KOTs, bills, and held bills.',
                ),
                trailing: IconButton(
                  tooltip: 'Sync now',
                  onPressed: () async {
                    await sync.flush(context.read<ApiClient>());
                    if (!context.mounted) return;
                    ScaffoldMessenger.of(context).showSnackBar(
                      const SnackBar(content: Text('Sync attempted')),
                    );
                  },
                  icon: const Icon(Icons.refresh),
                ),
              ),
            ),
            const SizedBox(height: 12),
            if (items.isEmpty)
              const Card(
                child: Padding(
                  padding: EdgeInsets.all(16),
                  child: Text('No queued offline actions.'),
                ),
              )
            else
              for (final item in items)
                Card(
                  child: ListTile(
                    title: Text('${item.entityType} ${item.action}'),
                    subtitle: Text(item.status.name),
                    trailing: Text('${item.retryCount} retries'),
                  ),
                ),
          ],
        ),
      ),
    );
  }
}
