import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../auth/auth_controller.dart';
import '../auth/invite_code_login_screen.dart';
import '../realtime/websocket_service.dart';
import '../settings/settings_screen.dart';
import '../sync/sync_status_screen.dart';
import 'bill_history_screen.dart';
import 'cart_screen.dart';
import 'pending_kot_screen.dart';
import 'product_menu_screen.dart';

class StaffBillingHomeScreen extends StatefulWidget {
  const StaffBillingHomeScreen({super.key});

  @override
  State<StaffBillingHomeScreen> createState() => _StaffBillingHomeScreenState();
}

class _StaffBillingHomeScreenState extends State<StaffBillingHomeScreen> {
  bool _connectAttempted = false;

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (_connectAttempted) return;
    _connectAttempted = true;
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!mounted) return;
      final profile = context.read<AuthController>().profile;
      if (profile == null) return;
      context.read<WebSocketService>().connect(
        businessId: profile.businessId,
        branchId: profile.branchId,
        counterId: profile.counterId,
      );
    });
  }

  @override
  Widget build(BuildContext context) {
    final auth = context.watch<AuthController>();
    final webSocket = context.watch<WebSocketService>();
    final profile = auth.profile;
    final permissions = profile?.permissions;
    final flags = profile?.resolvedFeatureFlags;
    final canKot =
        flags?.kotEnabled == true && permissions?.canCreateKot == true;
    final canViewKot =
        flags?.kotEnabled == true && permissions?.canViewKot == true;
    final canBill = permissions?.canCreateBill != false;
    final canHold =
        flags?.holdBillEnabled == true && permissions?.canHoldBill == true;
    return Scaffold(
      appBar: AppBar(
        title: const Text('VRIDDHI Staff Billing'),
        actions: [
          IconButton(
            tooltip: 'Settings',
            onPressed: () => Navigator.of(
              context,
            ).push(MaterialPageRoute(builder: (_) => const SettingsScreen())),
            icon: const Icon(Icons.settings_outlined),
          ),
        ],
      ),
      body: SafeArea(
        child: ListView(
          padding: const EdgeInsets.all(16),
          children: [
            _StatusHeader(
              businessName: profile?.businessName ?? 'VRIDDHI',
              staffName: profile?.staffName ?? 'Staff',
              branchId: profile?.branchId ?? 'Branch',
              sectorLabel: profile?.sector.label ?? 'General Business',
              syncText: webSocket.status == WebSocketStatus.connected
                  ? 'Connected to admin'
                  : 'Sync pending',
              connected: webSocket.status == WebSocketStatus.connected,
            ),
            const SizedBox(height: 14),
            GridView.count(
              shrinkWrap: true,
              physics: const NeverScrollableScrollPhysics(),
              crossAxisCount: 2,
              crossAxisSpacing: 12,
              mainAxisSpacing: 12,
              childAspectRatio: 1.08,
              children: [
                if (canKot)
                  _HomeAction(
                    icon: Icons.receipt_long,
                    label: 'New KOT',
                    onTap: () => Navigator.of(context).push(
                      MaterialPageRoute(
                        builder: (_) => const ProductMenuScreen(),
                      ),
                    ),
                  ),
                if (canBill)
                  _HomeAction(
                    icon: flags?.serviceModeEnabled == true
                        ? Icons.spa_outlined
                        : Icons.point_of_sale,
                    label: flags?.serviceModeEnabled == true
                        ? 'Service Bill'
                        : 'New Bill',
                    onTap: () => Navigator.of(context).push(
                      MaterialPageRoute(
                        builder: (_) => const ProductMenuScreen(),
                      ),
                    ),
                  ),
                if (canViewKot)
                  _HomeAction(
                    icon: Icons.pending_actions,
                    label: 'Pending KOTs',
                    onTap: () => Navigator.of(context).push(
                      MaterialPageRoute(
                        builder: (_) => const PendingKotScreen(),
                      ),
                    ),
                  ),
                if (canHold)
                  _HomeAction(
                    icon: Icons.pause_circle_outline,
                    label: 'Held Bills',
                    onTap: () => Navigator.of(context).push(
                      MaterialPageRoute(
                        builder: (_) => const CartScreen(quickBill: true),
                      ),
                    ),
                  ),
                _HomeAction(
                  icon: Icons.history,
                  label: 'Bill History',
                  onTap: () => Navigator.of(context).push(
                    MaterialPageRoute(
                      builder: (_) => const BillHistoryScreen(),
                    ),
                  ),
                ),
                _HomeAction(
                  icon: Icons.sync,
                  label: 'Sync Status',
                  onTap: () => Navigator.of(context).push(
                    MaterialPageRoute(builder: (_) => const SyncStatusScreen()),
                  ),
                ),
                _HomeAction(
                  icon: Icons.logout,
                  label: 'Logout',
                  onTap: () async {
                    await context.read<AuthController>().logout();
                    if (!context.mounted) return;
                    Navigator.of(context).pushAndRemoveUntil(
                      MaterialPageRoute(
                        builder: (_) => const InviteCodeLoginScreen(),
                      ),
                      (_) => false,
                    );
                  },
                ),
              ],
            ),
            const SizedBox(height: 12),
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: [
                _MiniMetric(label: 'Today bills', value: '0'),
                if (permissions?.canCollectPayment == true)
                  _MiniMetric(label: 'Own collection', value: '₹0'),
                if (canViewKot) _MiniMetric(label: 'Pending KOT', value: '0'),
                if (canHold) _MiniMetric(label: 'Held bills', value: '0'),
              ],
            ),
          ],
        ),
      ),
    );
  }
}

class _StatusHeader extends StatelessWidget {
  const _StatusHeader({
    required this.businessName,
    required this.staffName,
    required this.branchId,
    required this.sectorLabel,
    required this.syncText,
    required this.connected,
  });

  final String businessName;
  final String staffName;
  final String branchId;
  final String sectorLabel;
  final String syncText;
  final bool connected;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(14),
      ),
      child: Row(
        children: [
          CircleAvatar(
            backgroundColor: Theme.of(context).colorScheme.primaryContainer,
            child: const Icon(Icons.badge_outlined),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  businessName,
                  style: const TextStyle(fontWeight: FontWeight.w900),
                ),
                const SizedBox(height: 2),
                Text(
                  staffName,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: const TextStyle(fontSize: 12, color: Colors.black87),
                ),
                const SizedBox(height: 2),
                Text(
                  '$branchId • $sectorLabel',
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: const TextStyle(fontSize: 12, color: Colors.black54),
                ),
              ],
            ),
          ),
          Column(
            crossAxisAlignment: CrossAxisAlignment.end,
            children: [
              _DotLabel(
                label: connected ? 'Connected' : 'Offline',
                color: connected ? Colors.green : Colors.orange,
              ),
              const SizedBox(height: 4),
              Text(
                syncText,
                style: const TextStyle(fontSize: 11, color: Colors.black54),
              ),
            ],
          ),
        ],
      ),
    );
  }
}

class _DotLabel extends StatelessWidget {
  const _DotLabel({required this.label, required this.color});

  final String label;
  final Color color;

  @override
  Widget build(BuildContext context) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Container(
          width: 8,
          height: 8,
          decoration: BoxDecoration(color: color, shape: BoxShape.circle),
        ),
        const SizedBox(width: 6),
        Text(label, style: const TextStyle(fontSize: 12)),
      ],
    );
  }
}

class _MiniMetric extends StatelessWidget {
  const _MiniMetric({required this.label, required this.value});

  final String label;
  final String value;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: 150,
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(12),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(label, style: const TextStyle(fontSize: 12)),
          const SizedBox(height: 4),
          Text(
            value,
            style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w900),
          ),
        ],
      ),
    );
  }
}

class _HomeAction extends StatelessWidget {
  const _HomeAction({
    required this.icon,
    required this.label,
    required this.onTap,
  });

  final IconData icon;
  final String label;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(8),
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Icon(
                icon,
                size: 34,
                color: Theme.of(context).colorScheme.primary,
              ),
              const Spacer(),
              Text(
                label,
                style: Theme.of(
                  context,
                ).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w800),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
