import 'dart:async';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:image_picker/image_picker.dart';
import 'package:uuid/uuid.dart';

import '../controllers/session_controller.dart';
import '../core/theme/app_colors.dart';
import '../models/material_movement.dart';
import '../services/api_exception.dart';
import '../services/location_service.dart';
import '../services/material_service.dart';
import '../widgets/brand_mark.dart';

class MaterialScreen extends StatefulWidget {
  const MaterialScreen({
    required this.sessionController,
    required this.historico,
    super.key,
  });

  final SessionController sessionController;
  final bool historico;

  @override
  State<MaterialScreen> createState() => _MaterialScreenState();
}

class _MaterialScreenState extends State<MaterialScreen>
    with WidgetsBindingObserver {
  late final MaterialService _service;
  final _buscaController = TextEditingController();
  Timer? _atualizacaoAutomatica;
  List<MaterialMovement> _itens = const [];
  bool _carregando = true;
  bool _recebendo = false;
  String? _erro;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    _service = MaterialService(widget.sessionController.apiClient);
    _carregar();

    _atualizacaoAutomatica = Timer.periodic(
      const Duration(seconds: 20),
      (_) => _carregar(silencioso: true),
    );
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.resumed) {
      unawaited(_carregar(silencioso: true));
    }
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    _atualizacaoAutomatica?.cancel();
    _buscaController.dispose();
    super.dispose();
  }

  Future<void> _carregar({bool silencioso = false}) async {
    if (!mounted || _recebendo) return;

    if (!silencioso) {
      setState(() {
        _carregando = true;
        _erro = null;
      });
    }

    try {
      final itens = widget.historico
          ? await _service.listarHistorico()
          : await _service.listarPendentes(
              busca: _buscaController.text,
            );
      if (mounted) {
        setState(() {
          _itens = itens;
          _erro = null;
        });
      }
    } on ApiException catch (erro) {
      if (erro.sessaoExpirada) {
        await widget.sessionController.sessaoExpirada();
        return;
      }
      if (mounted && !silencioso) setState(() => _erro = erro.message);
    } catch (_) {
      if (mounted && !silencioso) {
        setState(() => _erro = 'Não foi possível carregar as movimentações.');
      }
    } finally {
      if (mounted && !silencioso) setState(() => _carregando = false);
    }
  }

  Future<void> _abrirRecebimento(MaterialMovement item) async {
    final dados = await showModalBottomSheet<_ReceiptData>(
      context: context,
      isScrollControlled: true,
      useSafeArea: true,
      backgroundColor: Colors.white,
      builder: (context) => _ReceiptSheet(item: item),
    );

    if (dados == null || !mounted) return;
    setState(() => _recebendo = true);

    double? latitude;
    double? longitude;
    double? precisao;

    try {
      final posicao = await LocationService.obterAtual();
      latitude = posicao.latitude;
      longitude = posicao.longitude;
      precisao = posicao.accuracy;
    } catch (_) {
      // O recebimento continua com foto e horário quando o GPS não está disponível.
    }

    try {
      await _service.receber(
        movimentacaoId: item.id,
        clientUuid: const Uuid().v4(),
        fotoPath: dados.fotoPath,
        comRessalva: dados.comRessalva,
        observacao: dados.observacao,
        latitude: latitude,
        longitude: longitude,
        precisaoMetros: precisao,
      );

      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(
            dados.comRessalva
                ? 'Material recebido com ressalva.'
                : 'Material recebido com sucesso.',
          ),
          backgroundColor: dados.comRessalva
              ? AppColors.warning
              : AppColors.success,
        ),
      );
      await _carregar();
    } on ApiException catch (erro) {
      if (erro.sessaoExpirada) {
        await widget.sessionController.sessaoExpirada();
        return;
      }
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(erro.message),
            backgroundColor: AppColors.danger,
          ),
        );
      }
      if (erro.statusCode == 409) await _carregar();
    } finally {
      if (mounted) setState(() => _recebendo = false);
    }
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
        title: Row(
          children: [
            const BrandMark(size: 36, compact: true),
            const SizedBox(width: 12),
            Text(
              widget.historico ? 'Histórico' : 'Recebimentos',
              style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w700),
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
      body: Stack(
        children: [
          RefreshIndicator(
            onRefresh: _carregar,
            child: ListView(
              physics: const AlwaysScrollableScrollPhysics(),
              padding: const EdgeInsets.fromLTRB(20, 22, 20, 36),
              children: [
                Text(
                  widget.historico ? 'Seus recebimentos' : 'Cargas em trânsito',
                  style: Theme.of(context).textTheme.headlineSmall?.copyWith(
                        color: AppColors.ink,
                        fontWeight: FontWeight.w800,
                      ),
                ),
                const SizedBox(height: 4),
                Text(
                  widget.historico
                      ? 'Comprovantes confirmados pelo seu usuário.'
                      : 'Localize a viagem pela placa e confirme a descarga.',
                  style: const TextStyle(color: AppColors.muted),
                ),
                if (!widget.historico) ...[
                  const SizedBox(height: 18),
                  TextField(
                    controller: _buscaController,
                    textInputAction: TextInputAction.search,
                    textCapitalization: TextCapitalization.characters,
                    onSubmitted: (_) => _carregar(),
                    decoration: InputDecoration(
                      labelText: 'Buscar placa, material ou movimentação',
                      prefixIcon: const Icon(Icons.search),
                      suffixIcon: IconButton(
                        tooltip: 'Buscar',
                        onPressed: _carregar,
                        icon: const Icon(Icons.arrow_forward),
                      ),
                    ),
                  ),
                ],
                const SizedBox(height: 20),
                if (_carregando)
                  const Padding(
                    padding: EdgeInsets.symmetric(vertical: 90),
                    child: Center(child: CircularProgressIndicator()),
                  )
                else if (_erro != null)
                  _MaterialError(message: _erro!, onRetry: _carregar)
                else if (_itens.isEmpty)
                  _EmptyMaterial(historico: widget.historico)
                else
                  ..._itens.map(
                    (item) => Padding(
                      padding: const EdgeInsets.only(bottom: 12),
                      child: _MaterialCard(
                        item: item,
                        historico: widget.historico,
                        onReceive: () => _abrirRecebimento(item),
                      ),
                    ),
                  ),
              ],
            ),
          ),
          if (_recebendo)
            const Positioned.fill(
              child: ColoredBox(
                color: Color(0x660F172A),
                child: Center(
                  child: Card(
                    child: Padding(
                      padding: EdgeInsets.all(22),
                      child: Column(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          CircularProgressIndicator(),
                          SizedBox(height: 12),
                          Text('Confirmando recebimento...'),
                        ],
                      ),
                    ),
                  ),
                ),
              ),
            ),
        ],
      ),
    );
  }
}

class _MaterialCard extends StatelessWidget {
  const _MaterialCard({
    required this.item,
    required this.historico,
    required this.onReceive,
  });

  final MaterialMovement item;
  final bool historico;
  final VoidCallback onReceive;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(18),
      decoration: BoxDecoration(
        color: Colors.white,
        border: Border.all(color: AppColors.border),
        borderRadius: BorderRadius.circular(10),
        boxShadow: const [
          BoxShadow(
            color: Color(0x100F172A),
            blurRadius: 16,
            offset: Offset(0, 6),
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Container(
                width: 45,
                height: 45,
                decoration: BoxDecoration(
                  color: item.comRessalva
                      ? const Color(0xFFFFF1F2)
                      : AppColors.primarySoft,
                  borderRadius: BorderRadius.circular(8),
                ),
                child: Icon(
                  historico ? Icons.inventory_outlined : Icons.local_shipping,
                  color: item.comRessalva
                      ? AppColors.danger
                      : AppColors.primary,
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      item.placa,
                      style: const TextStyle(
                        color: AppColors.ink,
                        fontSize: 19,
                        fontWeight: FontWeight.w900,
                        letterSpacing: 0.4,
                      ),
                    ),
                    Text(
                      item.modeloVeiculo,
                      style: const TextStyle(color: AppColors.muted),
                    ),
                  ],
                ),
              ),
              _StatusBadge(item: item),
            ],
          ),
          const SizedBox(height: 17),
          Text(
            item.material,
            style: const TextStyle(
              color: AppColors.ink,
              fontSize: 17,
              fontWeight: FontWeight.w800,
            ),
          ),
          const SizedBox(height: 3),
          Text(
            'Movimentação ${item.numeroMovimentacao}'
            '${item.quantidadeFormatada == null ? '' : ' · ${item.quantidadeFormatada}'}',
            style: const TextStyle(color: AppColors.muted, fontSize: 12),
          ),
          const SizedBox(height: 14),
          _InfoLine(
            icon: Icons.route_outlined,
            text: '${item.origem} → ${item.destino}',
          ),
          const SizedBox(height: 7),
          _InfoLine(
            icon: Icons.person_outline,
            text: '${item.motorista} · saída ${item.horaSaida}',
          ),
          if (item.obra?.isNotEmpty ?? false) ...[
            const SizedBox(height: 7),
            _InfoLine(icon: Icons.business_outlined, text: item.obra!),
          ],
          if (historico && item.recebidoEm != null) ...[
            const Divider(height: 28),
            _InfoLine(
              icon: Icons.check_circle_outline,
              text: 'Recebido em ${_formatarDataHora(item.recebidoEm!)}',
            ),
            if (item.observacaoRecebimento?.isNotEmpty ?? false) ...[
              const SizedBox(height: 7),
              _InfoLine(
                icon: Icons.notes_outlined,
                text: item.observacaoRecebimento!,
              ),
            ],
          ],
          if (!historico) ...[
            const SizedBox(height: 18),
            SizedBox(
              width: double.infinity,
              child: FilledButton.icon(
                onPressed: onReceive,
                icon: const Icon(Icons.camera_alt_outlined),
                label: const Text('Confirmar recebimento'),
              ),
            ),
          ],
        ],
      ),
    );
  }
}

class _StatusBadge extends StatelessWidget {
  const _StatusBadge({required this.item});

  final MaterialMovement item;

  @override
  Widget build(BuildContext context) {
    final color = item.emTransito
        ? AppColors.warning
        : item.comRessalva
            ? AppColors.danger
            : AppColors.success;
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 9, vertical: 5),
      decoration: BoxDecoration(
        color: color.withAlpha(31),
        borderRadius: BorderRadius.circular(20),
      ),
      child: Text(
        item.status.toUpperCase(),
        style: TextStyle(
          color: color,
          fontSize: 9,
          fontWeight: FontWeight.w900,
        ),
      ),
    );
  }
}

class _InfoLine extends StatelessWidget {
  const _InfoLine({required this.icon, required this.text});

  final IconData icon;
  final String text;

  @override
  Widget build(BuildContext context) {
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Icon(icon, size: 17, color: AppColors.primary),
        const SizedBox(width: 8),
        Expanded(
          child: Text(
            text,
            style: const TextStyle(
              color: AppColors.inkSoft,
              fontSize: 13,
              height: 1.3,
            ),
          ),
        ),
      ],
    );
  }
}

class _ReceiptData {
  const _ReceiptData({
    required this.fotoPath,
    required this.comRessalva,
    required this.observacao,
  });

  final String fotoPath;
  final bool comRessalva;
  final String observacao;
}

class _ReceiptSheet extends StatefulWidget {
  const _ReceiptSheet({required this.item});

  final MaterialMovement item;

  @override
  State<_ReceiptSheet> createState() => _ReceiptSheetState();
}

class _ReceiptSheetState extends State<_ReceiptSheet> {
  final _formKey = GlobalKey<FormState>();
  final _picker = ImagePicker();
  final _observacaoController = TextEditingController();
  XFile? _foto;
  bool _comRessalva = false;

  @override
  void dispose() {
    _observacaoController.dispose();
    super.dispose();
  }

  Future<void> _tirarFoto() async {
    final foto = await _picker.pickImage(
      source: ImageSource.camera,
      preferredCameraDevice: CameraDevice.rear,
      imageQuality: 82,
      maxWidth: 1600,
    );
    if (foto != null && mounted) setState(() => _foto = foto);
  }

  void _confirmar() {
    if (!_formKey.currentState!.validate()) return;
    if (_foto == null) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Tire uma foto do material descarregado.'),
          backgroundColor: AppColors.danger,
        ),
      );
      return;
    }

    Navigator.pop(
      context,
      _ReceiptData(
        fotoPath: _foto!.path,
        comRessalva: _comRessalva,
        observacao: _observacaoController.text.trim(),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final item = widget.item;

    return Padding(
      padding: EdgeInsets.fromLTRB(
        20,
        8,
        20,
        20 + MediaQuery.viewInsetsOf(context).bottom,
      ),
      child: Form(
        key: _formKey,
        child: SingleChildScrollView(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Center(
                child: Container(
                  width: 42,
                  height: 4,
                  margin: const EdgeInsets.symmetric(vertical: 8),
                  decoration: BoxDecoration(
                    color: AppColors.border,
                    borderRadius: BorderRadius.circular(3),
                  ),
                ),
              ),
              const SizedBox(height: 7),
              const Text(
                'Confirmar recebimento',
                style: TextStyle(
                  color: AppColors.ink,
                  fontSize: 21,
                  fontWeight: FontWeight.w800,
                ),
              ),
              const SizedBox(height: 14),
              Container(
                width: double.infinity,
                padding: const EdgeInsets.all(14),
                decoration: BoxDecoration(
                  color: AppColors.primarySoft,
                  borderRadius: BorderRadius.circular(8),
                ),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      '${item.placa} · ${item.material}',
                      style: const TextStyle(
                        color: AppColors.ink,
                        fontWeight: FontWeight.w800,
                      ),
                    ),
                    const SizedBox(height: 3),
                    Text(
                      'Movimentação ${item.numeroMovimentacao} · '
                      '${item.motorista}',
                      style: const TextStyle(
                        color: AppColors.inkSoft,
                        fontSize: 12,
                      ),
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 18),
              InkWell(
                onTap: _tirarFoto,
                borderRadius: BorderRadius.circular(9),
                child: Container(
                  width: double.infinity,
                  height: 180,
                  decoration: BoxDecoration(
                    color: AppColors.background,
                    border: Border.all(
                      color: _foto == null
                          ? AppColors.border
                          : AppColors.success,
                    ),
                    borderRadius: BorderRadius.circular(9),
                  ),
                  child: _foto == null
                      ? const Column(
                          mainAxisAlignment: MainAxisAlignment.center,
                          children: [
                            Icon(
                              Icons.camera_alt_outlined,
                              color: AppColors.primary,
                              size: 38,
                            ),
                            SizedBox(height: 9),
                            Text(
                              'Tirar foto do material',
                              style: TextStyle(fontWeight: FontWeight.w800),
                            ),
                            SizedBox(height: 3),
                            Text(
                              'A foto é obrigatória para confirmar.',
                              style: TextStyle(
                                color: AppColors.muted,
                                fontSize: 12,
                              ),
                            ),
                          ],
                        )
                      : ClipRRect(
                          borderRadius: BorderRadius.circular(8),
                          child: Image.file(
                            File(_foto!.path),
                            fit: BoxFit.cover,
                          ),
                        ),
                ),
              ),
              const SizedBox(height: 14),
              SwitchListTile.adaptive(
                contentPadding: EdgeInsets.zero,
                value: _comRessalva,
                onChanged: (valor) => setState(() => _comRessalva = valor),
                title: const Text(
                  'Recebido com ressalva',
                  style: TextStyle(fontWeight: FontWeight.w800),
                ),
                subtitle: const Text(
                  'Use quando houver divergência, avaria ou descarga parcial.',
                ),
              ),
              const SizedBox(height: 10),
              TextFormField(
                controller: _observacaoController,
                maxLines: 3,
                textCapitalization: TextCapitalization.sentences,
                decoration: InputDecoration(
                  labelText: _comRessalva
                      ? 'Descreva a ressalva'
                      : 'Observação (opcional)',
                  alignLabelWithHint: true,
                ),
                validator: (valor) {
                  if (_comRessalva && (valor ?? '').trim().isEmpty) {
                    return 'Descreva a divergência encontrada.';
                  }
                  return null;
                },
              ),
              const SizedBox(height: 22),
              SizedBox(
                width: double.infinity,
                child: FilledButton.icon(
                  onPressed: _confirmar,
                  icon: const Icon(Icons.check_circle_outline),
                  label: const Text('Confirmar chegada do material'),
                ),
              ),
              const SizedBox(height: 8),
              SizedBox(
                width: double.infinity,
                child: TextButton(
                  onPressed: () => Navigator.pop(context),
                  child: const Text('Cancelar'),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _MaterialError extends StatelessWidget {
  const _MaterialError({required this.message, required this.onRetry});

  final String message;
  final Future<void> Function() onRetry;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(22),
        child: Column(
          children: [
            const Icon(Icons.cloud_off_outlined, color: AppColors.danger),
            const SizedBox(height: 10),
            Text(message, textAlign: TextAlign.center),
            const SizedBox(height: 14),
            OutlinedButton.icon(
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

class _EmptyMaterial extends StatelessWidget {
  const _EmptyMaterial({required this.historico});

  final bool historico;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 22, vertical: 42),
        child: Column(
          children: [
            Icon(
              historico ? Icons.history : Icons.inventory_2_outlined,
              color: AppColors.primary,
              size: 36,
            ),
            const SizedBox(height: 12),
            Text(
              historico
                  ? 'Nenhum recebimento confirmado ainda.'
                  : 'Nenhuma carga aguardando recebimento.',
              textAlign: TextAlign.center,
              style: const TextStyle(
                color: AppColors.ink,
                fontWeight: FontWeight.w800,
              ),
            ),
          ],
        ),
      ),
    );
  }
}

String _formatarDataHora(DateTime data) {
  String dois(int valor) => valor.toString().padLeft(2, '0');
  return '${dois(data.day)}/${dois(data.month)}/${data.year} '
      '${dois(data.hour)}:${dois(data.minute)}';
}
