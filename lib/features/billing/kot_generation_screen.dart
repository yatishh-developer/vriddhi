import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../auth/auth_controller.dart';
import 'billing_controller.dart';
import 'pending_kot_screen.dart';

class KotGenerationScreen extends StatelessWidget {
  const KotGenerationScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final controller = context.watch<BillingController>();
    final profile = context.watch<AuthController>().profile;
    return Scaffold(
      appBar: AppBar(title: const Text('Generate KOT')),
      body: SafeArea(
        child: ListView(
          padding: const EdgeInsets.all(16),
          children: [
            const TextField(
              decoration: InputDecoration(
                labelText: 'Table number / order token',
                prefixIcon: Icon(Icons.table_restaurant),
              ),
            ),
            const SizedBox(height: 12),
            const TextField(
              decoration: InputDecoration(
                labelText: 'Notes',
                prefixIcon: Icon(Icons.notes_outlined),
              ),
            ),
            const SizedBox(height: 16),
            for (final item in controller.cart)
              ListTile(
                title: Text(item.name),
                subtitle: Text('Qty ${item.quantity}'),
                trailing: Text('₹${item.total.toStringAsFixed(2)}'),
              ),
            const SizedBox(height: 16),
            FilledButton.icon(
              onPressed: () async {
                if (profile == null ||
                    profile.businessId.isEmpty ||
                    profile.branchId.isEmpty ||
                    profile.staffId.isEmpty) {
                  ScaffoldMessenger.of(context).showSnackBar(
                    const SnackBar(
                      content: Text(
                        'Staff profile missing. Please log in again.',
                      ),
                    ),
                  );
                  return;
                }
                await controller.createKot(
                  businessId: profile.businessId,
                  branchId: profile.branchId,
                  staffId: profile.staffId,
                );
                if (!context.mounted) return;
                Navigator.of(context).pushAndRemoveUntil(
                  MaterialPageRoute(builder: (_) => const PendingKotScreen()),
                  (route) => route.isFirst,
                );
              },
              icon: const Icon(Icons.check_circle_outline),
              label: const Text('Generate KOT'),
            ),
          ],
        ),
      ),
    );
  }
}
