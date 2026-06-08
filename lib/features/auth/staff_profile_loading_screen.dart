import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../billing/staff_billing_home_screen.dart';
import '../shared/brand_header.dart';
import 'auth_controller.dart';
import 'invite_code_login_screen.dart';

class StaffProfileLoadingScreen extends StatefulWidget {
  const StaffProfileLoadingScreen({super.key});

  @override
  State<StaffProfileLoadingScreen> createState() =>
      _StaffProfileLoadingScreenState();
}

class _StaffProfileLoadingScreenState extends State<StaffProfileLoadingScreen> {
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) => _load());
  }

  Future<void> _load() async {
    final auth = context.read<AuthController>();
    if (auth.profile != null && auth.isAuthenticated) {
      Navigator.of(context).pushReplacement(
        MaterialPageRoute(builder: (_) => const StaffBillingHomeScreen()),
      );
      return;
    }
    await auth.logout();
    if (!mounted) return;
    Navigator.of(context).pushReplacement(
      MaterialPageRoute(builder: (_) => const InviteCodeLoginScreen()),
    );
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
              BrandHeader(subtitle: 'Loading your staff profile.'),
              SizedBox(height: 28),
              LinearProgressIndicator(),
            ],
          ),
        ),
      ),
    );
  }
}
