import 'package:diario_de_bordo_app/models/diary_state.dart';
import 'package:diario_de_bordo_app/models/pending_point.dart';
import 'package:diario_de_bordo_app/models/point_record.dart';
import 'package:diario_de_bordo_app/models/user_model.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('converte usuário retornado pela API', () {
    final usuario = UserModel.fromJson({
      'id': 7,
      'nome': 'João da Silva',
      'usuario': 'joao',
      'perfil': 'motorista',
      'empresa': {'id': 1, 'nome': 'MSM Industrial'},
      'colaborador_vinculado': true,
    });

    expect(usuario.id, 7);
    expect(usuario.primeiroNome, 'João');
    expect(usuario.perfil, 'motorista');
    expect(usuario.empresa, 'MSM Industrial');
  });

  test('converte registro de ponto retornado pela API', () {
    final registro = PointRecord.fromJson({
      'id': 3,
      'tipo': 'REGISTRO',
      'tipo_descricao': 'Entrada',
      'registrado_em': '2026-07-14T13:30:00+00:00',
      'observacao': null,
    });

    expect(registro.id, 3);
    expect(registro.tipo, 'REGISTRO');
    expect(registro.tipoDescricao, 'Entrada');
    expect(registro.registradoEm.isUtc, false);
  });

  test('preserva os dados de uma marcação pendente', () {
    final pendencia = PendingPoint(
      clientUuid: 'aparelho-123-registro-1',
      usuarioId: 7,
      tipoPrevisto: 'entrada',
      fotoPath: '/dados/selfie.jpg',
      latitude: -9.97499,
      longitude: -67.82430,
      precisaoMetros: 8.5,
      capturadoEm: DateTime.parse('2026-07-14T08:00:00-05:00'),
      dispositivoId: 'aparelho-123',
      salvoEm: DateTime.parse('2026-07-14T08:00:02-05:00'),
    );

    final restaurada = PendingPoint.fromJson(pendencia.toJson());

    expect(restaurada.clientUuid, pendencia.clientUuid);
    expect(restaurada.usuarioId, 7);
    expect(restaurada.tipoPrevisto, 'entrada');
    expect(restaurada.latitude, closeTo(-9.97499, 0.000001));
    expect(restaurada.precisaoMetros, 8.5);
    expect(restaurada.capturadoEm, pendencia.capturadoEm);
  });

  test('converte o estado do diário de bordo retornado pela API', () {
    final estado = DiaryState.fromJson({
      'motorista': {'id': 9, 'nome': 'João da Silva'},
      'veiculo': {
        'id': 4,
        'placa': 'ABC1D23',
        'modelo': 'Fiorino',
        'km_atual': 82500,
        'combustivel': 'Gasolina',
        'obra_id': 2,
      },
      'obras': [
        {'id': 2, 'codigo': 'OB-02', 'nome': 'Unidade Norte'},
      ],
      'diario_em_andamento': {
        'id': 15,
        'data': '2026-07-14',
        'hora_saida': '08:10',
        'hora_chegada': null,
        'km_inicial': 82500,
        'km_final': null,
        'km_percorrida': null,
        'origem': 'Base',
        'destino': 'Unidade Norte',
        'finalidade': 'Entrega',
        'ocorrencias': null,
        'status': 'Em andamento',
        'veiculo': {
          'id': 4,
          'placa': 'ABC1D23',
          'modelo': 'Fiorino',
          'km_atual': 82500,
          'combustivel': 'Gasolina',
          'obra_id': 2,
        },
        'motorista': {'id': 9, 'nome': 'João da Silva'},
        'obra': {'id': 2, 'codigo': 'OB-02', 'nome': 'Unidade Norte'},
        'houve_abastecimento': true,
      },
      'pode_iniciar': false,
      'bloqueio': null,
      'recentes': [],
    });

    expect(estado.motorista.nome, 'João da Silva');
    expect(estado.veiculo?.placa, 'ABC1D23');
    expect(estado.diarioEmAndamento?.emAndamento, true);
    expect(estado.diarioEmAndamento?.houveAbastecimento, true);
    expect(estado.obras.single.descricao, 'OB-02 — Unidade Norte');
    expect(estado.podeIniciar, false);
  });
}
