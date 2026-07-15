import 'package:geolocator/geolocator.dart';

import 'api_exception.dart';

class LocationService {
  const LocationService._();

  static Future<Position> obterAtual() async {
    final servicoAtivo = await Geolocator.isLocationServiceEnabled();
    if (!servicoAtivo) {
      throw const ApiException(
        'Ative a localização do aparelho para registrar o ponto.',
      );
    }

    var permissao = await Geolocator.checkPermission();
    if (permissao == LocationPermission.denied) {
      permissao = await Geolocator.requestPermission();
    }

    if (permissao == LocationPermission.denied) {
      throw const ApiException(
        'A permissão de localização é obrigatória para registrar o ponto.',
      );
    }

    if (permissao == LocationPermission.deniedForever) {
      throw const ApiException(
        'Libere a localização para o aplicativo nas configurações do aparelho.',
      );
    }

    return Geolocator.getCurrentPosition(
      locationSettings: const LocationSettings(
        accuracy: LocationAccuracy.high,
        timeLimit: Duration(seconds: 20),
      ),
    );
  }
}
