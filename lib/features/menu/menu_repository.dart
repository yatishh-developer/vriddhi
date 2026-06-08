import 'package:hive/hive.dart';

import '../../core/network/api_client.dart';
import '../../core/storage/local_database.dart';
import 'menu_models.dart';

class MenuRepository {
  MenuRepository(this._apiClient, {LocalDatabase? database})
    : _database = database ?? LocalDatabase.instance;

  final ApiClient _apiClient;
  final LocalDatabase _database;

  List<LocalProduct> products() {
    return _productBox.values
        .whereType<Map>()
        .map((value) => LocalProduct.fromJson(Map<String, dynamic>.from(value)))
        .where((product) => product.id.isNotEmpty)
        .toList()
      ..sort((a, b) => a.name.compareTo(b.name));
  }

  Future<List<LocalProduct>> refreshProducts() async {
    final response = await _apiClient.get('/staff/products');
    final products = (response.data as List)
        .whereType<Map>()
        .map(
          (value) =>
              LocalProduct.fromBackendJson(Map<String, dynamic>.from(value)),
        )
        .where((product) => product.id.isNotEmpty)
        .toList();
    await _productBox.clear();
    for (final product in products) {
      await _productBox.put(product.id, product.toJson());
    }
    return products;
  }

  Box<dynamic> get _productBox => _database.box(LocalDatabase.productBox);
}
