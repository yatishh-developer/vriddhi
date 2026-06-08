import 'package:hive_flutter/hive_flutter.dart';

class LocalDatabase {
  LocalDatabase._();

  static final instance = LocalDatabase._();
  bool _ready = false;

  static const settingsBox = 'settings';
  static const profileBox = 'profile';
  static const productBox = 'products';
  static const categoryBox = 'categories';
  static const kotBox = 'kots';
  static const billBox = 'bills';
  static const paymentBox = 'payments';
  static const syncQueueBox = 'sync_queue';
  static const realtimeEventBox = 'realtime_events';
  static const metadataBox = 'metadata';

  Future<void> init() async {
    if (_ready) return;
    await Hive.initFlutter();
    await Future.wait([
      Hive.openBox<dynamic>(settingsBox),
      Hive.openBox<dynamic>(profileBox),
      Hive.openBox<dynamic>(productBox),
      Hive.openBox<dynamic>(categoryBox),
      Hive.openBox<dynamic>(kotBox),
      Hive.openBox<dynamic>(billBox),
      Hive.openBox<dynamic>(paymentBox),
      Hive.openBox<dynamic>(syncQueueBox),
      Hive.openBox<dynamic>(realtimeEventBox),
      Hive.openBox<dynamic>(metadataBox),
    ]);
    _ready = true;
  }

  Box<dynamic> box(String name) => Hive.box<dynamic>(name);
}
