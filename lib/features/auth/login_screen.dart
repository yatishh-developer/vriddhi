import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../core/config/app_config.dart';
import '../../core/utils/validators.dart';
import '../billing/staff_billing_home_screen.dart';
import '../shared/brand_header.dart';
import 'auth_controller.dart';
import 'create_account_screen.dart';
import 'enter_invite_code_screen.dart';
import 'forgot_password_screen.dart';
import 'otp_auth_screen.dart';

class LoginScreen extends StatefulWidget {
  const LoginScreen({super.key});

  @override
  State<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends State<LoginScreen> {
  final _formKey = GlobalKey<FormState>();
  final _loginId = TextEditingController();
  final _password = TextEditingController();
  bool _obscurePassword = true;

  @override
  void dispose() {
    _loginId.dispose();
    _password.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    if (!_formKey.currentState!.validate()) return;
    final ok = await context.read<AuthController>().login(
      _loginId.text.trim(),
      _password.text,
    );
    if (!mounted || !ok) return;
    Navigator.of(context).pushReplacement(
      MaterialPageRoute(builder: (_) => const StaffBillingHomeScreen()),
    );
  }

  Future<void> _completeSocialAuth(Future<bool> Function() action) async {
    final ok = await action();
    if (!mounted || !ok) return;
    if (context.read<AuthController>().pendingFirebaseIdentity != null) {
      Navigator.of(context).pushReplacement(
        MaterialPageRoute(builder: (_) => const EnterInviteCodeScreen()),
      );
      return;
    }
    Navigator.of(context).pushReplacement(
      MaterialPageRoute(builder: (_) => const StaffBillingHomeScreen()),
    );
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
              child: Form(
                key: _formKey,
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    const BrandHeader(
                      subtitle: 'Staff, cashier, and waiter login.',
                    ),
                    const SizedBox(height: 28),
                    TextFormField(
                      controller: _loginId,
                      validator: Validators.loginId,
                      decoration: const InputDecoration(
                        labelText: 'Phone, email, or staff code',
                        prefixIcon: Icon(Icons.person_outline),
                      ),
                    ),
                    const SizedBox(height: 12),
                    TextFormField(
                      controller: _password,
                      obscureText: _obscurePassword,
                      validator: Validators.password,
                      decoration: InputDecoration(
                        labelText: 'Password',
                        prefixIcon: const Icon(Icons.lock_outline),
                        suffixIcon: IconButton(
                          tooltip: _obscurePassword
                              ? 'Show password'
                              : 'Hide password',
                          onPressed: () {
                            setState(
                              () => _obscurePassword = !_obscurePassword,
                            );
                          },
                          icon: Icon(
                            _obscurePassword
                                ? Icons.visibility_outlined
                                : Icons.visibility_off_outlined,
                          ),
                        ),
                      ),
                    ),
                    Align(
                      alignment: Alignment.centerRight,
                      child: TextButton(
                        onPressed: () => Navigator.of(context).push(
                          MaterialPageRoute(
                            builder: (_) => const ForgotPasswordScreen(),
                          ),
                        ),
                        child: const Text('Forgot password'),
                      ),
                    ),
                    if (auth.errorMessage != null) ...[
                      Text(
                        auth.errorMessage!,
                        style: TextStyle(
                          color: Theme.of(context).colorScheme.error,
                        ),
                      ),
                      const SizedBox(height: 12),
                    ],
                    FilledButton.icon(
                      onPressed: auth.isLoading ? null : _submit,
                      icon: const Icon(Icons.login),
                      label: const Text('Login'),
                    ),
                    const SizedBox(height: 10),
                    OutlinedButton.icon(
                      onPressed: () => Navigator.of(context).push(
                        MaterialPageRoute(
                          builder: (_) => const CreateAccountScreen(),
                        ),
                      ),
                      icon: const Icon(Icons.person_add_alt_1),
                      label: const Text('Create account'),
                    ),
                    if (AppConfig.enableFirebaseAuth) ...[
                      const SizedBox(height: 16),
                      Row(
                        children: [
                          const Expanded(child: Divider()),
                          Padding(
                            padding: const EdgeInsets.symmetric(horizontal: 12),
                            child: Text(
                              'Firebase auth',
                              style: Theme.of(context).textTheme.labelMedium,
                            ),
                          ),
                          const Expanded(child: Divider()),
                        ],
                      ),
                      const SizedBox(height: 12),
                      OutlinedButton.icon(
                        onPressed: auth.isLoading
                            ? null
                            : () => _completeSocialAuth(
                                context.read<AuthController>().signInWithGoogle,
                              ),
                        icon: const Icon(Icons.g_mobiledata),
                        label: const Text('Continue with Google'),
                      ),
                      const SizedBox(height: 10),
                      OutlinedButton.icon(
                        onPressed: auth.isLoading
                            ? null
                            : () => _completeSocialAuth(
                                context.read<AuthController>().signInWithApple,
                              ),
                        icon: const Icon(Icons.apple),
                        label: const Text('Continue with Apple'),
                      ),
                      const SizedBox(height: 10),
                      OutlinedButton.icon(
                        onPressed: () => Navigator.of(context).push(
                          MaterialPageRoute(
                            builder: (_) => const OtpAuthScreen(),
                          ),
                        ),
                        icon: const Icon(Icons.sms_outlined),
                        label: const Text('Continue with OTP'),
                      ),
                    ],
                  ],
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}
