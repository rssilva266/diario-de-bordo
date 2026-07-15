class PointRecord {
  const PointRecord({
    required this.id,
    required this.tipo,
    required this.tipoDescricao,
    required this.registradoEm,
    this.observacao,
    this.latitude,
    this.longitude,
    this.precisaoMetros,
    this.dentroGeocerca,
    this.distanciaLocalMetros,
  });

  final int id;
  final String tipo;
  final String tipoDescricao;
  final DateTime registradoEm;
  final String? observacao;
  final double? latitude;
  final double? longitude;
  final double? precisaoMetros;
  final bool? dentroGeocerca;
  final double? distanciaLocalMetros;

  factory PointRecord.fromJson(Map<String, dynamic> json) {
    return PointRecord(
      id: json['id'] as int,
      tipo: json['tipo'] as String,
      tipoDescricao: json['tipo_descricao'] as String? ?? json['tipo'] as String,
      registradoEm: DateTime.parse(
        (json['capturado_em'] ?? json['registrado_em']) as String,
      ).toLocal(),
      observacao: json['observacao'] as String?,
      latitude: (json['latitude'] as num?)?.toDouble(),
      longitude: (json['longitude'] as num?)?.toDouble(),
      precisaoMetros: (json['precisao_metros'] as num?)?.toDouble(),
      dentroGeocerca: json['dentro_geocerca'] as bool?,
      distanciaLocalMetros: (json['distancia_local_metros'] as num?)?.toDouble(),
    );
  }
}
