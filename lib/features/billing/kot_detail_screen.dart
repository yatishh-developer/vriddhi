import 'package:flutter/material.dart';

import 'billing_models.dart';
import 'convert_kot_to_bill_screen.dart';

class KotDetailScreen extends StatelessWidget {
  const KotDetailScreen({super.key, required this.kot});

  final LocalKot kot;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text(kot.kotNumber)),
      body: SafeArea(
        child: ListView(
          padding: const EdgeInsets.all(16),
          children: [
            for (final item in kot.items)
              Card(
                child: ListTile(
                  title: Text(item.name),
                  subtitle: Text('Qty ${item.quantity}'),
                  trailing: Text('₹${item.total.toStringAsFixed(2)}'),
                ),
              ),
            const SizedBox(height: 16),
            FilledButton.icon(
              onPressed: kot.canConvert
                  ? () => Navigator.of(context).push(
                      MaterialPageRoute(
                        builder: (_) => ConvertKotToBillScreen(kot: kot),
                      ),
                    )
                  : null,
              icon: const Icon(Icons.point_of_sale),
              label: const Text('Convert to Bill'),
            ),
          ],
        ),
      ),
    );
  }
}
