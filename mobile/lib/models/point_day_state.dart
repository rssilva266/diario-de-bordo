import 'point_record.dart';

class PointDayState {
  const PointDayState({
    required this.colaboradorNome,
    required this.matricula,
    required this.localTrabalho,
    required this.proximoTipo,
    required this.proximoTipoDescricao,
    required this.jornadaConcluida,
    required this.registros,
  });

  final String colaboradorNome;
  final String matricula;
  final String? localTrabalho;
  final String? proximoTipo;
  final String? proximoTipoDescricao;
  final bool jornadaConcluida;
  final List<PointRecord> registros;

  factory PointDayState.fromJson(Map<String, dynamic> json) {
    final colaborador = json['colaborador'] as Map<String, dynamic>;
    final local = json['local_trabalho'] as Map<String, dynamic>?;
    final registros = json['registros'] as List<dynamic>? ?? [];

    return PointDayState(
      colaboradorNome: colaborador['nome'] as String,
      matricula: colaborador['matricula'] as String,
      localTrabalho: local?['nome'] as String?,
      proximoTipo: json['proximo_tipo'] as String?,
      proximoTipoDescricao: json['proximo_tipo_descricao'] as String?,
      jornadaConcluida: json['jornada_concluida'] as bool? ?? false,
      registros: registros
          .map((item) => PointRecord.fromJson(item as Map<String, dynamic>))
          .toList(),
    );
  }
}
