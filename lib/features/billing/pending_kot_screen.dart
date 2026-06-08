import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import 'billing_controller.dart';
import 'kot_detail_screen.dart';

class PendingKotScreen extends StatelessWidget {
  const PendingKotScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final kots = context.watch<BillingController>().pendingKots;
    return Scaffold(
      appBar: AppBar(title: const Text('Pending KOTs')),
      body: SafeArea(
        child: ListView(
          padding: const EdgeInsets.all(16),
          children: [
            SegmentedButton<String>(
              segments: const [
                ButtonSegment(value: 'all', label: Text('All')),
                ButtonSegment(value: 'mine', label: Text('My KOTs')),
                ButtonSegment(value: 'table', label: Text('Table')),
              ],
              selected: {'all'},
            ),
            const SizedBox(height: 12),
            if (kots.isEmpty)
              const Card(
                child: Padding(
                  padding: EdgeInsets.all(16),
                  child: Text('No pending KOTs.'),
                ),
              )
            else
              for (final kot in kots)
                Card(
                  child: ListTile(
                    leading: const Icon(Icons.receipt_long),
                    title: Text(kot.kotNumber),
                    subtitle: Text(
                      '${kot.status.name} • ₹${kot.total.toStringAsFixed(2)}',
                    ),
                    trailing: const Icon(Icons.chevron_right),
                    onTap: () => Navigator.of(context).push(
                      MaterialPageRoute(
                        builder: (_) => KotDetailScreen(kot: kot),
                      ),
                    ),
                  ),
                ),
          ],
        ),
      ),
    );
  }
}
