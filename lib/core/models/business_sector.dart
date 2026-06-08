enum BusinessSector {
  restaurantCafe,
  retailKirana,
  fashionGarments,
  electronics,
  medicalPharmacy,
  salonService,
  generalBusiness;

  String get key => switch (this) {
    BusinessSector.restaurantCafe => 'restaurant_cafe',
    BusinessSector.retailKirana => 'retail_kirana',
    BusinessSector.fashionGarments => 'fashion_garments',
    BusinessSector.electronics => 'electronics',
    BusinessSector.medicalPharmacy => 'medical_pharmacy',
    BusinessSector.salonService => 'salon_service',
    BusinessSector.generalBusiness => 'general_business',
  };

  String get label => switch (this) {
    BusinessSector.restaurantCafe => 'Restaurant / Cafe',
    BusinessSector.retailKirana => 'Retail / Kirana',
    BusinessSector.fashionGarments => 'Fashion / Garments',
    BusinessSector.electronics => 'Electronics',
    BusinessSector.medicalPharmacy => 'Medical / Pharmacy',
    BusinessSector.salonService => 'Salon / Service Business',
    BusinessSector.generalBusiness => 'General Business',
  };

  static BusinessSector fromKey(String? key) {
    final normalized = (key ?? '').trim().toLowerCase().replaceAll(
      RegExp(r'[^a-z0-9]+'),
      '_',
    );
    if (normalized.contains('restaurant') ||
        normalized.contains('cafe') ||
        normalized.contains('hotel') ||
        normalized.contains('food')) {
      return restaurantCafe;
    }
    if (normalized.contains('retail') ||
        normalized.contains('kirana') ||
        normalized.contains('grocery') ||
        normalized.contains('shop') ||
        normalized.contains('store')) {
      return retailKirana;
    }
    return BusinessSector.values.firstWhere(
      (sector) => sector.key == normalized,
      orElse: () => generalBusiness,
    );
  }
}

class BusinessFeatureFlags {
  const BusinessFeatureFlags({
    required this.kotEnabled,
    required this.barcodeEnabled,
    required this.holdBillEnabled,
    required this.tableEnabled,
    required this.kitchenEnabled,
    required this.variantsEnabled,
    required this.batchExpiryEnabled,
    required this.serialNumberEnabled,
    required this.serviceModeEnabled,
    this.qrMenuEnabled = false,
    this.customerLedgerEnabled = false,
    this.inventoryEnabled = false,
    this.purchaseRestockEnabled = false,
  });

  final bool kotEnabled;
  final bool barcodeEnabled;
  final bool holdBillEnabled;
  final bool tableEnabled;
  final bool kitchenEnabled;
  final bool variantsEnabled;
  final bool batchExpiryEnabled;
  final bool serialNumberEnabled;
  final bool serviceModeEnabled;
  final bool qrMenuEnabled;
  final bool customerLedgerEnabled;
  final bool inventoryEnabled;
  final bool purchaseRestockEnabled;

  static BusinessFeatureFlags defaultsFor(BusinessSector sector) =>
      switch (sector) {
        BusinessSector.restaurantCafe => const BusinessFeatureFlags(
          kotEnabled: true,
          barcodeEnabled: false,
          holdBillEnabled: false,
          tableEnabled: true,
          kitchenEnabled: true,
          variantsEnabled: false,
          batchExpiryEnabled: false,
          serialNumberEnabled: false,
          serviceModeEnabled: false,
          qrMenuEnabled: true,
        ),
        BusinessSector.retailKirana => const BusinessFeatureFlags(
          kotEnabled: false,
          barcodeEnabled: true,
          holdBillEnabled: true,
          tableEnabled: false,
          kitchenEnabled: false,
          variantsEnabled: false,
          batchExpiryEnabled: false,
          serialNumberEnabled: false,
          serviceModeEnabled: false,
          customerLedgerEnabled: true,
          inventoryEnabled: true,
          purchaseRestockEnabled: true,
        ),
        BusinessSector.fashionGarments => const BusinessFeatureFlags(
          kotEnabled: false,
          barcodeEnabled: true,
          holdBillEnabled: true,
          tableEnabled: false,
          kitchenEnabled: false,
          variantsEnabled: true,
          batchExpiryEnabled: false,
          serialNumberEnabled: false,
          serviceModeEnabled: false,
        ),
        BusinessSector.electronics => const BusinessFeatureFlags(
          kotEnabled: false,
          barcodeEnabled: true,
          holdBillEnabled: false,
          tableEnabled: false,
          kitchenEnabled: false,
          variantsEnabled: false,
          batchExpiryEnabled: false,
          serialNumberEnabled: true,
          serviceModeEnabled: false,
          customerLedgerEnabled: true,
        ),
        BusinessSector.medicalPharmacy => const BusinessFeatureFlags(
          kotEnabled: false,
          barcodeEnabled: true,
          holdBillEnabled: false,
          tableEnabled: false,
          kitchenEnabled: false,
          variantsEnabled: false,
          batchExpiryEnabled: true,
          serialNumberEnabled: false,
          serviceModeEnabled: false,
          inventoryEnabled: true,
        ),
        BusinessSector.salonService => const BusinessFeatureFlags(
          kotEnabled: false,
          barcodeEnabled: false,
          holdBillEnabled: false,
          tableEnabled: false,
          kitchenEnabled: false,
          variantsEnabled: false,
          batchExpiryEnabled: false,
          serialNumberEnabled: false,
          serviceModeEnabled: true,
        ),
        BusinessSector.generalBusiness => const BusinessFeatureFlags(
          kotEnabled: false,
          barcodeEnabled: false,
          holdBillEnabled: true,
          tableEnabled: false,
          kitchenEnabled: false,
          variantsEnabled: false,
          batchExpiryEnabled: false,
          serialNumberEnabled: false,
          serviceModeEnabled: false,
          customerLedgerEnabled: true,
        ),
      };

  factory BusinessFeatureFlags.fromJson(Map<String, dynamic>? json) {
    if (json == null) {
      return BusinessFeatureFlags.defaultsFor(BusinessSector.generalBusiness);
    }
    return BusinessFeatureFlags(
      kotEnabled: _bool(json, 'kotEnabled', 'kot'),
      barcodeEnabled: _bool(json, 'barcodeEnabled', 'barcode_scan'),
      holdBillEnabled: _bool(json, 'holdBillEnabled', 'hold_bill'),
      tableEnabled: _bool(json, 'tableEnabled', 'table_token'),
      kitchenEnabled: _bool(json, 'kitchenEnabled', 'kitchen_flow'),
      variantsEnabled: _bool(json, 'variantsEnabled'),
      batchExpiryEnabled: _bool(json, 'batchExpiryEnabled'),
      serialNumberEnabled: _bool(json, 'serialNumberEnabled'),
      serviceModeEnabled: _bool(json, 'serviceModeEnabled'),
      qrMenuEnabled: _bool(json, 'qrMenuEnabled', 'qr_menu'),
      customerLedgerEnabled: _bool(
        json,
        'customerLedgerEnabled',
        'customer_ledger',
      ),
      inventoryEnabled: _bool(json, 'inventoryEnabled', 'inventory'),
      purchaseRestockEnabled: _bool(
        json,
        'purchaseRestockEnabled',
        'purchase_restock',
      ),
    );
  }

  static bool _bool(Map<String, dynamic> json, String key, [String? alt]) {
    return json[key] as bool? ??
        (alt == null ? null : json[alt] as bool?) ??
        false;
  }

  Map<String, dynamic> toJson() => {
    'kotEnabled': kotEnabled,
    'barcodeEnabled': barcodeEnabled,
    'holdBillEnabled': holdBillEnabled,
    'tableEnabled': tableEnabled,
    'kitchenEnabled': kitchenEnabled,
    'variantsEnabled': variantsEnabled,
    'batchExpiryEnabled': batchExpiryEnabled,
    'serialNumberEnabled': serialNumberEnabled,
    'serviceModeEnabled': serviceModeEnabled,
    'qrMenuEnabled': qrMenuEnabled,
    'customerLedgerEnabled': customerLedgerEnabled,
    'inventoryEnabled': inventoryEnabled,
    'purchaseRestockEnabled': purchaseRestockEnabled,
  };

  BusinessFeatureFlags copyWithOverride(String key, bool value) {
    final json = toJson()..[key] = value;
    return BusinessFeatureFlags.fromJson(json);
  }
}

class BusinessFeatureService {
  const BusinessFeatureService._();

  static BusinessFeatureFlags resolve({
    required BusinessSector sector,
    Map<String, bool> overrides = const {},
  }) {
    var flags = BusinessFeatureFlags.defaultsFor(sector);
    for (final entry in overrides.entries) {
      flags = flags.copyWithOverride(entry.key, entry.value);
    }
    return flags;
  }
}
