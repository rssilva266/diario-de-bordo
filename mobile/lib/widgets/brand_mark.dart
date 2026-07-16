import 'package:flutter/material.dart';

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
    return ClipRRect(
      borderRadius: BorderRadius.circular(compact ? 5 : 9),
      child: Image.asset(
        'assets/branding/motriva_fleet_icon.png',
        width: size,
        height: size,
        fit: BoxFit.cover,
        filterQuality: FilterQuality.high,
      ),
    );
  }
}