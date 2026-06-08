# Auth Testing and Firebase Setup

## Temporary Test Account

For backend-only testing, seed a temporary staff account:

```bash
cd /Users/yatish/vriddhi_versions/vabos_staff_backend
env PYTHONPATH=. .venv/bin/python scripts/create_test_staff.py
```

Default credentials:

- Email: `test@vriddhi.app`
- Password: `Test@12345`

These credentials are not shown in the Flutter UI. The account must exist in the
FastAPI database or authentication will fail normally.

## Create Account

The app includes a create-account screen wired to Firebase email/password auth.
FastAPI also exposes compatible `/auth/staff/signup` and `/auth/staff/login`
endpoints for staff billing auth.

## Firebase Auth

The app includes controller support for:

- Google sign-in
- Apple sign-in
- Phone OTP
- Firebase email/password account creation

Firebase auth buttons are hidden by default for publish-readiness. Before these
providers are enabled at runtime, configure Firebase for the Flutter app:

1. Run `flutterfire configure`.
2. Add the generated `lib/firebase_options.dart`.
3. Add Android `google-services.json` and iOS `GoogleService-Info.plist` as needed.
4. Enable Google, Apple, Phone, and Email/Password providers in Firebase Auth.
5. Configure Apple Sign In entitlements for iOS/macOS.
6. Build with:

```bash
flutter build web --release \
  --dart-define=ENABLE_FIREBASE_AUTH=true \
  --dart-define=FIREBASE_API_KEY=... \
  --dart-define=FIREBASE_APP_ID=... \
  --dart-define=FIREBASE_MESSAGING_SENDER_ID=... \
  --dart-define=FIREBASE_PROJECT_ID=... \
  --dart-define=FIREBASE_AUTH_DOMAIN=...
```

Until Firebase is configured, the app shows a readable Firebase configuration
error instead of silently failing.
