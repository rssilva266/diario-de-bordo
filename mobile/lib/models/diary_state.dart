class DiaryDriver {
  const DiaryDriver({required this.id, required this.nome});

  final int id;
  final String nome;

  factory DiaryDriver.fromJson(Map<String, dynamic> json) {
    return DiaryDriver(
      id: (json['id'] as num).toInt(),
      nome: json['nome'] as String? ?? '',
    );
  }
}

class DiaryVehicle {
  const DiaryVehicle({
    required this.id,
    required this.placa,
    required this.modelo,
    required this.kmAtual,
    required this.combustivel,
    this.obraId,
  });

  final int id;
  final String placa;
  final String modelo;
  final int kmAtual;
  final String combustivel;
  final int? obraId;

  factory DiaryVehicle.fromJson(Map<String, dynamic> json) {
    return DiaryVehicle(
      id: (json['id'] as num).toInt(),
      placa: json['placa'] as String? ?? '',
      modelo: json['modelo'] as String? ?? '',
      kmAtual: (json['km_atual'] as num?)?.toInt() ?? 0,
      combustivel: json['combustivel'] as String? ?? '',
      obraId: (json['obra_id'] as num?)?.toInt(),
    );
  }
}

class DiaryWorkSite {
  const DiaryWorkSite({
    required this.id,
    required this.codigo,
    required this.nome,
  });

  final int id;
  final String codigo;
  final String nome;

  String get descricao => codigo.isEmpty ? nome : '$codigo — $nome';

  factory DiaryWorkSite.fromJson(Map<String, dynamic> json) {
    return DiaryWorkSite(
      id: (json['id'] as num).toInt(),
      codigo: json['codigo'] as String? ?? '',
      nome: json['nome'] as String? ?? '',
    );
  }
}

class DiaryEntry {
  const DiaryEntry({
    required this.id,
    required this.data,
    required this.horaSaida,
    required this.kmInicial,
    required this.origem,
    required this.destino,
    required this.status,
    required this.veiculo,
    required this.motorista,
    required this.houveAbastecimento,
    this.horaChegada,
    this.kmFinal,
    this.kmPercorrida,
    this.finalidade,
    this.ocorrencias,
    this.obra,
  });

  final int id;
  final DateTime data;
  final String horaSaida;
  final String? horaChegada;
  final int kmInicial;
  final int? kmFinal;
  final int? kmPercorrida;
  final String origem;
  final String destino;
  final String? finalidade;
  final String? ocorrencias;
  final String status;
  final DiaryVehicle veiculo;
  final DiaryDriver motorista;
  final DiaryWorkSite? obra;
  final bool houveAbastecimento;

  bool get emAndamento => status == 'Em andamento';

  factory DiaryEntry.fromJson(Map<String, dynamic> json) {
    final obraJson = json['obra'];

    return DiaryEntry(
      id: (json['id'] as num).toInt(),
      data: DateTime.parse(json['data'] as String),
      horaSaida: json['hora_saida'] as String? ?? '',
      horaChegada: json['hora_chegada'] as String?,
      kmInicial: (json['km_inicial'] as num).toInt(),
      kmFinal: (json['km_final'] as num?)?.toInt(),
      kmPercorrida: (json['km_percorrida'] as num?)?.toInt(),
      origem: json['origem'] as String? ?? '',
      destino: json['destino'] as String? ?? '',
      finalidade: json['finalidade'] as String?,
      ocorrencias: json['ocorrencias'] as String?,
      status: json['status'] as String? ?? '',
      veiculo: DiaryVehicle.fromJson(
        json['veiculo'] as Map<String, dynamic>,
      ),
      motorista: DiaryDriver.fromJson(
        json['motorista'] as Map<String, dynamic>,
      ),
      obra: obraJson is Map<String, dynamic>
          ? DiaryWorkSite.fromJson(obraJson)
          : null,
      houveAbastecimento: json['houve_abastecimento'] as bool? ?? false,
    );
  }
}

class DiaryState {
  const DiaryState({
    required this.motorista,
    required this.obras,
    required this.podeIniciar,
    required this.recentes,
    this.veiculo,
    this.diarioEmAndamento,
    this.bloqueio,
  });

  final DiaryDriver motorista;
  final DiaryVehicle? veiculo;
  final List<DiaryWorkSite> obras;
  final DiaryEntry? diarioEmAndamento;
  final bool podeIniciar;
  final String? bloqueio;
  final List<DiaryEntry> recentes;

  factory DiaryState.fromJson(Map<String, dynamic> json) {
    final veiculoJson = json['veiculo'];
    final diarioJson = json['diario_em_andamento'];

    return DiaryState(
      motorista: DiaryDriver.fromJson(
        json['motorista'] as Map<String, dynamic>,
      ),
      veiculo: veiculoJson is Map<String, dynamic>
          ? DiaryVehicle.fromJson(veiculoJson)
          : null,
      obras: (json['obras'] as List<dynamic>? ?? const [])
          .map(
            (item) => DiaryWorkSite.fromJson(item as Map<String, dynamic>),
          )
          .toList(growable: false),
      diarioEmAndamento: diarioJson is Map<String, dynamic>
          ? DiaryEntry.fromJson(diarioJson)
          : null,
      podeIniciar: json['pode_iniciar'] as bool? ?? false,
      bloqueio: json['bloqueio'] as String?,
      recentes: (json['recentes'] as List<dynamic>? ?? const [])
          .map(
            (item) => DiaryEntry.fromJson(item as Map<String, dynamic>),
          )
          .toList(growable: false),
    );
  }
}
