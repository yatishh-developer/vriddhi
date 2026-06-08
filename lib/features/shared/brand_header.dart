import 'package:flutter/material.dart';

import '../../core/config/app_config.dart';

class BrandHeader extends StatelessWidget {
  const BrandHeader({super.key, this.subtitle});

  final String? subtitle;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          AppConfig.brandName,
          style: Theme.of(context).textTheme.labelLarge?.copyWith(
            color: Theme.of(context).colorScheme.primary,
            fontWeight: FontWeight.w900,
          ),
        ),
        const SizedBox(height: 4),
        Text(
          AppConfig.appName,
          style: Theme.of(
            context,
          ).textTheme.headlineMedium?.copyWith(fontWeight: FontWeight.w900),
        ),
        if (subtitle != null) ...[const SizedBox(height: 8), Text(subtitle!)],
      ],
    );
  }
}
