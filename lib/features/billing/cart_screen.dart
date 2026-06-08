import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../auth/auth_controller.dart';
import '../auth/auth_models.dart';
import '../menu/menu_models.dart';
import 'billing_controller.dart';
import 'billing_models.dart';

class CartScreen extends StatefulWidget {
  const CartScreen({super.key, this.quickBill = false});

  final bool quickBill;

  @override
  State<CartScreen> createState() => _CartScreenState();
}

class _CartScreenState extends State<CartScreen> {
  final _table = TextEditingController();
  final _notes = TextEditingController();
  double _cash = 0;
  double _upi = 0;
  double _card = 0;
  bool _saving = false;

  @override
  void dispose() {
    _table.dispose();
    _notes.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final auth = context.watch<AuthController>();
    final profile = auth.profile;
    final permissions = profile?.permissions;
    final flags = profile?.resolvedFeatureFlags;
    final controller = context.watch<BillingController>();
    final canKot =
        flags?.kotEnabled == true && permissions?.canCreateKot == true;
    final canBill = permissions?.canCreateBill == true;
    final canHold =
        flags?.holdBillEnabled == true && permissions?.canHoldBill == true;
    final canPay = permissions?.canCollectPayment == true;
    final showTable = flags?.tableEnabled == true;

    return Scaffold(
      appBar: AppBar(title: Text(widget.quickBill ? 'New Bill' : 'Cart')),
      body: SafeArea(
        child: ListView(
          padding: const EdgeInsets.fromLTRB(16, 8, 16, 120),
          children: [
            if (controller.cart.isEmpty)
              _EmptyCart(
                showKot: flags?.kotEnabled == true,
                showHeld: flags?.holdBillEnabled == true,
              )
            else ...[
              for (final item in controller.cart)
                _CartItemTile(
                  item: item,
                  onMinus: () => controller.decrement(item.productId),
                  onPlus: () {
                    final product = context
                        .read<BillingController>()
                        .cart
                        .firstWhere(
                          (cartItem) => cartItem.productId == item.productId,
                        );
                    context.read<BillingController>().cart;
                    controller.addProduct(
                      _CartProductAdapter.fromItem(product),
                    );
                  },
                  onRemove: () => controller.remove(item.productId),
                ),
              const SizedBox(height: 12),
              if (showTable) ...[
                TextField(
                  controller: _table,
                  decoration: const InputDecoration(
                    labelText: 'Table / token',
                    prefixIcon: Icon(Icons.table_restaurant_outlined),
                  ),
                ),
                const SizedBox(height: 10),
                SegmentedButton<OrderType>(
                  segments: const [
                    ButtonSegment(
                      value: OrderType.dineIn,
                      label: Text('Dine-in'),
                    ),
                    ButtonSegment(
                      value: OrderType.takeaway,
                      label: Text('Takeaway'),
                    ),
                    ButtonSegment(
                      value: OrderType.parcel,
                      label: Text('Parcel'),
                    ),
                  ],
                  selected: const {OrderType.dineIn},
                  onSelectionChanged: (_) {},
                ),
                const SizedBox(height: 10),
              ],
              TextField(
                controller: _notes,
                decoration: const InputDecoration(
                  labelText: 'Notes',
                  prefixIcon: Icon(Icons.notes_outlined),
                ),
              ),
              const SizedBox(height: 12),
              _AmountSummary(
                subtotal: controller.subtotal,
                tax: controller.tax,
                total: controller.total,
              ),
              if (canPay) ...[
                const SizedBox(height: 12),
                _PaymentPanel(
                  total: controller.total,
                  onChanged: (cash, upi, card) {
                    _cash = cash;
                    _upi = upi;
                    _card = card;
                  },
                ),
              ],
            ],
          ],
        ),
      ),
      bottomNavigationBar: controller.cart.isEmpty
          ? null
          : SafeArea(
              child: Container(
                padding: const EdgeInsets.all(16),
                color: Colors.white,
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    if (canKot)
                      _SlideAction(
                        label: 'Slide to Generate KOT',
                        loading: _saving,
                        onComplete: () => _saveKot(controller, profile),
                      ),
                    if (canBill) ...[
                      if (canKot) const SizedBox(height: 10),
                      _SlideAction(
                        label: flags?.kotEnabled == true
                            ? 'Slide to Generate Bill'
                            : 'Slide to Save Bill',
                        loading: _saving,
                        onComplete: () => _saveBill(controller, profile),
                      ),
                    ],
                    if (canHold) ...[
                      const SizedBox(height: 10),
                      _SlideAction(
                        label: 'Slide to Hold Bill',
                        loading: _saving,
                        onComplete: () => _holdBill(controller, profile),
                      ),
                    ],
                  ],
                ),
              ),
            ),
    );
  }

  Future<void> _saveKot(
    BillingController controller,
    LocalStaffProfile? profile,
  ) async {
    await _guarded(() async {
      final staff = _requireProfile(profile);
      await controller.createKot(
        businessId: staff.businessId,
        branchId: staff.branchId,
        staffId: staff.staffId,
      );
    });
  }

  Future<void> _saveBill(
    BillingController controller,
    LocalStaffProfile? profile,
  ) async {
    await _guarded(() async {
      final staff = _requireProfile(profile);
      await controller.createBill(
        businessId: staff.businessId,
        branchId: staff.branchId,
        staffId: staff.staffId,
        payment: LocalPayment(cash: _cash, upi: _upi, card: _card),
      );
    });
  }

  Future<void> _holdBill(
    BillingController controller,
    LocalStaffProfile? profile,
  ) async {
    await _guarded(() async {
      final staff = _requireProfile(profile);
      await controller.createBill(
        businessId: staff.businessId,
        branchId: staff.branchId,
        staffId: staff.staffId,
        payment: const LocalPayment(),
        hold: true,
      );
    });
  }

  LocalStaffProfile _requireProfile(LocalStaffProfile? profile) {
    if (profile == null ||
        profile.businessId.isEmpty ||
        profile.branchId.isEmpty ||
        profile.staffId.isEmpty) {
      throw StateError('Staff profile missing. Please log in again.');
    }
    return profile;
  }

  Future<void> _guarded(Future<void> Function() action) async {
    if (_saving) return;
    setState(() => _saving = true);
    String? actionError;
    try {
      await action();
    } on StateError catch (error) {
      actionError = error.message;
    } catch (_) {
      actionError = 'Could not save. Please try again.';
    } finally {
      if (mounted) setState(() => _saving = false);
    }
    if (!mounted) return;
    final error = actionError ?? context.read<BillingController>().lastError;
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text(error ?? 'Saved locally. Sync queued.')),
    );
    if (error == null) Navigator.pop(context);
  }
}

class _CartItemTile extends StatelessWidget {
  const _CartItemTile({
    required this.item,
    required this.onMinus,
    required this.onPlus,
    required this.onRemove,
  });

  final LocalKotItem item;
  final VoidCallback onMinus;
  final VoidCallback onPlus;
  final VoidCallback onRemove;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: ListTile(
        title: Text(item.name, maxLines: 2, overflow: TextOverflow.ellipsis),
        subtitle: Text('₹${item.price.toStringAsFixed(2)}'),
        trailing: SizedBox(
          width: 148,
          child: Row(
            mainAxisAlignment: MainAxisAlignment.end,
            children: [
              IconButton(onPressed: onMinus, icon: const Icon(Icons.remove)),
              Text(
                '${item.quantity}',
                style: const TextStyle(fontWeight: FontWeight.w900),
              ),
              IconButton(onPressed: onPlus, icon: const Icon(Icons.add)),
              IconButton(onPressed: onRemove, icon: const Icon(Icons.close)),
            ],
          ),
        ),
      ),
    );
  }
}

class _AmountSummary extends StatelessWidget {
  const _AmountSummary({
    required this.subtotal,
    required this.tax,
    required this.total,
  });

  final double subtotal;
  final double tax;
  final double total;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          children: [
            _AmountRow(label: 'Subtotal', value: subtotal),
            _AmountRow(label: 'GST / Tax', value: tax),
            const Divider(),
            _AmountRow(label: 'Total', value: total, bold: true),
          ],
        ),
      ),
    );
  }
}

class _AmountRow extends StatelessWidget {
  const _AmountRow({
    required this.label,
    required this.value,
    this.bold = false,
  });

  final String label;
  final double value;
  final bool bold;

  @override
  Widget build(BuildContext context) {
    final style = TextStyle(fontWeight: bold ? FontWeight.w900 : null);
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 4),
      child: Row(
        children: [
          Text(label, style: style),
          const Spacer(),
          Text('₹${value.toStringAsFixed(2)}', style: style),
        ],
      ),
    );
  }
}

class _PaymentPanel extends StatefulWidget {
  const _PaymentPanel({required this.total, required this.onChanged});

  final double total;
  final void Function(double cash, double upi, double card) onChanged;

  @override
  State<_PaymentPanel> createState() => _PaymentPanelState();
}

class _PaymentPanelState extends State<_PaymentPanel> {
  final _cash = TextEditingController();
  final _upi = TextEditingController();
  final _card = TextEditingController();

  @override
  void initState() {
    super.initState();
    _cash.text = widget.total.toStringAsFixed(2);
    _notify();
  }

  @override
  void dispose() {
    _cash.dispose();
    _upi.dispose();
    _card.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text(
              'Payment',
              style: TextStyle(fontWeight: FontWeight.w900),
            ),
            const SizedBox(height: 10),
            Row(
              children: [
                Expanded(child: _moneyField(_cash, 'Cash')),
                const SizedBox(width: 8),
                Expanded(child: _moneyField(_upi, 'UPI')),
                const SizedBox(width: 8),
                Expanded(child: _moneyField(_card, 'Card')),
              ],
            ),
          ],
        ),
      ),
    );
  }

  Widget _moneyField(TextEditingController controller, String label) {
    return TextField(
      controller: controller,
      keyboardType: TextInputType.number,
      decoration: InputDecoration(labelText: label),
      onChanged: (_) => _notify(),
    );
  }

  void _notify() {
    widget.onChanged(
      double.tryParse(_cash.text) ?? 0,
      double.tryParse(_upi.text) ?? 0,
      double.tryParse(_card.text) ?? 0,
    );
  }
}

class _SlideAction extends StatefulWidget {
  const _SlideAction({
    required this.label,
    required this.onComplete,
    required this.loading,
  });

  final String label;
  final Future<void> Function() onComplete;
  final bool loading;

  @override
  State<_SlideAction> createState() => _SlideActionState();
}

class _SlideActionState extends State<_SlideAction> {
  double _value = 0;

  @override
  Widget build(BuildContext context) {
    return Container(
      height: 54,
      decoration: BoxDecoration(
        color: Theme.of(context).colorScheme.primary,
        borderRadius: BorderRadius.circular(8),
      ),
      child: Stack(
        alignment: Alignment.center,
        children: [
          Text(
            widget.loading ? 'Saving...' : widget.label,
            style: const TextStyle(
              color: Colors.white,
              fontWeight: FontWeight.w900,
            ),
          ),
          SliderTheme(
            data: SliderTheme.of(context).copyWith(
              trackHeight: 0,
              thumbShape: const RoundSliderThumbShape(enabledThumbRadius: 22),
              overlayShape: SliderComponentShape.noOverlay,
              thumbColor: Colors.white,
            ),
            child: Slider(
              value: _value,
              onChanged: widget.loading
                  ? null
                  : (value) => setState(() => _value = value),
              onChangeEnd: widget.loading
                  ? null
                  : (value) async {
                      if (value < 0.92) {
                        setState(() => _value = 0);
                        return;
                      }
                      await widget.onComplete();
                      if (mounted) setState(() => _value = 0);
                    },
            ),
          ),
        ],
      ),
    );
  }
}

class _EmptyCart extends StatelessWidget {
  const _EmptyCart({required this.showKot, required this.showHeld});

  final bool showKot;
  final bool showHeld;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          children: [
            const Icon(Icons.shopping_cart_outlined, size: 40),
            const SizedBox(height: 8),
            const Text('Cart is empty'),
            const SizedBox(height: 10),
            Wrap(
              spacing: 8,
              children: [
                if (showKot) const Chip(label: Text('Pending KOTs')),
                if (showHeld) const Chip(label: Text('Held Bills')),
                const Chip(label: Text('Recent Bills')),
                const Chip(label: Text('Sync Status')),
              ],
            ),
          ],
        ),
      ),
    );
  }
}

class _CartProductAdapter extends LocalProduct {
  _CartProductAdapter.fromItem(LocalKotItem item)
    : super(
        id: item.productId,
        businessId: '',
        branchId: '',
        name: item.name,
        categoryId: 'cart',
        categoryName: 'Cart',
        price: item.price,
        taxRate: item.taxRate,
        unit: 'unit',
        isAvailable: true,
        updatedAt: DateTime.now(),
        syncVersion: 1,
      );
}
