import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../billing/staff_billing_home_screen.dart';
import 'auth_controller.dart';

class OtpAuthScreen extends StatefulWidget {
  const OtpAuthScreen({super.key});

  @override
  State<OtpAuthScreen> createState() => _OtpAuthScreenState();
}

class _OtpAuthScreenState extends State<OtpAuthScreen> {
  final _phone = TextEditingController();
  final _otp = TextEditingController();
  bool _otpSent = false;

  @override
  void dispose() {
    _phone.dispose();
    _otp.dispose();
    super.dispose();
  }

  Future<void> _sendOtp() async {
    final ok = await context.read<AuthController>().sendPhoneOtp(
      _phone.text.trim(),
    );
    if (!mounted || !ok) return;
    setState(() => _otpSent = true);
  }

  Future<void> _verifyOtp() async {
    final ok = await context.read<AuthController>().verifyPhoneOtp(
      _otp.text.trim(),
    );
    if (!mounted || !ok) return;
    Navigator.of(context).pushReplacement(
      MaterialPageRoute(builder: (_) => const StaffBillingHomeScreen()),
    );
  }

  @override
  Widget build(BuildContext context) {
    final auth = context.watch<AuthController>();
    return Scaffold(
      appBar: AppBar(title: const Text('Phone OTP')),
      body: SafeArea(
        child: ListView(
          padding: const EdgeInsets.all(24),
          children: [
            TextField(
              controller: _phone,
              keyboardType: TextInputType.phone,
              decoration: const InputDecoration(
                labelText: 'Phone number with country code',
                prefixIcon: Icon(Icons.phone_outlined),
              ),
            ),
            const SizedBox(height: 12),
            if (_otpSent)
              TextField(
                controller: _otp,
                keyboardType: TextInputType.number,
                decoration: const InputDecoration(
                  labelText: 'OTP',
                  prefixIcon: Icon(Icons.sms_outlined),
                ),
              ),
            if (auth.errorMessage != null) ...[
              const SizedBox(height: 12),
              Text(
                auth.errorMessage!,
                style: TextStyle(color: Theme.of(context).colorScheme.error),
              ),
            ],
            const SizedBox(height: 16),
            FilledButton.icon(
              onPressed: auth.isLoading
                  ? null
                  : (_otpSent ? _verifyOtp : _sendOtp),
              icon: Icon(
                _otpSent ? Icons.verified_outlined : Icons.sms_outlined,
              ),
              label: Text(_otpSent ? 'Verify OTP' : 'Send OTP'),
            ),
          ],
        ),
      ),
    );
  }
}
