import 'dart:convert';
import 'dart:io';

import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:path_provider/path_provider.dart';

import '../models/pending_point.dart';

class PendingPointStorage {
  static const _storageKey = 'mobile_pending_points_v1';
  static const _storage = FlutterSecureStorage();

  Future<List<PendingPoint>> listarUsuario(int usuarioId) async {
    final todos = await _listarTodos();
    final itens = todos
        .where((item) => item.usuarioId == usuarioId)
        .toList()
      ..sort((a, b) => a.capturadoEm.compareTo(b.capturadoEm));
    return itens;
  }

  Future<PendingPoint> adicionar({
    required String clientUuid,
    required int usuarioId,
    required String tipoPrevisto,
    required String fotoPath,
    required double latitude,
    required double longitude,
    required double precisaoMetros,
    required DateTime capturadoEm,
    required String dispositivoId,
  }) async {
    final diretorioBase = await getApplicationDocumentsDirectory();
    final diretorio = Directory(
      '${diretorioBase.path}${Platform.pathSeparator}pontos_pendentes',
    );
    await diretorio.create(recursive: true);

    final fotoPersistente = File(
      '${diretorio.path}${Platform.pathSeparator}$clientUuid.jpg',
    );
    await File(fotoPath).copy(fotoPersistente.path);

    final pendencia = PendingPoint(
      clientUuid: clientUuid,
      usuarioId: usuarioId,
      tipoPrevisto: tipoPrevisto,
      fotoPath: fotoPersistente.path,
      latitude: latitude,
      longitude: longitude,
      precisaoMetros: precisaoMetros,
      capturadoEm: capturadoEm,
      dispositivoId: dispositivoId,
      salvoEm: DateTime.now(),
    );

    final todos = await _listarTodos();
    todos.removeWhere((item) => item.clientUuid == clientUuid);
    todos.add(pendencia);
    await _salvarTodos(todos);
    return pendencia;
  }

  Future<void> remover(PendingPoint pendencia) async {
    final todos = await _listarTodos();
    todos.removeWhere(
      (item) => item.clientUuid == pendencia.clientUuid,
    );
    await _salvarTodos(todos);

    final foto = File(pendencia.fotoPath);
    if (await foto.exists()) await foto.delete();
  }

  Future<List<PendingPoint>> _listarTodos() async {
    final texto = await _storage.read(key: _storageKey);
    if (texto == null || texto.isEmpty) return [];

    try {
      final itens = jsonDecode(texto) as List<dynamic>;
      return itens
          .map(
            (item) => PendingPoint.fromJson(
              item as Map<String, dynamic>,
            ),
          )
          .toList();
    } catch (_) {
      return [];
    }
  }

  Future<void> _salvarTodos(List<PendingPoint> itens) {
    return _storage.write(
      key: _storageKey,
      value: jsonEncode(
        itens.map((item) => item.toJson()).toList(),
      ),
    );
  }
}
