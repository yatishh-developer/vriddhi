import '../../core/models/business_sector.dart';

class StaffPermissions {
  const StaffPermissions({
    this.canCreateKot = false,
    this.canViewKot = true,
    this.canConvertKotToBill = false,
    this.canCreateBill = true,
    this.canHoldBill = false,
    this.canUseBarcode = false,
    this.canCollectPayment = false,
    this.canGiveDiscount = false,
    this.canPrintBill = false,
    this.canCancelKot = false,
    this.canCancelBill = false,
    this.canViewOwnBillsOnly = true,
  });

  final bool canCreateKot;
  final bool canViewKot;
  final bool canConvertKotToBill;
  final bool canCreateBill;
  final bool canHoldBill;
  final bool canUseBarcode;
  final bool canCollectPayment;
  final bool canGiveDiscount;
  final bool canPrintBill;
  final bool canCancelKot;
  final bool canCancelBill;
  final bool canViewOwnBillsOnly;

  factory StaffPermissions.fromJson(Map<String, dynamic>? json) {
    return StaffPermissions(
      canCreateKot: _bool(json, 'canCreateKot', 'create_kot'),
      canViewKot: _bool(json, 'canViewKot', 'view_kot', fallback: true),
      canConvertKotToBill: _bool(
        json,
        'canConvertKotToBill',
        'convert_kot_to_bill',
      ),
      canCreateBill: _bool(
        json,
        'canCreateBill',
        'create_bill',
        fallback: true,
      ),
      canHoldBill: _bool(json, 'canHoldBill', 'hold_bill'),
      canUseBarcode: _bool(json, 'canUseBarcode', 'barcode_scan'),
      canCollectPayment: _bool(json, 'canCollectPayment', 'collect_payment'),
      canGiveDiscount: _bool(json, 'canGiveDiscount', 'apply_discount'),
      canPrintBill: _bool(json, 'canPrintBill', 'print_bill'),
      canCancelKot: _bool(json, 'canCancelKot', 'cancel_kot'),
      canCancelBill: _bool(json, 'canCancelBill', 'cancel_bill'),
      canViewOwnBillsOnly: _bool(
        json,
        'canViewOwnBillsOnly',
        'view_own_bills_only',
        fallback: true,
      ),
    );
  }

  Map<String, dynamic> toJson() => {
    'canCreateKot': canCreateKot,
    'canViewKot': canViewKot,
    'canConvertKotToBill': canConvertKotToBill,
    'canCreateBill': canCreateBill,
    'canHoldBill': canHoldBill,
    'canUseBarcode': canUseBarcode,
    'canCollectPayment': canCollectPayment,
    'canGiveDiscount': canGiveDiscount,
    'canPrintBill': canPrintBill,
    'canCancelKot': canCancelKot,
    'canCancelBill': canCancelBill,
    'canViewOwnBillsOnly': canViewOwnBillsOnly,
  };

  static bool _bool(
    Map<String, dynamic>? json,
    String key,
    String alt, {
    bool fallback = false,
  }) {
    return json?[key] as bool? ?? json?[alt] as bool? ?? fallback;
  }
}

class LocalStaffProfile {
  const LocalStaffProfile({
    required this.staffId,
    required this.staffName,
    required this.businessId,
    this.businessName = '',
    required this.branchId,
    this.counterId,
    required this.role,
    required this.permissions,
    this.sector = BusinessSector.generalBusiness,
    this.featureFlags,
  });

  final String staffId;
  final String staffName;
  final String businessId;
  final String businessName;
  final String branchId;
  final String? counterId;
  final String role;
  final StaffPermissions permissions;
  final BusinessSector sector;
  final BusinessFeatureFlags? featureFlags;

  BusinessFeatureFlags get resolvedFeatureFlags =>
      featureFlags ?? BusinessFeatureFlags.defaultsFor(sector);

  factory LocalStaffProfile.fromJson(Map<String, dynamic> json) {
    final businessProfile = json['businessProfile'] is Map<String, dynamic>
        ? json['businessProfile'] as Map<String, dynamic>
        : <String, dynamic>{};
    final sector = BusinessSector.fromKey(
      json['businessSector'] as String? ??
          json['business_type'] as String? ??
          json['businessType'] as String? ??
          businessProfile['sector'] as String? ??
          businessProfile['business_type'] as String? ??
          businessProfile['businessSector'] as String?,
    );
    return LocalStaffProfile(
      staffId:
          json['staffId'] as String? ??
          json['staff_id'] as String? ??
          json['id']?.toString() ??
          '',
      staffName:
          json['staffName'] as String? ??
          json['staff_name'] as String? ??
          json['name'] as String? ??
          '',
      businessId:
          json['businessId'] as String? ??
          json['business_id'] as String? ??
          businessProfile['businessId'] as String? ??
          businessProfile['business_id'] as String? ??
          '',
      businessName:
          json['businessName'] as String? ??
          json['business_name'] as String? ??
          businessProfile['businessName'] as String? ??
          businessProfile['business_name'] as String? ??
          '',
      branchId:
          json['branchId'] as String? ??
          json['branch_id'] as String? ??
          businessProfile['branchId'] as String? ??
          businessProfile['branch_id'] as String? ??
          '',
      counterId: json['counterId'] as String?,
      role: json['role'] as String? ?? 'staff',
      permissions: StaffPermissions.fromJson(
        json['permissions'] is Map<String, dynamic>
            ? json['permissions'] as Map<String, dynamic>
            : null,
      ),
      sector: sector,
      featureFlags: json['featureFlags'] is Map<String, dynamic>
          ? BusinessFeatureFlags.fromJson(
              json['featureFlags'] as Map<String, dynamic>,
            )
          : json['feature_flags'] is Map<String, dynamic>
          ? BusinessFeatureFlags.fromJson(
              json['feature_flags'] as Map<String, dynamic>,
            )
          : null,
    );
  }

  Map<String, dynamic> toJson() => {
    'staffId': staffId,
    'staffName': staffName,
    'businessId': businessId,
    'businessName': businessName,
    'branchId': branchId,
    'counterId': counterId,
    'role': role,
    'permissions': permissions.toJson(),
    'businessSector': sector.key,
    'featureFlags': resolvedFeatureFlags.toJson(),
  };
}

class AuthSession {
  const AuthSession({
    required this.accessToken,
    required this.refreshToken,
    required this.profile,
  });

  final String accessToken;
  final String refreshToken;
  final LocalStaffProfile profile;

  factory AuthSession.fromJson(Map<String, dynamic> json) {
    final profileJson = json['staff'] ?? json['profile'] ?? json['user'];
    final mergedProfile = <String, dynamic>{
      if (profileJson is Map<String, dynamic>) ...profileJson,
      if (json['staff_id'] != null) 'staff_id': json['staff_id'],
      if (json['staff_name'] != null) 'staff_name': json['staff_name'],
      if (json['business_id'] != null) 'business_id': json['business_id'],
      if (json['business_name'] != null) 'business_name': json['business_name'],
      if (json['business_type'] != null) 'business_type': json['business_type'],
      if (json['branch_id'] != null) 'branch_id': json['branch_id'],
      if (json['role'] != null) 'role': json['role'],
      if (json['businessProfile'] != null)
        'businessProfile': json['businessProfile'],
      if (json['permissions'] != null) 'permissions': json['permissions'],
      if (json['featureFlags'] != null) 'featureFlags': json['featureFlags'],
      if (json['feature_flags'] != null) 'feature_flags': json['feature_flags'],
      if (json['businessSector'] != null)
        'businessSector': json['businessSector'],
    };
    return AuthSession(
      accessToken:
          json['accessToken'] as String? ?? json['access_token'] as String,
      refreshToken:
          json['refreshToken'] as String? ?? json['refresh_token'] as String,
      profile: LocalStaffProfile.fromJson(mergedProfile),
    );
  }

  factory AuthSession.fromLegacyTokenJson(
    Map<String, dynamic> json, {
    required String loginId,
  }) {
    final accessToken =
        json['accessToken'] as String? ?? json['access_token'] as String? ?? '';
    final refreshToken =
        json['refreshToken'] as String? ??
        json['refresh_token'] as String? ??
        accessToken;
    return AuthSession(
      accessToken: accessToken,
      refreshToken: refreshToken,
      profile: LocalStaffProfile(
        staffId: loginId,
        staffName: 'Staff Member',
        businessId: 'test_business',
        businessName: 'Test Business',
        branchId: 'test_branch',
        role: 'cashier',
        sector: BusinessSector.restaurantCafe,
        permissions: const StaffPermissions(
          canCreateKot: true,
          canViewKot: true,
          canConvertKotToBill: true,
          canCreateBill: true,
          canCollectPayment: true,
          canPrintBill: true,
        ),
      ),
    );
  }
}

class FirebaseIdentity {
  const FirebaseIdentity({
    required this.idToken,
    required this.uid,
    required this.email,
    required this.displayName,
    required this.provider,
  });

  final String idToken;
  final String uid;
  final String email;
  final String displayName;
  final String provider;

  Map<String, dynamic> toJson() => {
    'idToken': idToken,
    'uid': uid,
    'email': email,
    'displayName': displayName,
    'provider': provider,
  };
}
