import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../core/utils/validators.dart';
import '../billing/staff_billing_home_screen.dart';
import '../shared/brand_header.dart';
import 'auth_controller.dart';

class CreateAccountScreen extends StatefulWidget {
  const CreateAccountScreen({super.key});

  @override
  State<CreateAccountScreen> createState() => _CreateAccountScreenState();
}

class _CreateAccountScreenState extends State<CreateAccountScreen> {
  final _formKey = GlobalKey<FormState>();
  final _name = TextEditingController();
  final _email = TextEditingController();
  final _password = TextEditingController();
  bool _obscurePassword = true;

  @override
  void dispose() {
    _name.dispose();
    _email.dispose();
    _password.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    if (!_formKey.currentState!.validate()) return;
    final ok = await context.read<AuthController>().createAccount(
      name: _name.text.trim(),
      email: _email.text.trim(),
      password: _password.text,
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
      appBar: AppBar(title: const Text('Create account')),
      body: SafeArea(
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(24),
          child: Form(
            key: _formKey,
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                const BrandHeader(subtitle: 'Create a staff billing login.'),
                const SizedBox(height: 24),
                TextFormField(
                  controller: _name,
                  validator: (value) {
                    if ((value ?? '').trim().isEmpty) return 'Enter name.';
                    return null;
                  },
                  decoration: const InputDecoration(
                    labelText: 'Name',
                    prefixIcon: Icon(Icons.badge_outlined),
                  ),
                ),
                const SizedBox(height: 12),
                TextFormField(
                  controller: _email,
                  keyboardType: TextInputType.emailAddress,
                  validator: Validators.loginId,
                  decoration: const InputDecoration(
                    labelText: 'Email',
                    prefixIcon: Icon(Icons.mail_outline),
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
                        setState(() => _obscurePassword = !_obscurePassword);
                      },
                      icon: Icon(
                        _obscurePassword
                            ? Icons.visibility_outlined
                            : Icons.visibility_off_outlined,
                      ),
                    ),
                  ),
                ),
                if (auth.errorMessage != null) ...[
                  const SizedBox(height: 12),
                  Text(
                    auth.errorMessage!,
                    style: TextStyle(
                      color: Theme.of(context).colorScheme.error,
                    ),
                  ),
                ],
                const SizedBox(height: 16),
                FilledButton.icon(
                  onPressed: auth.isLoading ? null : _submit,
                  icon: const Icon(Icons.person_add_alt_1),
                  label: const Text('Create account'),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
