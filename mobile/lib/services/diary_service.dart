import '../models/diary_state.dart';
import 'api_client.dart';

class DiaryStartData {
  const DiaryStartData({
    required this.data,
    required this.horaSaida,
    required this.kmInicial,
    required this.origem,
    required this.destino,
    required this.houveAbastecimento,
    this.obraId,
    this.finalidade = '',
    this.ocorrencias = '',
    this.posto = '',
    this.litros = '',
    this.valorLitro = '',
    this.numeroNota = '',
    this.tanqueCheio = false,
    this.fotoOdometroPath,
    this.cupomFiscalPath,
  });

  final String data;
  final String horaSaida;
  final int kmInicial;
  final String origem;
  final String destino;
  final int? obraId;
  final String finalidade;
  final String ocorrencias;
  final bool houveAbastecimento;
  final String posto;
  final String litros;
  final String valorLitro;
  final String numeroNota;
  final bool tanqueCheio;
  final String? fotoOdometroPath;
  final String? cupomFiscalPath;
}

class DiaryService {
  const DiaryService(this._apiClient);

  final ApiClient _apiClient;

  Future<DiaryState> obterEstado() async {
    final json = await _apiClient.get('/diario/estado');
    return DiaryState.fromJson(json);
  }

  Future<DiaryState> iniciar(DiaryStartData dados) async {
    final json = await _apiClient.postMultipartFiles(
      '/diario/iniciar',
      fields: {
        'data': dados.data,
        'hora_saida': dados.horaSaida,
        'km_inicial': dados.kmInicial.toString(),
        'origem': dados.origem,
        'destino': dados.destino,
        'obra_id': dados.obraId?.toString() ?? '',
        'finalidade': dados.finalidade,
        'ocorrencias': dados.ocorrencias,
        'houve_abastecimento': dados.houveAbastecimento ? 'sim' : 'nao',
        'posto_abastecimento': dados.posto,
        'litros_abastecimento': dados.litros,
        'valor_litro_abastecimento': dados.valorLitro,
        'numero_nota_abastecimento': dados.numeroNota,
        'tanque_cheio_abastecimento': dados.tanqueCheio ? 'sim' : 'nao',
      },
      files: {
        if (dados.fotoOdometroPath != null)
          'foto_odometro': dados.fotoOdometroPath!,
        if (dados.cupomFiscalPath != null)
          'cupom_fiscal': dados.cupomFiscalPath!,
      },
    );

    return DiaryState.fromJson(json['estado'] as Map<String, dynamic>);
  }

  Future<DiaryState> finalizar({
    required int diarioId,
    required String horaChegada,
    required int kmFinal,
  }) async {
    final json = await _apiClient.post(
      '/diario/$diarioId/finalizar',
      body: {
        'hora_chegada': horaChegada,
        'km_final': kmFinal,
      },
    );

    return DiaryState.fromJson(json['estado'] as Map<String, dynamic>);
  }
}
