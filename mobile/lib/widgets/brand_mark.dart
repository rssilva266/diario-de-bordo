import 'package:flutter/material.dart';

import '../core/theme/app_colors.dart';

class BrandMark extends StatelessWidget {
  const BrandMark({
    required this.size,
    this.compact = false,
    super.key,
  });

  final double size;
  final bool compact;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: size,
      height: size,
      decoration: BoxDecoration(
        color: AppColors.primary,
        borderRadius: BorderRadius.circular(compact ? 5 : 8),
      ),
      child: Icon(
        Icons.local_shipping_outlined,
        size: size * 0.52,
        color: Colors.white,
      ),
    );
  }
}
