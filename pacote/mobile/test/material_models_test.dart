import 'package:diario_de_bordo_app/models/diary_state.dart';
import 'package:diario_de_bordo_app/models/material_movement.dart';
import 'package:diario_de_bordo_app/models/user_model.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('identifica o perfil apontador retornado pela API', () {
    final usuario = UserModel.fromJson({
      'id': 12,
      'nome': 'Apontador Teste',
      'usuario': 'apontador',
      'perfil': 'Apontador',
      'empresa': {'id': 1, 'nome': 'Empresa Teste'},
      'pode_receber_materiais': true,
    });

    expect(usuario.podeReceberMateriais, true);
    expect(usuario.perfil, 'Apontador');
  });

  test('converte uma carga em trânsito', () {
    final movimento = MaterialMovement.fromJson({
      'id': 31,
      'material': 'Tubos PEAD',
      'numero_movimentacao': 'MOV-2026-001',
      'quantidade': 12.5,
      'unidade': 'un',
      'status': 'Em trânsito',
      'recebido_em': null,
      'recebido_por': null,
      'diario': {
        'id': 44,
        'data': '2026-07-16',
        'hora_saida': '08:30',
        'origem': 'Almoxarifado',
        'destino': 'Trecho 12',
        'veiculo': {
          'id': 5,
          'placa': 'ABC1D23',
          'modelo': 'Caminhão teste',
          'km_atual': 1000,
          'combustivel': 'Diesel',
          'obra_id': null,
        },
        'motorista': {'id': 7, 'nome': 'Motorista Teste'},
        'obra': null,
      },
    });

    expect(movimento.emTransito, true);
    expect(movimento.placa, 'ABC1D23');
    expect(movimento.quantidadeFormatada, '12,500 un');
  });

  test('inclui a movimentação no diário em andamento', () {
    final diario = DiaryEntry.fromJson({
      'id': 44,
      'data': '2026-07-16',
      'hora_saida': '08:30',
      'hora_chegada': null,
      'km_inicial': 1000,
      'km_final': null,
      'km_percorrida': null,
      'origem': 'Almoxarifado',
      'destino': 'Trecho 12',
      'status': 'Em andamento',
      'veiculo': {
        'id': 5,
        'placa': 'ABC1D23',
        'modelo': 'Caminhão teste',
        'km_atual': 1000,
        'combustivel': 'Diesel',
        'obra_id': null,
      },
      'motorista': {'id': 7, 'nome': 'Motorista Teste'},
      'obra': null,
      'houve_abastecimento': false,
      'movimentacao_material': {
        'id': 31,
        'material': 'Tubos PEAD',
        'numero_movimentacao': 'MOV-2026-001',
        'quantidade': 12.5,
        'unidade': 'un',
        'status': 'Recebido',
        'recebido_em': '2026-07-16T09:45:00',
      },
    });

    expect(diario.movimentacaoMaterial?.material, 'Tubos PEAD');
    expect(diario.movimentacaoMaterial?.status, 'Recebido');
    expect(diario.movimentacaoMaterial?.recebida, true);
    expect(diario.movimentacaoMaterial?.recebidoEm?.hour, 9);
  });
}
