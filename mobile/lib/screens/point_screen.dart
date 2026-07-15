import 'dart:async';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:image_picker/image_picker.dart';

import '../controllers/session_controller.dart';
import '../core/theme/app_colors.dart';
import '../models/point_day_state.dart';
import '../models/point_record.dart';
import '../models/pending_point.dart';
import '../services/api_exception.dart';
import '../services/location_service.dart';
import '../services/pending_point_storage.dart';
import '../services/point_service.dart';
import '../widgets/brand_mark.dart';

class PointScreen extends StatefulWidget {
  const PointScreen({required this.sessionController, super.key});

  final SessionController sessionController;

  @override
  State<PointScreen> createState() => _PointScreenState();
}

class _PointScreenState extends State<PointScreen> with WidgetsBindingObserver {
  late final PointService _pointService;
  late final PendingPointStorage _pendingStorage;
  late final Timer _relogio;
  final _imagePicker = ImagePicker();

  DateTime _agora = DateTime.now();
  PointDayState? _estado;
  List<PendingPoint> _pendencias = [];
  bool _carregando = true;
  bool _registrando = false;
  bool _sincronizando = false;
  String? _etapaRegistro;
  String? _erro;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    _pointService = PointService(widget.sessionController.apiClient);
    _pendingStorage = PendingPointStorage();
    _relogio = Timer.periodic(const Duration(seconds: 1), (_) {
      if (mounted) setState(() => _agora = DateTime.now());
    });
    _inicializar();
  }

  Future<void> _inicializar() async {
    await _carregarPendencias();
    if (!mounted || widget.sessionController.usuario == null) return;
    if (_pendencias.isNotEmpty) {
      await _sincronizarPendencias(silencioso: true);
    }
    if (!mounted || widget.sessionController.usuario == null) return;
    await _carregarEstado();
  }

  Future<void> _atualizarTudo() async {
    if (!mounted || widget.sessionController.usuario == null) return;
    await _carregarPendencias();
    if (!mounted || widget.sessionController.usuario == null) return;
    if (_pendencias.isNotEmpty) {
      await _sincronizarPendencias(silencioso: true);
    }
    if (!mounted || widget.sessionController.usuario == null) return;
    await _carregarEstado();
  }

  Future<void> _carregarPendencias() async {
    final usuario = widget.sessionController.usuario;
    if (!mounted || usuario == null) return;
    final usuarioId = usuario.id;
    final itens = await _pendingStorage.listarUsuario(usuarioId);
    if (mounted) setState(() => _pendencias = itens);
  }

  int get _totalEfetivoHoje {
    final registrosServidor = _estado?.registros.length ?? 0;
    final hoje = DateTime.now();
    final pendentesHoje = _pendencias.where((item) {
      final data = item.capturadoEm;
      return data.year == hoje.year &&
          data.month == hoje.month &&
          data.day == hoje.day;
    }).length;

    return (registrosServidor + pendentesHoje).clamp(0, 4).toInt();
  }

  bool get _jornadaEfetivaConcluida => _totalEfetivoHoje >= 4;

  String? get _proximoTipoEfetivo {
    const tipos = ['entrada', 'intervalo', 'retorno', 'saida'];
    return _totalEfetivoHoje < tipos.length
        ? tipos[_totalEfetivoHoje]
        : null;
  }

  String get _proximoTipoDescricaoEfetivo {
    const descricoes = [
      'Entrada',
      'Início do intervalo',
      'Retorno do intervalo',
      'Saída',
    ];
    return _totalEfetivoHoje < descricoes.length
        ? descricoes[_totalEfetivoHoje]
        : 'Jornada concluída';
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    _relogio.cancel();
    super.dispose();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.resumed &&
        !_registrando &&
        !_sincronizando) {
      unawaited(_atualizarTudo());
    }
  }

  Future<void> _carregarEstado() async {
    if (!mounted || widget.sessionController.usuario == null) return;
    setState(() {
      _carregando = true;
      _erro = null;
    });

    try {
      final estado = await _pointService.obterEstado();
      if (mounted) setState(() => _estado = estado);
    } on ApiException catch (erro) {
      if (erro.sessaoExpirada) {
        await widget.sessionController.sessaoExpirada();
        return;
      }
      if (erro.networkFailure && _estado != null) {
        if (mounted) setState(() => _erro = null);
        return;
      }
      if (mounted) setState(() => _erro = erro.message);
    } finally {
      if (mounted) setState(() => _carregando = false);
    }
  }

  Future<void> _sincronizarPendencias({bool silencioso = false}) async {
    if (!mounted ||
        widget.sessionController.usuario == null ||
        _sincronizando ||
        _pendencias.isEmpty) {
      return;
    }

    setState(() => _sincronizando = true);
    var sincronizadas = 0;
    String? erroSincronizacao;

    try {
      for (final pendencia in List<PendingPoint>.from(_pendencias)) {
        if (!await File(pendencia.fotoPath).exists()) {
          erroSincronizacao = (
            'A selfie de uma marcação pendente não foi encontrada no aparelho.'
          );
          break;
        }

        try {
          final estado = await _pointService.registrar(
            clientUuid: pendencia.clientUuid,
            fotoPath: pendencia.fotoPath,
            latitude: pendencia.latitude,
            longitude: pendencia.longitude,
            precisaoMetros: pendencia.precisaoMetros,
            capturadoEm: pendencia.capturadoEm,
            dispositivoId: pendencia.dispositivoId,
          );

          await _pendingStorage.remover(pendencia);
          sincronizadas++;
          if (mounted) setState(() => _estado = estado);
        } on ApiException catch (erro) {
          if (erro.sessaoExpirada) {
            await widget.sessionController.sessaoExpirada();
            return;
          }

          erroSincronizacao = erro.message;
          break;
        }
      }

      await _carregarPendencias();

      if (!mounted || silencioso) return;

      if (sincronizadas > 0) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(
              sincronizadas == 1
                  ? 'Marcação pendente sincronizada.'
                  : '$sincronizadas marcações pendentes sincronizadas.',
            ),
            backgroundColor: AppColors.success,
          ),
        );
      } else if (erroSincronizacao != null) {
        _mostrarErro(erroSincronizacao);
      }
    } finally {
      if (mounted) setState(() => _sincronizando = false);
    }
  }

  Future<void> _iniciarRegistro() async {
    if (_estado == null || _jornadaEfetivaConcluida) return;

    if (_pendencias.isNotEmpty) {
      await _sincronizarPendencias(silencioso: true);
      if (!mounted || widget.sessionController.usuario == null) return;
    }

    final continuar = await _mostrarOrientacaoSelfie();
    if (continuar != true || !mounted) return;

    setState(() {
      _registrando = true;
      _etapaRegistro = 'Obtendo sua localização...';
    });

    try {
      final posicao = await LocationService.obterAtual();
      if (!mounted) return;

      setState(() => _etapaRegistro = 'Abra a câmera para tirar a selfie...');

      final foto = await _imagePicker.pickImage(
        source: ImageSource.camera,
        preferredCameraDevice: CameraDevice.front,
        imageQuality: 88,
        maxWidth: 1600,
      );

      if (foto == null || !mounted) return;

      final capturadoEm = DateTime.now();
      final confirmou = await _confirmarRegistro(
        foto: foto,
        precisaoMetros: posicao.accuracy,
      );

      if (confirmou != true || !mounted) return;

      setState(() => _etapaRegistro = 'Enviando o registro...');

      final dispositivoId = await widget.sessionController.obterDispositivoId();
      final clientUuid = _pointService.gerarClientUuid(
        dispositivoId,
        capturadoEm,
      );
      final tipoPrevisto = _proximoTipoEfetivo ?? 'registro';

      if (_pendencias.isNotEmpty) {
        await _salvarMarcacaoPendente(
          clientUuid: clientUuid,
          tipoPrevisto: tipoPrevisto,
          fotoPath: foto.path,
          latitude: posicao.latitude,
          longitude: posicao.longitude,
          precisaoMetros: posicao.accuracy,
          capturadoEm: capturadoEm,
          dispositivoId: dispositivoId,
          mensagem: (
            'Há uma marcação anterior aguardando envio. '
            'Esta também foi salva no aparelho e será enviada na ordem correta.'
          ),
        );
        return;
      }

      PointDayState? estado;

      try {
        estado = await _pointService.registrar(
          clientUuid: clientUuid,
          fotoPath: foto.path,
          latitude: posicao.latitude,
          longitude: posicao.longitude,
          precisaoMetros: posicao.accuracy,
          capturadoEm: capturadoEm,
          dispositivoId: dispositivoId,
        );
      } on ApiException catch (erro) {
        if (!erro.networkFailure) rethrow;

        await _salvarMarcacaoPendente(
          clientUuid: clientUuid,
          tipoPrevisto: tipoPrevisto,
          fotoPath: foto.path,
          latitude: posicao.latitude,
          longitude: posicao.longitude,
          precisaoMetros: posicao.accuracy,
          capturadoEm: capturadoEm,
          dispositivoId: dispositivoId,
          mensagem: (
            'Sem conexão. A marcação foi salva no aparelho e será '
            'sincronizada depois.'
          ),
        );
        return;
      }

      if (!mounted) return;
      setState(() => _estado = estado);
      await HapticFeedback.mediumImpact();
      if (!mounted) return;

      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Ponto registrado com sucesso.'),
          backgroundColor: AppColors.success,
        ),
      );
    } on ApiException catch (erro) {
      if (erro.sessaoExpirada) {
        await widget.sessionController.sessaoExpirada();
        return;
      }
      if (mounted) _mostrarErro(erro.message);
    } catch (_) {
      if (mounted) {
        _mostrarErro('Não foi possível registrar o ponto. Tente novamente.');
      }
    } finally {
      if (mounted) {
        setState(() {
          _registrando = false;
          _etapaRegistro = null;
        });
      }
    }
  }

  Future<void> _salvarMarcacaoPendente({
    required String clientUuid,
    required String tipoPrevisto,
    required String fotoPath,
    required double latitude,
    required double longitude,
    required double precisaoMetros,
    required DateTime capturadoEm,
    required String dispositivoId,
    required String mensagem,
  }) async {
    await _pendingStorage.adicionar(
      clientUuid: clientUuid,
      usuarioId: widget.sessionController.usuario!.id,
      tipoPrevisto: tipoPrevisto,
      fotoPath: fotoPath,
      latitude: latitude,
      longitude: longitude,
      precisaoMetros: precisaoMetros,
      capturadoEm: capturadoEm,
      dispositivoId: dispositivoId,
    );
    await _carregarPendencias();

    if (!mounted) return;
    await HapticFeedback.mediumImpact();
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(mensagem),
        backgroundColor: AppColors.warning,
        duration: const Duration(seconds: 5),
      ),
    );
  }

  Future<bool?> _mostrarOrientacaoSelfie() {
    return showDialog<bool>(
      context: context,
      builder: (context) {
        return AlertDialog(
          title: const Text('Antes de registrar'),
          content: const Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              _InstructionRow(
                icon: Icons.face_outlined,
                text: 'Mantenha o rosto centralizado e completamente visível.',
              ),
              SizedBox(height: 13),
              _InstructionRow(
                icon: Icons.wb_sunny_outlined,
                text: 'Procure um local bem iluminado.',
              ),
              SizedBox(height: 13),
              _InstructionRow(
                icon: Icons.location_on_outlined,
                text: 'Aguarde a localização ficar precisa antes da selfie.',
              ),
            ],
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(context, false),
              child: const Text('Cancelar'),
            ),
            FilledButton.icon(
              onPressed: () => Navigator.pop(context, true),
              icon: const Icon(Icons.camera_alt_outlined),
              label: const Text('Continuar'),
            ),
          ],
        );
      },
    );
  }

  Future<bool?> _confirmarRegistro({
    required XFile foto,
    required double precisaoMetros,
  }) {
    final tipo = _proximoTipoDescricaoEfetivo;

    return showDialog<bool>(
      context: context,
      builder: (context) {
        return AlertDialog(
          title: Text('Confirmar $tipo'),
          content: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              ClipRRect(
                borderRadius: BorderRadius.circular(8),
                child: AspectRatio(
                  aspectRatio: 4 / 3,
                  child: Image.file(
                    File(foto.path),
                    fit: BoxFit.cover,
                  ),
                ),
              ),
              const SizedBox(height: 14),
              Text(
                'Horário: ${_formatarHorario(DateTime.now())}',
                style: const TextStyle(fontWeight: FontWeight.w700),
              ),
              const SizedBox(height: 5),
              Text(
                'Precisão do GPS: ${precisaoMetros.toStringAsFixed(0)} m',
                style: TextStyle(
                  color: precisaoMetros > 50
                      ? AppColors.warning
                      : AppColors.muted,
                  fontWeight: precisaoMetros > 50
                      ? FontWeight.w700
                      : FontWeight.w400,
                ),
              ),
              if (precisaoMetros > 50) ...[
                const SizedBox(height: 5),
                const Text(
                  'Sinal de GPS fraco. Aguarde alguns segundos em uma área aberta se puder.',
                  style: TextStyle(color: AppColors.warning, fontSize: 12),
                ),
              ],
            ],
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(context, false),
              child: const Text('Refazer'),
            ),
            FilledButton(
              onPressed: () => Navigator.pop(context, true),
              child: const Text('Confirmar'),
            ),
          ],
        );
      },
    );
  }

  void _mostrarErro(String mensagem) {
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(mensagem),
        backgroundColor: AppColors.danger,
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final usuario = widget.sessionController.usuario!;

    return Scaffold(
      appBar: AppBar(
        titleSpacing: 20,
        bottom: const PreferredSize(
          preferredSize: Size.fromHeight(1),
          child: Divider(height: 1, color: AppColors.border),
        ),
        title: const Row(
          children: [
            BrandMark(size: 36, compact: true),
            SizedBox(width: 12),
            Text(
              'Diário de Bordo',
              style: TextStyle(fontSize: 18, fontWeight: FontWeight.w700),
            ),
          ],
        ),
        actions: [
          PopupMenuButton<String>(
            tooltip: 'Opções da conta',
            onSelected: (value) {
              if (value == 'sair') widget.sessionController.logout();
            },
            itemBuilder: (context) => const [
              PopupMenuItem(
                value: 'sair',
                child: Row(
                  children: [
                    Icon(Icons.logout, size: 20),
                    SizedBox(width: 10),
                    Text('Sair'),
                  ],
                ),
              ),
            ],
            icon: CircleAvatar(
              radius: 17,
              backgroundColor: AppColors.primary,
              child: Text(
                usuario.inicial,
                style: const TextStyle(
                  color: Colors.white,
                  fontWeight: FontWeight.w700,
                ),
              ),
            ),
          ),
          const SizedBox(width: 8),
        ],
      ),
      body: RefreshIndicator(
        onRefresh: _atualizarTudo,
        child: ListView(
          physics: const AlwaysScrollableScrollPhysics(),
          padding: const EdgeInsets.fromLTRB(20, 24, 20, 36),
          children: [
            Text(
              'Olá, ${usuario.primeiroNome}',
              style: Theme.of(context).textTheme.headlineSmall?.copyWith(
                    color: AppColors.ink,
                    fontWeight: FontWeight.w800,
                  ),
            ),
            const SizedBox(height: 4),
            Text(
              usuario.empresa,
              style: const TextStyle(color: AppColors.muted, fontSize: 14),
            ),
            const SizedBox(height: 3),
            Text(
              _formatarDataCompleta(_agora),
              style: const TextStyle(color: AppColors.muted, fontSize: 14),
            ),
            const SizedBox(height: 24),
            if (_carregando)
              const Padding(
                padding: EdgeInsets.symmetric(vertical: 80),
                child: Center(child: CircularProgressIndicator()),
              )
            else if (_erro != null)
              _ErrorCard(message: _erro!, onRetry: _carregarEstado)
            else if (_estado != null) ...[
              _PointCard(
                agora: _agora,
                estado: _estado!,
                totalConcluido: _totalEfetivoHoje,
                jornadaConcluida: _jornadaEfetivaConcluida,
                proximoTipoDescricao: _proximoTipoDescricaoEfetivo,
                registrando: _registrando,
                etapaRegistro: _etapaRegistro,
                onRegister: _iniciarRegistro,
              ),
              if (_pendencias.isNotEmpty) ...[
                const SizedBox(height: 14),
                _SyncCard(
                  pendencias: _pendencias,
                  sincronizando: _sincronizando,
                  onSync: () => _sincronizarPendencias(),
                ),
              ],
              const SizedBox(height: 24),
              const Text(
                'Marcações de hoje',
                style: TextStyle(
                  color: AppColors.ink,
                  fontSize: 18,
                  fontWeight: FontWeight.w800,
                ),
              ),
              const SizedBox(height: 12),
              _RecordsCard(registros: _estado!.registros),
            ],
          ],
        ),
      ),
    );
  }
}

class _InstructionRow extends StatelessWidget {
  const _InstructionRow({required this.icon, required this.text});

  final IconData icon;
  final String text;

  @override
  Widget build(BuildContext context) {
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Container(
          width: 34,
          height: 34,
          decoration: BoxDecoration(
            color: AppColors.primarySoft,
            borderRadius: BorderRadius.circular(5),
          ),
          child: Icon(icon, size: 19, color: AppColors.primaryDark),
        ),
        const SizedBox(width: 11),
        Expanded(
          child: Padding(
            padding: const EdgeInsets.only(top: 6),
            child: Text(text),
          ),
        ),
      ],
    );
  }
}

class _PointCard extends StatelessWidget {
  const _PointCard({
    required this.agora,
    required this.estado,
    required this.totalConcluido,
    required this.jornadaConcluida,
    required this.proximoTipoDescricao,
    required this.registrando,
    required this.etapaRegistro,
    required this.onRegister,
  });

  final DateTime agora;
  final PointDayState estado;
  final int totalConcluido;
  final bool jornadaConcluida;
  final String proximoTipoDescricao;
  final bool registrando;
  final String? etapaRegistro;
  final VoidCallback onRegister;

  @override
  Widget build(BuildContext context) {
    final concluida = jornadaConcluida;
    final proximo = proximoTipoDescricao;

    return Container(
      decoration: BoxDecoration(
        gradient: const LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: [AppColors.navy, AppColors.navySecondary],
        ),
        border: Border.all(color: const Color(0x2E94A3B8)),
        borderRadius: BorderRadius.circular(12),
        boxShadow: const [
          BoxShadow(
            color: Color(0x280F172A),
            blurRadius: 24,
            offset: Offset(0, 10),
          ),
        ],
      ),
      child: Padding(
        padding: const EdgeInsets.all(22),
        child: Column(
          children: [
            Row(
              children: [
                const Icon(Icons.access_time, color: AppColors.lightBlue),
                const SizedBox(width: 9),
                const Expanded(
                  child: Text(
                    'Registro de ponto',
                    style: TextStyle(
                      color: Colors.white,
                      fontSize: 17,
                      fontWeight: FontWeight.w700,
                    ),
                  ),
                ),
                Text(
                  '$totalConcluido/4',
                  style: const TextStyle(
                    color: AppColors.sidebarText,
                    fontWeight: FontWeight.w700,
                  ),
                ),
              ],
            ),
            const SizedBox(height: 18),
            _PointProgress(totalConcluido: totalConcluido),
            const SizedBox(height: 22),
            Text(
              _formatarHorario(agora),
              style: const TextStyle(
                color: Colors.white,
                fontSize: 44,
                height: 1,
                fontWeight: FontWeight.w800,
                letterSpacing: -1.5,
                fontFeatures: [FontFeature.tabularFigures()],
              ),
            ),
            const SizedBox(height: 12),
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 7),
              decoration: BoxDecoration(
                color: concluida
                    ? const Color(0x2422C55E)
                    : const Color(0xFF1E293B),
                borderRadius: BorderRadius.circular(6),
                border: Border.all(
                  color: concluida
                      ? const Color(0x6622C55E)
                      : const Color(0xFF334155),
                ),
              ),
              child: Text(
                proximo,
                style: TextStyle(
                  color: concluida ? AppColors.success : Colors.white,
                  fontWeight: FontWeight.w700,
                ),
              ),
            ),
            if (estado.localTrabalho != null) ...[
              const SizedBox(height: 12),
              Row(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  const Icon(
                    Icons.location_on_outlined,
                    size: 18,
                    color: AppColors.sidebarText,
                  ),
                  const SizedBox(width: 5),
                  Flexible(
                    child: Text(
                      estado.localTrabalho!,
                      overflow: TextOverflow.ellipsis,
                      style: const TextStyle(color: AppColors.sidebarText),
                    ),
                  ),
                ],
              ),
            ],
            const SizedBox(height: 22),
            FilledButton.icon(
              onPressed: concluida || registrando ? null : onRegister,
              icon: registrando
                  ? const SizedBox(
                      width: 19,
                      height: 19,
                      child: CircularProgressIndicator(
                        color: Colors.white,
                        strokeWidth: 2.3,
                      ),
                    )
                  : Icon(concluida ? Icons.check_circle : Icons.camera_alt_outlined),
              label: Text(
                registrando
                    ? etapaRegistro ?? 'Preparando...'
                    : concluida
                        ? 'Jornada concluída'
                        : 'Registrar $proximo',
              ),
            ),
            if (!concluida) ...[
              const SizedBox(height: 11),
              const Text(
                'Será necessário permitir o GPS e tirar uma selfie.',
                textAlign: TextAlign.center,
                style: TextStyle(color: AppColors.sidebarText, fontSize: 12),
              ),
            ],
          ],
        ),
      ),
    );
  }
}

class _PointProgress extends StatelessWidget {
  const _PointProgress({required this.totalConcluido});

  final int totalConcluido;

  static const _etapas = [
    ('Entrada', AppColors.success),
    ('Intervalo', AppColors.warning),
    ('Retorno', Color(0xFF3B82F6)),
    ('Saída', AppColors.danger),
  ];

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        for (var index = 0; index < _etapas.length; index++) ...[
          Expanded(
            child: _ProgressStep(
              label: _etapas[index].$1,
              color: _etapas[index].$2,
              completed: index < totalConcluido,
              current: index == totalConcluido,
            ),
          ),
          if (index < _etapas.length - 1)
            Container(
              width: 12,
              height: 1,
              color: index < totalConcluido
                  ? _etapas[index].$2
                  : const Color(0xFF475569),
            ),
        ],
      ],
    );
  }
}

class _ProgressStep extends StatelessWidget {
  const _ProgressStep({
    required this.label,
    required this.color,
    required this.completed,
    required this.current,
  });

  final String label;
  final Color color;
  final bool completed;
  final bool current;

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        Container(
          width: 28,
          height: 28,
          decoration: BoxDecoration(
            shape: BoxShape.circle,
            color: completed ? color : Colors.transparent,
            border: Border.all(
              color: completed || current ? color : const Color(0xFF64748B),
              width: current ? 2 : 1,
            ),
          ),
          child: Icon(
            completed ? Icons.check : Icons.circle,
            size: completed ? 16 : 8,
            color: completed
                ? Colors.white
                : current
                    ? color
                    : const Color(0xFF64748B),
          ),
        ),
        const SizedBox(height: 6),
        Text(
          label,
          maxLines: 1,
          overflow: TextOverflow.ellipsis,
          style: TextStyle(
            color: completed || current
                ? Colors.white
                : const Color(0xFF94A3B8),
            fontSize: 10,
            fontWeight: current ? FontWeight.w700 : FontWeight.w500,
          ),
        ),
      ],
    );
  }
}

class _SyncCard extends StatelessWidget {
  const _SyncCard({
    required this.pendencias,
    required this.sincronizando,
    required this.onSync,
  });

  final List<PendingPoint> pendencias;
  final bool sincronizando;
  final Future<void> Function() onSync;

  @override
  Widget build(BuildContext context) {
    final quantidade = pendencias.length;
    final primeira = pendencias.first;

    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: const Color(0xFFFFF7E6),
        border: Border.all(color: const Color(0x66F59E0B)),
        borderRadius: BorderRadius.circular(6),
      ),
      child: Row(
        children: [
          const Icon(Icons.cloud_upload_outlined, color: AppColors.warning),
          const SizedBox(width: 11),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  quantidade == 1
                      ? '1 marcação aguardando envio'
                      : '$quantidade marcações aguardando envio',
                  style: const TextStyle(
                    color: AppColors.ink,
                    fontWeight: FontWeight.w700,
                  ),
                ),
                const SizedBox(height: 3),
                Text(
                  'Salva no aparelho desde ${_formatarHorarioCurto(primeira.salvoEm)}',
                  style: const TextStyle(color: AppColors.muted, fontSize: 12),
                ),
              ],
            ),
          ),
          const SizedBox(width: 8),
          IconButton(
            tooltip: 'Sincronizar agora',
            onPressed: sincronizando ? null : onSync,
            icon: sincronizando
                ? const SizedBox(
                    width: 19,
                    height: 19,
                    child: CircularProgressIndicator(strokeWidth: 2.2),
                  )
                : const Icon(Icons.sync, color: AppColors.primary),
          ),
        ],
      ),
    );
  }
}

class _RecordsCard extends StatelessWidget {
  const _RecordsCard({required this.registros});

  final List<PointRecord> registros;

  @override
  Widget build(BuildContext context) {
    if (registros.isEmpty) {
      return const Card(
        child: Padding(
          padding: EdgeInsets.symmetric(horizontal: 22, vertical: 28),
          child: Row(
            children: [
              Icon(Icons.schedule, color: AppColors.primary),
              SizedBox(width: 12),
              Expanded(
                child: Text(
                  'Nenhuma marcação registrada hoje.',
                  style: TextStyle(color: AppColors.muted),
                ),
              ),
            ],
          ),
        ),
      );
    }

    return Card(
      child: Column(
        children: [
          for (var index = 0; index < registros.length; index++) ...[
            _RecordTile(record: registros[index]),
            if (index < registros.length - 1)
              const Divider(height: 1, indent: 64),
          ],
        ],
      ),
    );
  }
}

class _RecordTile extends StatelessWidget {
  const _RecordTile({required this.record});

  final PointRecord record;

  @override
  Widget build(BuildContext context) {
    final (cor, icone, localizacao) = switch (record.dentroGeocerca) {
      true => (AppColors.success, Icons.location_on, 'Dentro da área'),
      false => (AppColors.danger, Icons.location_off, 'Fora da área'),
      null => (AppColors.muted, Icons.location_searching, 'Local não validado'),
    };

    return ListTile(
      minVerticalPadding: 13,
      leading: Container(
        width: 40,
        height: 40,
        decoration: BoxDecoration(
          color: AppColors.primarySoft,
          borderRadius: BorderRadius.circular(6),
        ),
        child: Icon(Icons.fingerprint, color: _corTipo(record.tipo)),
      ),
      title: Row(
        children: [
          Expanded(
            child: Text(
              record.tipoDescricao,
              style: const TextStyle(
                color: AppColors.ink,
                fontWeight: FontWeight.w700,
              ),
            ),
          ),
          Text(
            _formatarHorarioCurto(record.registradoEm),
            style: const TextStyle(
              color: AppColors.ink,
              fontWeight: FontWeight.w800,
              fontFeatures: [FontFeature.tabularFigures()],
            ),
          ),
        ],
      ),
      subtitle: Padding(
        padding: const EdgeInsets.only(top: 4),
        child: Row(
          children: [
            Icon(icone, size: 15, color: cor),
            const SizedBox(width: 4),
            Text(localizacao, style: TextStyle(color: cor, fontSize: 12)),
          ],
        ),
      ),
    );
  }
}

class _ErrorCard extends StatelessWidget {
  const _ErrorCard({required this.message, required this.onRetry});

  final String message;
  final Future<void> Function() onRetry;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(22),
        child: Column(
          children: [
            const Icon(Icons.warning_amber_rounded, color: AppColors.danger, size: 34),
            const SizedBox(height: 12),
            Text(message, textAlign: TextAlign.center),
            const SizedBox(height: 14),
            TextButton.icon(
              onPressed: onRetry,
              icon: const Icon(Icons.refresh),
              label: const Text('Tentar novamente'),
            ),
          ],
        ),
      ),
    );
  }
}

Color _corTipo(String tipo) {
  return switch (tipo) {
    'entrada' => AppColors.success,
    'intervalo' => AppColors.warning,
    'retorno' => const Color(0xFF3B82F6),
    'saida' => AppColors.danger,
    _ => AppColors.primary,
  };
}

String _doisDigitos(int value) => value.toString().padLeft(2, '0');

String _formatarHorario(DateTime dateTime) {
  return '${_doisDigitos(dateTime.hour)}:${_doisDigitos(dateTime.minute)}:${_doisDigitos(dateTime.second)}';
}

String _formatarHorarioCurto(DateTime dateTime) {
  return '${_doisDigitos(dateTime.hour)}:${_doisDigitos(dateTime.minute)}';
}

String _formatarDataCompleta(DateTime dateTime) {
  const dias = [
    'segunda-feira',
    'terça-feira',
    'quarta-feira',
    'quinta-feira',
    'sexta-feira',
    'sábado',
    'domingo',
  ];
  const meses = [
    'janeiro',
    'fevereiro',
    'março',
    'abril',
    'maio',
    'junho',
    'julho',
    'agosto',
    'setembro',
    'outubro',
    'novembro',
    'dezembro',
  ];

  return '${dias[dateTime.weekday - 1]}, ${dateTime.day} de ${meses[dateTime.month - 1]}';
}
