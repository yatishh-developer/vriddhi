import 'package:flutter/foundation.dart';

import '../../core/config/app_config.dart';

class SettingsController extends ChangeNotifier {
  SettingsController();

  String get activeBaseUrl => AppConfig.activeBaseUrl;

  Future<void> load() async {
    notifyListeners();
  }
}
