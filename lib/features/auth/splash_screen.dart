import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../shared/brand_header.dart';
import 'auth_controller.dart';
import 'invite_code_login_screen.dart';
import '../billing/staff_billing_home_screen.dart';

class SplashScreen extends StatefulWidget {
  const SplashScreen({super.key});

  @override
  State<SplashScreen> createState() => _SplashScreenState();
}

class _SplashScreenState extends State<SplashScreen> {
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) async {
      await Future<void>.delayed(const Duration(milliseconds: 700));
      if (!mounted) return;
      final auth = context.read<AuthController>();
      Navigator.of(context).pushReplacement(
        MaterialPageRoute(
          builder: (_) => auth.isAuthenticated
              ? const StaffBillingHomeScreen()
              : const InviteCodeLoginScreen(),
        ),
      );
    });
  }

  @override
  Widget build(BuildContext context) {
    return const Scaffold(
      body: SafeArea(
        child: Padding(
          padding: EdgeInsets.all(24),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              BrandHeader(subtitle: 'Fast KOT and billing for staff.'),
              SizedBox(height: 28),
              LinearProgressIndicator(),
            ],
          ),
        ),
      ),
    );
  }
}
