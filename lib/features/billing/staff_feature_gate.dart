import '../../core/models/business_sector.dart';
import '../auth/auth_models.dart';

class StaffFeatureGate {
  const StaffFeatureGate({required this.permissions, required this.flags});

  final StaffPermissions permissions;
  final BusinessFeatureFlags flags;

  bool get canShowKot =>
      flags.kotEnabled && (permissions.canCreateKot || permissions.canViewKot);
  bool get canCreateKot => flags.kotEnabled && permissions.canCreateKot;
  bool get canConvertKot => flags.kotEnabled && permissions.canConvertKotToBill;
  bool get canShowBarcode => flags.barcodeEnabled && permissions.canUseBarcode;
  bool get canHoldBill => flags.holdBillEnabled && permissions.canHoldBill;
  bool get canCollectPayment => permissions.canCollectPayment;
  bool get canShowDiscount => permissions.canGiveDiscount;
  bool get canPrint => permissions.canPrintBill;
}
