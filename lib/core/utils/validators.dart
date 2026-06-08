class Validators {
  const Validators._();

  static String? loginId(String? value) {
    final text = value?.trim() ?? '';
    if (text.isEmpty) return 'Enter phone, email, or staff code.';
    if (text.length < 3) return 'Enter a valid login.';
    return null;
  }

  static String? password(String? value) {
    final text = value ?? '';
    if (text.isEmpty) return 'Enter password.';
    if (text.length < 8) return 'Password must be at least 8 characters.';
    return null;
  }
}
