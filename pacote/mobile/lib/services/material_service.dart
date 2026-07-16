import '../models/material_movement.dart';
import 'api_client.dart';

class MaterialService {
  const MaterialService(this._apiClient);

  final ApiClient _apiClient;

  Future<List<MaterialMovement>> listarPendentes({String busca = ''}) async {
    final query = busca.trim().isEmpty
        ? ''
        : '?busca=${Uri.encodeQueryComponent(busca.trim())}';
    final json = await _apiClient.get('/materiais/pendentes$query');
    return _converterLista(json);
  }

  Future<List<MaterialMovement>> listarHistorico() async {
    final json = await _apiClient.get('/materiais/historico');
    return _converterLista(json);
  }

  Future<MaterialMovement> receber({
    required int movimentacaoId,
    required String clientUuid,
    required String fotoPath,
    required bool comRessalva,
    required String observacao,
    double? latitude,
    double? longitude,
    double? precisaoMetros,
  }) async {
    final json = await _apiClient.postMultipartFiles(
      '/materiais/$movimentacaoId/receber',
      fields: {
        'client_uuid': clientUuid,
        'com_ressalva': comRessalva ? 'sim' : 'nao',
        'observacao': observacao,
        if (latitude != null) 'latitude': latitude.toString(),
        if (longitude != null) 'longitude': longitude.toString(),
        if (precisaoMetros != null)
          'precisao_metros': precisaoMetros.toString(),
      },
      files: {'foto_material': fotoPath},
    );

    return MaterialMovement.fromJson(
      json['movimentacao'] as Map<String, dynamic>,
    );
  }

  List<MaterialMovement> _converterLista(Map<String, dynamic> json) {
    return (json['movimentacoes'] as List<dynamic>? ?? const [])
        .map(
          (item) => MaterialMovement.fromJson(item as Map<String, dynamic>),
        )
        .toList(growable: false);
  }
}
