import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import 'billing_controller.dart';

class BillHistoryScreen extends StatelessWidget {
  const BillHistoryScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final bills = context.watch<BillingController>().bills;
    return Scaffold(
      appBar: AppBar(title: const Text('Bill history')),
      body: SafeArea(
        child: ListView(
          padding: const EdgeInsets.all(16),
          children: [
            const TextField(
              decoration: InputDecoration(
                labelText: 'Search bill / KOT / table',
                prefixIcon: Icon(Icons.search),
              ),
            ),
            const SizedBox(height: 12),
            if (bills.isEmpty)
              const Card(
                child: Padding(
                  padding: EdgeInsets.all(16),
                  child: Text('No bills created on this device yet.'),
                ),
              )
            else
              for (final bill in bills)
                Card(
                  child: ListTile(
                    leading: const Icon(Icons.receipt),
                    title: Text(bill.billNumber),
                    subtitle: Text(bill.syncStatus),
                    trailing: Text('₹${bill.total.toStringAsFixed(2)}'),
                  ),
                ),
          ],
        ),
      ),
    );
  }
}
