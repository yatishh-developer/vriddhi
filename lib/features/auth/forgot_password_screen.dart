import 'package:flutter/material.dart';

class ForgotPasswordScreen extends StatelessWidget {
  const ForgotPasswordScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Forgot password')),
      body: const SafeArea(
        child: Padding(
          padding: EdgeInsets.all(24),
          child: Text(
            'Reset endpoint UI placeholder. Backend contract is documented.',
          ),
        ),
      ),
    );
  }
}
