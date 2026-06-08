import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../shared/brand_header.dart';
import 'auth_controller.dart';
import 'invite_status_screen.dart';
import 'scan_invite_qr_screen.dart';
import 'staff_profile_loading_screen.dart';

class EnterInviteCodeScreen extends StatefulWidget {
  const EnterInviteCodeScreen({super.key});

  @override
  State<EnterInviteCodeScreen> createState() => _EnterInviteCodeScreenState();
}

class _EnterInviteCodeScreenState extends State<EnterInviteCodeScreen> {
  final _code = TextEditingController();

  @override
  void dispose() {
    _code.dispose();
    super.dispose();
  }

  Future<void> _accept() async {
    final value = _code.text.trim();
    if (!RegExp(r'^\d{6}(\d{2})?$').hasMatch(value)) {
      Navigator.push(
        context,
        MaterialPageRoute(
          builder: (_) => const InviteStatusScreen.invalid(
            message: 'Invite code must be 6 or 8 digits.',
          ),
        ),
      );
      return;
    }
    final ok = await context.read<AuthController>().verifyInviteCode(value);
    if (!mounted) return;
    if (ok) {
      Navigator.of(context).pushAndRemoveUntil(
        MaterialPageRoute(builder: (_) => const StaffProfileLoadingScreen()),
        (_) => false,
      );
    } else {
      Navigator.push(
        context,
        MaterialPageRoute(
          builder: (_) => InviteStatusScreen.invalid(
            message:
                context.read<AuthController>().errorMessage ??
                'Invite code is invalid or expired.',
          ),
        ),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    final auth = context.watch<AuthController>();
    return Scaffold(
      body: SafeArea(
        child: Center(
          child: SingleChildScrollView(
            padding: const EdgeInsets.all(24),
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 440),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  const BrandHeader(
                    subtitle: 'Enter the staff invite from your admin.',
                  ),
                  const SizedBox(height: 28),
                  TextField(
                    controller: _code,
                    keyboardType: TextInputType.number,
                    maxLength: 8,
                    decoration: const InputDecoration(
                      labelText: 'Invite code',
                      prefixIcon: Icon(Icons.pin_outlined),
                      counterText: '',
                    ),
                  ),
                  const SizedBox(height: 12),
                  FilledButton.icon(
                    onPressed: auth.isLoading ? null : _accept,
                    icon: const Icon(Icons.verified_user_outlined),
                    label: Text(
                      auth.isLoading ? 'Checking code...' : 'Join business',
                    ),
                  ),
                  const SizedBox(height: 10),
                  OutlinedButton.icon(
                    onPressed: () => Navigator.push(
                      context,
                      MaterialPageRoute(
                        builder: (_) => const ScanInviteQrScreen(),
                      ),
                    ),
                    icon: const Icon(Icons.qr_code_scanner),
                    label: const Text('Scan invite QR'),
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}
