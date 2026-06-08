import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import 'billing_controller.dart';
import 'billing_models.dart';
import 'bill_history_screen.dart';

class ConvertKotToBillScreen extends StatelessWidget {
  const ConvertKotToBillScreen({super.key, required this.kot});

  final LocalKot kot;

  @override
  Widget build(BuildContext context) {
    final controller = context.watch<BillingController>();
    return Scaffold(
      appBar: AppBar(title: const Text('Convert KOT to bill')),
      body: SafeArea(
        child: ListView(
          padding: const EdgeInsets.all(16),
          children: [
            Text(
              'Total: ₹${kot.total.toStringAsFixed(2)}',
              style: Theme.of(
                context,
              ).textTheme.headlineSmall?.copyWith(fontWeight: FontWeight.w900),
            ),
            const SizedBox(height: 12),
            const TextField(
              decoration: InputDecoration(
                labelText: 'Cash',
                prefixIcon: Icon(Icons.payments_outlined),
              ),
              keyboardType: TextInputType.number,
            ),
            const SizedBox(height: 12),
            const TextField(
              decoration: InputDecoration(
                labelText: 'UPI',
                prefixIcon: Icon(Icons.qr_code_2),
              ),
              keyboardType: TextInputType.number,
            ),
            const SizedBox(height: 12),
            const TextField(
              decoration: InputDecoration(
                labelText: 'Card',
                prefixIcon: Icon(Icons.credit_card),
              ),
              keyboardType: TextInputType.number,
            ),
            if (controller.lastError != null) ...[
              const SizedBox(height: 12),
              Text(
                controller.lastError!,
                style: TextStyle(color: Theme.of(context).colorScheme.error),
              ),
            ],
            const SizedBox(height: 16),
            FilledButton.icon(
              onPressed: () async {
                await controller.convertKot(kot);
                if (!context.mounted || controller.lastError != null) return;
                Navigator.of(context).pushAndRemoveUntil(
                  MaterialPageRoute(builder: (_) => const BillHistoryScreen()),
                  (route) => route.isFirst,
                );
              },
              icon: const Icon(Icons.check_circle_outline),
              label: const Text('Create Bill'),
            ),
          ],
        ),
      ),
    );
  }
}
