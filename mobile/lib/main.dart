import 'package:flutter/material.dart';

import 'app.dart';
import 'controllers/session_controller.dart';
import 'services/api_client.dart';
import 'services/auth_storage.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();

  final apiClient = ApiClient();
  final authStorage = AuthStorage();
  final sessionController = SessionController(
    apiClient: apiClient,
    authStorage: authStorage,
  );

  runApp(DiarioDeBordoApp(sessionController: sessionController));
  await sessionController.restaurarSessao();
}
