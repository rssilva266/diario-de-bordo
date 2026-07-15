import 'package:flutter/material.dart';

import 'controllers/session_controller.dart';
import 'core/theme/app_theme.dart';
import 'screens/home_screen.dart';
import 'screens/login_screen.dart';
import 'screens/splash_screen.dart';

class DiarioDeBordoApp extends StatelessWidget {
  const DiarioDeBordoApp({
    required this.sessionController,
    super.key,
  });

  final SessionController sessionController;

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Diário de Bordo',
      debugShowCheckedModeBanner: false,
      theme: AppTheme.light,
      home: AnimatedBuilder(
        animation: sessionController,
        builder: (context, _) {
          return switch (sessionController.status) {
            SessionStatus.carregando => const SplashScreen(),
            SessionStatus.autenticado => HomeScreen(
                key: ValueKey(sessionController.usuario?.id),
                sessionController: sessionController,
              ),
            SessionStatus.desautenticado => LoginScreen(
                sessionController: sessionController,
              ),
          };
        },
      ),
    );
  }
}
