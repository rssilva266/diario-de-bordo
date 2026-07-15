import 'dart:io';
import 'dart:math';

import '../models/point_day_state.dart';
import 'api_client.dart';

class PointService {
  const PointService(this._apiClient);

  final ApiClient _apiClient;

  Future<PointDayState> obterEstado() async {
    final json = await _apiClient.get('/ponto/estado');
    return PointDayState.fromJson(json);
  }

  Future<PointDayState> registrar({
    required String clientUuid,
    required String fotoPath,
    required double latitude,
    required double longitude,
    required double precisaoMetros,
    required DateTime capturadoEm,
    required String dispositivoId,
  }) async {
    final json = await _apiClient.postMultipart(
      '/ponto/registrar',
      fields: {
        'client_uuid': clientUuid,
        'capturado_em': capturadoEm.toIso8601String(),
        'latitude': latitude.toStringAsFixed(8),
        'longitude': longitude.toStringAsFixed(8),
        'precisao_metros': precisaoMetros.toStringAsFixed(2),
        'dispositivo_id': dispositivoId,
        'dispositivo_info': '${Platform.operatingSystem} ${Platform.operatingSystemVersion}',
      },
      fileField: 'foto',
      filePath: fotoPath,
    );

    final estado = json['estado'];
    if (estado is Map<String, dynamic>) {
      return PointDayState.fromJson(estado);
    }

    return obterEstado();
  }

  String gerarClientUuid(String dispositivoId, DateTime data) {
    final random = Random.secure();
    final sufixo = List.generate(
      12,
      (_) => random.nextInt(16).toRadixString(16),
    ).join();

    return '$dispositivoId-${data.microsecondsSinceEpoch}-$sufixo';
  }
}
