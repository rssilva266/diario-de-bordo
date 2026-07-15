class PendingPoint {
  const PendingPoint({
    required this.clientUuid,
    required this.usuarioId,
    required this.tipoPrevisto,
    required this.fotoPath,
    required this.latitude,
    required this.longitude,
    required this.precisaoMetros,
    required this.capturadoEm,
    required this.dispositivoId,
    required this.salvoEm,
  });

  final String clientUuid;
  final int usuarioId;
  final String tipoPrevisto;
  final String fotoPath;
  final double latitude;
  final double longitude;
  final double precisaoMetros;
  final DateTime capturadoEm;
  final String dispositivoId;
  final DateTime salvoEm;

  Map<String, dynamic> toJson() {
    return {
      'client_uuid': clientUuid,
      'usuario_id': usuarioId,
      'tipo_previsto': tipoPrevisto,
      'foto_path': fotoPath,
      'latitude': latitude,
      'longitude': longitude,
      'precisao_metros': precisaoMetros,
      'capturado_em': capturadoEm.toIso8601String(),
      'dispositivo_id': dispositivoId,
      'salvo_em': salvoEm.toIso8601String(),
    };
  }

  factory PendingPoint.fromJson(Map<String, dynamic> json) {
    return PendingPoint(
      clientUuid: json['client_uuid'] as String,
      usuarioId: json['usuario_id'] as int,
      tipoPrevisto: json['tipo_previsto'] as String,
      fotoPath: json['foto_path'] as String,
      latitude: (json['latitude'] as num).toDouble(),
      longitude: (json['longitude'] as num).toDouble(),
      precisaoMetros: (json['precisao_metros'] as num).toDouble(),
      capturadoEm: DateTime.parse(json['capturado_em'] as String),
      dispositivoId: json['dispositivo_id'] as String,
      salvoEm: DateTime.parse(json['salvo_em'] as String),
    );
  }
}
