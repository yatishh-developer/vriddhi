import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../auth/auth_controller.dart';
import '../menu/menu_models.dart';
import '../menu/menu_repository.dart';
import '../sync/sync_status_screen.dart';
import 'billing_controller.dart';
import 'cart_screen.dart';
import 'pending_kot_screen.dart';

class ProductMenuScreen extends StatefulWidget {
  const ProductMenuScreen({super.key});

  @override
  State<ProductMenuScreen> createState() => _ProductMenuScreenState();
}

class _ProductMenuScreenState extends State<ProductMenuScreen> {
  String _query = '';
  String _category = 'All';
  bool _loaded = false;
  bool _loading = false;
  String? _loadError;

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (_loaded) return;
    _loaded = true;
    _refreshProducts();
  }

  Future<void> _refreshProducts() async {
    setState(() {
      _loading = true;
      _loadError = null;
    });
    try {
      await context.read<MenuRepository>().refreshProducts();
    } catch (_) {
      _loadError = 'Offline. Showing saved products if available.';
    } finally {
      if (mounted) {
        setState(() => _loading = false);
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final profile = context.watch<AuthController>().profile;
    final flags = profile?.resolvedFeatureFlags;
    final permissions = profile?.permissions;
    final products = context.watch<MenuRepository>().products();
    final categories = [
      'All',
      ...{for (final p in products) p.categoryName},
    ];
    final filtered = products.where((product) {
      final matchesCategory =
          _category == 'All' || product.categoryName == _category;
      final text = '${product.name} ${product.categoryName}'.toLowerCase();
      return matchesCategory && text.contains(_query.toLowerCase());
    }).toList();
    final controller = context.watch<BillingController>();
    final cartCount = controller.cart.fold<int>(
      0,
      (sum, item) => sum + item.quantity,
    );

    return GestureDetector(
      onHorizontalDragEnd: (details) {
        if ((details.primaryVelocity ?? 0) > 350) {
          Navigator.push(
            context,
            MaterialPageRoute(builder: (_) => const CartScreen()),
          );
        }
      },
      child: Scaffold(
        appBar: AppBar(
          title: Text(
            flags?.serviceModeEnabled == true ? 'Service billing' : 'Billing',
          ),
          actions: [
            if (flags?.barcodeEnabled == true &&
                permissions?.canUseBarcode == true)
              IconButton(
                tooltip: 'Scan barcode',
                onPressed: () => ScaffoldMessenger.of(context).showSnackBar(
                  const SnackBar(content: Text('Barcode scanner placeholder')),
                ),
                icon: const Icon(Icons.qr_code_scanner),
              ),
            IconButton(
              tooltip: 'Cart',
              onPressed: () => Navigator.push(
                context,
                MaterialPageRoute(builder: (_) => const CartScreen()),
              ),
              icon: Badge.count(
                count: cartCount,
                isLabelVisible: cartCount > 0,
                child: const Icon(Icons.shopping_cart_outlined),
              ),
            ),
          ],
        ),
        body: SafeArea(
          child: Column(
            children: [
              Padding(
                padding: const EdgeInsets.fromLTRB(16, 8, 16, 10),
                child: Column(
                  children: [
                    TextField(
                      onChanged: (value) => setState(() => _query = value),
                      decoration: InputDecoration(
                        labelText: flags?.barcodeEnabled == true
                            ? 'Search or scan SKU'
                            : 'Search products',
                        prefixIcon: const Icon(Icons.search),
                        suffixIcon: cartCount == 0
                            ? null
                            : Padding(
                                padding: const EdgeInsets.only(right: 12),
                                child: Center(
                                  widthFactor: 1,
                                  child: Text(
                                    '₹${controller.total.toStringAsFixed(2)}',
                                    style: const TextStyle(
                                      fontWeight: FontWeight.w900,
                                    ),
                                  ),
                                ),
                              ),
                      ),
                    ),
                    const SizedBox(height: 10),
                    SizedBox(
                      height: 38,
                      child: ListView.separated(
                        scrollDirection: Axis.horizontal,
                        itemCount: categories.length,
                        separatorBuilder: (_, _) => const SizedBox(width: 8),
                        itemBuilder: (context, index) {
                          final category = categories[index];
                          return ChoiceChip(
                            label: Text(category),
                            selected: category == _category,
                            onSelected: (_) =>
                                setState(() => _category = category),
                          );
                        },
                      ),
                    ),
                  ],
                ),
              ),
              if (controller.cart.isEmpty)
                _EmptyCartShortcuts(
                  kotEnabled: flags?.kotEnabled == true,
                  holdBillEnabled: flags?.holdBillEnabled == true,
                ),
              if (_loading) const LinearProgressIndicator(),
              if (_loadError != null && products.isNotEmpty)
                Padding(
                  padding: const EdgeInsets.fromLTRB(16, 8, 16, 0),
                  child: Text(
                    _loadError!,
                    style: const TextStyle(fontSize: 12, color: Colors.orange),
                  ),
                ),
              Expanded(
                child: products.isEmpty
                    ? _EmptyProducts(
                        loading: _loading,
                        error: _loadError,
                        onRetry: _refreshProducts,
                      )
                    : GridView.builder(
                        padding: const EdgeInsets.fromLTRB(16, 4, 16, 88),
                        gridDelegate:
                            const SliverGridDelegateWithMaxCrossAxisExtent(
                              maxCrossAxisExtent: 210,
                              crossAxisSpacing: 12,
                              mainAxisSpacing: 12,
                              childAspectRatio: 1.08,
                            ),
                        itemCount: filtered.length,
                        itemBuilder: (context, index) {
                          final product = filtered[index];
                          return _ProductCard(
                            product: product,
                            onTap: product.isAvailable
                                ? () => context
                                      .read<BillingController>()
                                      .addProduct(product)
                                : null,
                          );
                        },
                      ),
              ),
            ],
          ),
        ),
        bottomNavigationBar: SafeArea(
          child: Container(
            padding: const EdgeInsets.fromLTRB(16, 8, 16, 12),
            decoration: const BoxDecoration(color: Colors.white),
            child: FilledButton.icon(
              onPressed: controller.cart.isEmpty
                  ? null
                  : () => Navigator.push(
                      context,
                      MaterialPageRoute(builder: (_) => const CartScreen()),
                    ),
              icon: const Icon(Icons.swipe_right_alt),
              label: Text(
                cartCount == 0
                    ? 'Swipe right to open cart'
                    : 'Cart • $cartCount item(s) • ₹${controller.total.toStringAsFixed(2)}',
              ),
            ),
          ),
        ),
      ),
    );
  }
}

class _ProductCard extends StatelessWidget {
  const _ProductCard({required this.product, required this.onTap});

  final LocalProduct product;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(8),
        child: Padding(
          padding: const EdgeInsets.all(12),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Icon(
                Icons.shopping_bag_outlined,
                color: Theme.of(context).colorScheme.primary,
              ),
              const Spacer(),
              Text(
                product.name,
                maxLines: 2,
                overflow: TextOverflow.ellipsis,
                style: const TextStyle(fontWeight: FontWeight.w900),
              ),
              const SizedBox(height: 3),
              Text(
                product.categoryName,
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: const TextStyle(fontSize: 12, color: Colors.black54),
              ),
              const SizedBox(height: 8),
              Row(
                children: [
                  Text(
                    '₹${product.price.toStringAsFixed(2)}',
                    style: const TextStyle(fontWeight: FontWeight.bold),
                  ),
                  const Spacer(),
                  const Icon(Icons.add_circle, size: 22),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _EmptyProducts extends StatelessWidget {
  const _EmptyProducts({
    required this.loading,
    required this.error,
    required this.onRetry,
  });

  final bool loading;
  final String? error;
  final Future<void> Function() onRetry;

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Icon(Icons.inventory_2_outlined, size: 44),
            const SizedBox(height: 12),
            Text(
              loading ? 'Loading products...' : 'No products available',
              style: Theme.of(
                context,
              ).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w800),
            ),
            const SizedBox(height: 6),
            Text(
              error ?? 'Connect to admin and sync products before billing.',
              textAlign: TextAlign.center,
              style: const TextStyle(color: Colors.black54),
            ),
            const SizedBox(height: 12),
            OutlinedButton.icon(
              onPressed: loading ? null : onRetry,
              icon: const Icon(Icons.refresh),
              label: const Text('Sync products'),
            ),
          ],
        ),
      ),
    );
  }
}

class _EmptyCartShortcuts extends StatelessWidget {
  const _EmptyCartShortcuts({
    required this.kotEnabled,
    required this.holdBillEnabled,
  });

  final bool kotEnabled;
  final bool holdBillEnabled;

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      height: 68,
      child: ListView(
        padding: const EdgeInsets.symmetric(horizontal: 16),
        scrollDirection: Axis.horizontal,
        children: [
          if (kotEnabled)
            _ShortcutChip(
              icon: Icons.pending_actions,
              label: 'Pending KOTs',
              onTap: () => Navigator.push(
                context,
                MaterialPageRoute(builder: (_) => const PendingKotScreen()),
              ),
            ),
          if (holdBillEnabled)
            _ShortcutChip(
              icon: Icons.pause_circle_outline,
              label: 'Held Bills',
              onTap: () {},
            ),
          _ShortcutChip(
            icon: Icons.history,
            label: 'Recent Bills',
            onTap: () {},
          ),
          _ShortcutChip(
            icon: Icons.sync,
            label: 'Sync Status',
            onTap: () => Navigator.push(
              context,
              MaterialPageRoute(builder: (_) => const SyncStatusScreen()),
            ),
          ),
        ],
      ),
    );
  }
}

class _ShortcutChip extends StatelessWidget {
  const _ShortcutChip({
    required this.icon,
    required this.label,
    required this.onTap,
  });

  final IconData icon;
  final String label;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(right: 8),
      child: ActionChip(
        avatar: Icon(icon, size: 18),
        label: Text(label),
        onPressed: onTap,
      ),
    );
  }
}
