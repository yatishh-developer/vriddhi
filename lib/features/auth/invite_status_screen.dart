import 'package:flutter/material.dart';

class InviteStatusScreen extends StatelessWidget {
  const InviteStatusScreen.pending({super.key})
    : _title = 'Pending approval',
      _message = 'Your account is signed in but not linked to a business yet.',
      _icon = Icons.hourglass_empty;

  const InviteStatusScreen.invalid({super.key, required String message})
    : _title = 'Invalid invite',
      _message = message,
      _icon = Icons.error_outline;

  final String _title;
  final String _message;
  final IconData _icon;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text(_title)),
      body: Center(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Icon(_icon, size: 72, color: Theme.of(context).colorScheme.error),
              const SizedBox(height: 16),
              Text(
                _title,
                style: Theme.of(
                  context,
                ).textTheme.titleLarge?.copyWith(fontWeight: FontWeight.w800),
              ),
              const SizedBox(height: 8),
              Text(_message, textAlign: TextAlign.center),
            ],
          ),
        ),
      ),
    );
  }
}
