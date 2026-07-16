class MaterialMovement {
  const MaterialMovement({
    required this.id,
    required this.material,
    required this.numeroMovimentacao,
    required this.status,
    required this.diarioId,
    required this.data,
    required this.horaSaida,
    required this.origem,
    required this.destino,
    required this.placa,
    required this.modeloVeiculo,
    required this.motorista,
    this.quantidade,
    this.unidade,
    this.observacaoCarga,
    this.obra,
    this.recebidoEm,
    this.recebidoPor,
    this.observacaoRecebimento,
  });

  final int id;
  final String material;
  final String numeroMovimentacao;
  final double? quantidade;
  final String? unidade;
  final String? observacaoCarga;
  final String status;
  final int diarioId;
  final DateTime data;
  final String horaSaida;
  final String origem;
  final String destino;
  final String placa;
  final String modeloVeiculo;
  final String motorista;
  final String? obra;
  final DateTime? recebidoEm;
  final String? recebidoPor;
  final String? observacaoRecebimento;

  bool get emTransito => status == 'Em trânsito';
  bool get comRessalva => status == 'Recebido com ressalva';

  String? get quantidadeFormatada {
    final valor = quantidade;
    if (valor == null) return null;

    final casas = valor == valor.truncateToDouble() ? 0 : 3;
    final texto = valor.toStringAsFixed(casas).replaceAll('.', ',');
    return '$texto ${unidade ?? ''}'.trim();
  }

  factory MaterialMovement.fromJson(Map<String, dynamic> json) {
    final diario = json['diario'] as Map<String, dynamic>;
    final veiculo = diario['veiculo'] as Map<String, dynamic>;
    final motorista = diario['motorista'] as Map<String, dynamic>;
    final obra = diario['obra'];
    final recebidoPor = json['recebido_por'];

    return MaterialMovement(
      id: (json['id'] as num).toInt(),
      material: json['material'] as String? ?? '',
      numeroMovimentacao: json['numero_movimentacao'] as String? ?? '',
      quantidade: (json['quantidade'] as num?)?.toDouble(),
      unidade: json['unidade'] as String?,
      observacaoCarga: json['observacao_carga'] as String?,
      status: json['status'] as String? ?? '',
      diarioId: (diario['id'] as num).toInt(),
      data: DateTime.parse(diario['data'] as String),
      horaSaida: diario['hora_saida'] as String? ?? '',
      origem: diario['origem'] as String? ?? '',
      destino: diario['destino'] as String? ?? '',
      placa: veiculo['placa'] as String? ?? '',
      modeloVeiculo: veiculo['modelo'] as String? ?? '',
      motorista: motorista['nome'] as String? ?? '',
      obra: obra is Map<String, dynamic> ? obra['nome'] as String? : null,
      recebidoEm: json['recebido_em'] == null
          ? null
          : DateTime.parse(json['recebido_em'] as String),
      recebidoPor: recebidoPor is Map<String, dynamic>
          ? recebidoPor['nome'] as String?
          : null,
      observacaoRecebimento: json['observacao_recebimento'] as String?,
    );
  }
}
