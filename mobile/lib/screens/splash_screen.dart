import 'package:flutter/material.dart';

import '../core/theme/app_colors.dart';
import '../widgets/brand_mark.dart';

class SplashScreen extends StatelessWidget {
  const SplashScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return const Scaffold(
      backgroundColor: AppColors.navy,
      body: SafeArea(
        child: Center(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              BrandMark(size: 76),
              SizedBox(height: 24),
              SizedBox(
                width: 26,
                height: 26,
                child: CircularProgressIndicator(
                  color: AppColors.lightBlue,
                  strokeWidth: 3,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
