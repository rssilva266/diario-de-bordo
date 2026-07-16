import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:image_picker/image_picker.dart';

import '../controllers/session_controller.dart';
import '../core/theme/app_colors.dart';
import '../models/diary_state.dart';
import '../services/api_exception.dart';
import '../services/diary_service.dart';
import '../widgets/brand_mark.dart';

class DiaryScreen extends StatefulWidget {
  const DiaryScreen({required this.sessionController, super.key});

  final SessionController sessionController;

  @override
  State<DiaryScreen> createState() => _DiaryScreenState();
}

class _DiaryScreenState extends State<DiaryScreen> {
  late final DiaryService _diaryService;

  DiaryState? _estado;
  bool _carregando = true;
  bool _enviando = false;
  String? _erro;

  @override
  void initState() {
    super.initState();
    _diaryService = DiaryService(widget.sessionController.apiClient);
    _carregarEstado();
  }

  Future<void> _carregarEstado() async {
    if (!mounted || widget.sessionController.usuario == null) return;

    setState(() {
      _carregando = true;
      _erro = null;
    });

    try {
      final estado = await _diaryService.obterEstado();
      if (mounted) setState(() => _estado = estado);
    } on ApiException catch (erro) {
      if (erro.sessaoExpirada) {
        await widget.sessionController.sessaoExpirada();
        return;
      }
      if (mounted) setState(() => _erro = erro.message);
    } catch (_) {
      if (mounted) {
        setState(() => _erro = 'Não foi possível carregar seus diários.');
      }
    } finally {
      if (mounted) setState(() => _carregando = false);
    }
  }

  Future<void> _abrirNovoDiario() async {
    final estado = _estado;

    if (estado == null || !estado.podeIniciar || estado.veiculo == null) {
      return;
    }

    final dados = await showModalBottomSheet<DiaryStartData>(
      context: context,
      isScrollControlled: true,
      useSafeArea: true,
      backgroundColor: Colors.white,
      builder: (context) => _NewDiarySheet(estado: estado),
    );

    if (dados == null || !mounted) return;

    setState(() => _enviando = true);

    try {
      final novoEstado = await _diaryService.iniciar(dados);
      if (!mounted) return;
      setState(() => _estado = novoEstado);
      await HapticFeedback.mediumImpact();
      if (!mounted) return;

      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(
            dados.transportaMaterial
                ? 'Diário iniciado e carga enviada aos apontadores.'
                : dados.houveAbastecimento
                    ? 'Diário e abastecimento registrados.'
                    : 'Diário iniciado com sucesso.',
          ),
          backgroundColor: AppColors.success,
        ),
      );
    } on ApiException catch (erro) {
      if (erro.sessaoExpirada) {
        await widget.sessionController.sessaoExpirada();
        return;
      }
      if (mounted) _mostrarErro(erro.message);
      if (erro.statusCode == 409) await _carregarEstado();
    } catch (_) {
      if (mounted) _mostrarErro('Não foi possível iniciar o diário.');
    } finally {
      if (mounted) setState(() => _enviando = false);
    }
  }

  Future<void> _abrirFinalizacao(DiaryEntry diario) async {
    final dados = await showModalBottomSheet<_FinishDiaryData>(
      context: context,
      isScrollControlled: true,
      useSafeArea: true,
      backgroundColor: Colors.white,
      builder: (context) => _FinishDiarySheet(diario: diario),
    );

    if (dados == null || !mounted) return;

    setState(() => _enviando = true);

    try {
      final novoEstado = await _diaryService.finalizar(
        diarioId: diario.id,
        horaChegada: dados.horaChegada,
        kmFinal: dados.kmFinal,
      );
      if (!mounted) return;
      setState(() => _estado = novoEstado);
      await HapticFeedback.mediumImpact();
      if (!mounted) return;

      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Diário finalizado com sucesso.'),
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
      if (mounted) _mostrarErro('Não foi possível finalizar o diário.');
    } finally {
      if (mounted) setState(() => _enviando = false);
    }
  }

  void _mostrarErro(String mensagem) {
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text(mensagem), backgroundColor: AppColors.danger),
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
      body: Stack(
        children: [
          RefreshIndicator(
            onRefresh: _carregarEstado,
            child: ListView(
              physics: const AlwaysScrollableScrollPhysics(),
              padding: const EdgeInsets.fromLTRB(20, 22, 20, 36),
              children: [
                Text(
                  'Suas viagens',
                  style: Theme.of(context).textTheme.headlineSmall?.copyWith(
                        color: AppColors.ink,
                        fontWeight: FontWeight.w800,
                      ),
                ),
                const SizedBox(height: 4),
                Text(
                  'Inicie e finalize os deslocamentos do veículo vinculado.',
                  style: const TextStyle(color: AppColors.muted),
                ),
                const SizedBox(height: 22),
                if (_carregando)
                  const Padding(
                    padding: EdgeInsets.symmetric(vertical: 90),
                    child: Center(child: CircularProgressIndicator()),
                  )
                else if (_erro != null)
                  _DiaryErrorCard(message: _erro!, onRetry: _carregarEstado)
                else if (_estado != null)
                  _DiaryContent(
                    estado: _estado!,
                    onStart: _abrirNovoDiario,
                    onFinish: _abrirFinalizacao,
                  ),
              ],
            ),
          ),
          if (_enviando)
            Positioned.fill(
              child: ColoredBox(
                color: const Color(0x660F172A),
                child: Center(
                  child: Container(
                    padding: const EdgeInsets.all(20),
                    decoration: BoxDecoration(
                      color: Colors.white,
                      borderRadius: BorderRadius.circular(10),
                    ),
                    child: const Column(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        CircularProgressIndicator(),
                        SizedBox(height: 12),
                        Text('Salvando diário...'),
                      ],
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

class _DiaryContent extends StatelessWidget {
  const _DiaryContent({
    required this.estado,
    required this.onStart,
    required this.onFinish,
  });

  final DiaryState estado;
  final VoidCallback onStart;
  final Future<void> Function(DiaryEntry diario) onFinish;

  @override
  Widget build(BuildContext context) {
    final aberto = estado.diarioEmAndamento;
    final recentes = estado.recentes
        .where((item) => item.id != aberto?.id)
        .toList(growable: false);

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        if (aberto != null)
          _ActiveDiaryCard(diario: aberto, onFinish: () => onFinish(aberto))
        else
          _StartDiaryCard(estado: estado, onStart: onStart),
        const SizedBox(height: 26),
        const Text(
          'Últimos diários',
          style: TextStyle(
            color: AppColors.ink,
            fontSize: 18,
            fontWeight: FontWeight.w800,
          ),
        ),
        const SizedBox(height: 12),
        if (recentes.isEmpty)
          const Card(
            child: Padding(
              padding: EdgeInsets.all(22),
              child: Row(
                children: [
                  Icon(Icons.route_outlined, color: AppColors.primary),
                  SizedBox(width: 12),
                  Expanded(
                    child: Text(
                      'Nenhum diário finalizado ainda.',
                      style: TextStyle(color: AppColors.muted),
                    ),
                  ),
                ],
              ),
            ),
          )
        else
          Card(
            child: Column(
              children: [
                for (var index = 0; index < recentes.length; index++) ...[
                  _DiaryHistoryTile(diario: recentes[index]),
                  if (index < recentes.length - 1)
                    const Divider(height: 1, indent: 68),
                ],
              ],
            ),
          ),
      ],
    );
  }
}

class _StartDiaryCard extends StatelessWidget {
  const _StartDiaryCard({required this.estado, required this.onStart});

  final DiaryState estado;
  final VoidCallback onStart;

  @override
  Widget build(BuildContext context) {
    final veiculo = estado.veiculo;

    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: Colors.white,
        border: Border.all(color: AppColors.border),
        borderRadius: BorderRadius.circular(12),
        boxShadow: const [
          BoxShadow(
            color: Color(0x120F172A),
            blurRadius: 18,
            offset: Offset(0, 7),
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Container(
                width: 44,
                height: 44,
                decoration: BoxDecoration(
                  color: AppColors.primarySoft,
                  borderRadius: BorderRadius.circular(8),
                ),
                child: const Icon(
                  Icons.local_shipping_outlined,
                  color: AppColors.primary,
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      veiculo == null ? 'Veículo não vinculado' : veiculo.placa,
                      style: const TextStyle(
                        color: AppColors.ink,
                        fontSize: 18,
                        fontWeight: FontWeight.w800,
                      ),
                    ),
                    Text(
                      veiculo?.modelo ?? estado.motorista.nome,
                      style: const TextStyle(color: AppColors.muted),
                    ),
                  ],
                ),
              ),
            ],
          ),
          if (veiculo != null) ...[
            const SizedBox(height: 18),
            Row(
              children: [
                Expanded(
                  child: _MiniInfo(
                    label: 'KM atual',
                    value: '${_formatarInteiro(veiculo.kmAtual)} km',
                  ),
                ),
                const SizedBox(width: 10),
                Expanded(
                  child: _MiniInfo(
                    label: 'Combustível',
                    value: veiculo.combustivel.isEmpty
                        ? 'Não cadastrado'
                        : veiculo.combustivel,
                  ),
                ),
              ],
            ),
          ],
          const SizedBox(height: 18),
          if (estado.bloqueio != null)
            Container(
              width: double.infinity,
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: const Color(0xFFFFF7E6),
                borderRadius: BorderRadius.circular(7),
                border: Border.all(color: const Color(0x55F59E0B)),
              ),
              child: Text(
                estado.bloqueio!,
                style: const TextStyle(color: AppColors.inkSoft),
              ),
            )
          else
            SizedBox(
              width: double.infinity,
              child: FilledButton.icon(
                onPressed: estado.podeIniciar ? onStart : null,
                icon: const Icon(Icons.play_arrow_rounded),
                label: const Text('Iniciar novo diário'),
              ),
            ),
        ],
      ),
    );
  }
}

class _ActiveDiaryCard extends StatelessWidget {
  const _ActiveDiaryCard({required this.diario, required this.onFinish});

  final DiaryEntry diario;
  final VoidCallback onFinish;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        gradient: const LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: [AppColors.navy, AppColors.navySecondary],
        ),
        borderRadius: BorderRadius.circular(12),
        boxShadow: const [
          BoxShadow(
            color: Color(0x300F172A),
            blurRadius: 24,
            offset: Offset(0, 10),
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const Icon(Icons.route, color: AppColors.lightBlue),
              const SizedBox(width: 9),
              const Expanded(
                child: Text(
                  'Viagem em andamento',
                  style: TextStyle(
                    color: Colors.white,
                    fontSize: 17,
                    fontWeight: FontWeight.w800,
                  ),
                ),
              ),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 9, vertical: 5),
                decoration: BoxDecoration(
                  color: const Color(0x33F59E0B),
                  borderRadius: BorderRadius.circular(20),
                ),
                child: const Text(
                  'EM ANDAMENTO',
                  style: TextStyle(
                    color: Color(0xFFFCD34D),
                    fontSize: 10,
                    fontWeight: FontWeight.w800,
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 20),
          Text(
            '${diario.origem} → ${diario.destino}',
            style: const TextStyle(
              color: Colors.white,
              fontSize: 20,
              fontWeight: FontWeight.w800,
            ),
          ),
          if (diario.finalidade?.isNotEmpty ?? false) ...[
            const SizedBox(height: 5),
            Text(
              diario.finalidade!,
              style: const TextStyle(color: AppColors.sidebarText),
            ),
          ],
          const SizedBox(height: 20),
          Row(
            children: [
              Expanded(
                child: _DarkInfo(
                  icon: Icons.local_shipping_outlined,
                  label: diario.veiculo.placa,
                  value: diario.veiculo.modelo,
                ),
              ),
              const SizedBox(width: 10),
              Expanded(
                child: _DarkInfo(
                  icon: Icons.schedule,
                  label: 'Saída ${diario.horaSaida}',
                  value: 'KM ${_formatarInteiro(diario.kmInicial)}',
                ),
              ),
            ],
          ),
          if (diario.houveAbastecimento) ...[
            const SizedBox(height: 12),
            const Row(
              children: [
                Icon(Icons.local_gas_station, size: 18, color: AppColors.lightBlue),
                SizedBox(width: 7),
                Text(
                  'Abastecimento registrado nesta saída',
                  style: TextStyle(color: AppColors.sidebarText),
                ),
              ],
            ),
          ],
          if (diario.movimentacaoMaterial != null) ...[
            const SizedBox(height: 12),
            Container(
              width: double.infinity,
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: const Color(0xFF1E293B),
                borderRadius: BorderRadius.circular(7),
                border: Border.all(color: const Color(0x335DB4FF)),
              ),
              child: Row(
                children: [
                  const Icon(
                    Icons.inventory_2_outlined,
                    color: AppColors.lightBlue,
                  ),
                  const SizedBox(width: 9),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          diario.movimentacaoMaterial!.material,
                          style: const TextStyle(
                            color: Colors.white,
                            fontWeight: FontWeight.w800,
                          ),
                        ),
                        Text(
                          'Movimentação ${diario.movimentacaoMaterial!.numeroMovimentacao} '
                          '· ${diario.movimentacaoMaterial!.status}',
                          style: const TextStyle(
                            color: AppColors.sidebarText,
                            fontSize: 12,
                          ),
                        ),
                      ],
                    ),
                  ),
                ],
              ),
            ),
          ],
          const SizedBox(height: 20),
          SizedBox(
            width: double.infinity,
            child: FilledButton.icon(
              onPressed: onFinish,
              icon: const Icon(Icons.flag_outlined),
              label: const Text('Finalizar viagem'),
            ),
          ),
        ],
      ),
    );
  }
}

class _MiniInfo extends StatelessWidget {
  const _MiniInfo({required this.label, required this.value});

  final String label;
  final String value;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: AppColors.background,
        borderRadius: BorderRadius.circular(7),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(label, style: const TextStyle(color: AppColors.muted, fontSize: 11)),
          const SizedBox(height: 3),
          Text(
            value,
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
            style: const TextStyle(color: AppColors.ink, fontWeight: FontWeight.w700),
          ),
        ],
      ),
    );
  }
}

class _DarkInfo extends StatelessWidget {
  const _DarkInfo({
    required this.icon,
    required this.label,
    required this.value,
  });

  final IconData icon;
  final String label;
  final String value;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: const Color(0xFF1E293B),
        borderRadius: BorderRadius.circular(7),
      ),
      child: Row(
        children: [
          Icon(icon, size: 20, color: AppColors.lightBlue),
          const SizedBox(width: 8),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  label,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: const TextStyle(
                    color: Colors.white,
                    fontWeight: FontWeight.w700,
                  ),
                ),
                Text(
                  value,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: const TextStyle(color: AppColors.sidebarText, fontSize: 11),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _DiaryHistoryTile extends StatelessWidget {
  const _DiaryHistoryTile({required this.diario});

  final DiaryEntry diario;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 14),
      child: Row(
        children: [
          Container(
            width: 42,
            height: 42,
            decoration: BoxDecoration(
              color: AppColors.primarySoft,
              borderRadius: BorderRadius.circular(8),
            ),
            child: const Icon(Icons.route_outlined, color: AppColors.primary),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  '${diario.origem} → ${diario.destino}',
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: const TextStyle(
                    color: AppColors.ink,
                    fontWeight: FontWeight.w700,
                  ),
                ),
                const SizedBox(height: 3),
                Text(
                  '${_formatarData(diario.data)} · ${diario.horaSaida}'
                  '${diario.horaChegada == null ? '' : '–${diario.horaChegada}'}',
                  style: const TextStyle(color: AppColors.muted, fontSize: 12),
                ),
                if (diario.movimentacaoMaterial != null) ...[
                  const SizedBox(height: 3),
                  Text(
                    '${diario.movimentacaoMaterial!.material} · '
                    '${diario.movimentacaoMaterial!.status}',
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: const TextStyle(
                      color: AppColors.primary,
                      fontSize: 11,
                      fontWeight: FontWeight.w700,
                    ),
                  ),
                ],
              ],
            ),
          ),
          const SizedBox(width: 10),
          Text(
            diario.kmPercorrida == null
                ? '—'
                : '${_formatarInteiro(diario.kmPercorrida!)} km',
            style: const TextStyle(
              color: AppColors.ink,
              fontWeight: FontWeight.w800,
            ),
          ),
        ],
      ),
    );
  }
}

class _NewDiarySheet extends StatefulWidget {
  const _NewDiarySheet({required this.estado});

  final DiaryState estado;

  @override
  State<_NewDiarySheet> createState() => _NewDiarySheetState();
}

class _NewDiarySheetState extends State<_NewDiarySheet> {
  final _formKey = GlobalKey<FormState>();
  final _picker = ImagePicker();
  late final TextEditingController _kmController;
  final _origemController = TextEditingController();
  final _destinoController = TextEditingController();
  final _finalidadeController = TextEditingController();
  final _ocorrenciasController = TextEditingController();
  final _materialController = TextEditingController();
  final _numeroMovimentacaoController = TextEditingController();
  final _quantidadeMaterialController = TextEditingController();
  final _observacaoMaterialController = TextEditingController();
  final _postoController = TextEditingController();
  final _litrosController = TextEditingController();
  final _valorLitroController = TextEditingController();
  final _numeroNotaController = TextEditingController();

  late DateTime _data;
  late TimeOfDay _horaSaida;
  int? _obraId;
  bool _houveAbastecimento = false;
  bool _transportaMaterial = false;
  bool _tanqueCheio = false;
  String? _unidadeMaterial;
  XFile? _fotoOdometro;
  XFile? _cupomFiscal;

  @override
  void initState() {
    super.initState();
    final veiculo = widget.estado.veiculo!;
    _data = DateTime.now();
    _horaSaida = TimeOfDay.now();
    _obraId = widget.estado.obras.any((item) => item.id == veiculo.obraId)
        ? veiculo.obraId
        : null;
    _kmController = TextEditingController(text: veiculo.kmAtual.toString());
  }

  @override
  void dispose() {
    _kmController.dispose();
    _origemController.dispose();
    _destinoController.dispose();
    _finalidadeController.dispose();
    _ocorrenciasController.dispose();
    _materialController.dispose();
    _numeroMovimentacaoController.dispose();
    _quantidadeMaterialController.dispose();
    _observacaoMaterialController.dispose();
    _postoController.dispose();
    _litrosController.dispose();
    _valorLitroController.dispose();
    _numeroNotaController.dispose();
    super.dispose();
  }

  double get _valorTotal {
    final litros = double.tryParse(_litrosController.text.replaceAll(',', '.')) ?? 0;
    final valor =
        double.tryParse(_valorLitroController.text.replaceAll(',', '.')) ?? 0;
    return litros * valor;
  }

  Future<void> _selecionarData() async {
    final data = await showDatePicker(
      context: context,
      initialDate: _data,
      firstDate: DateTime.now().subtract(const Duration(days: 1)),
      lastDate: DateTime.now().add(const Duration(days: 1)),
    );

    if (!mounted) return;
    if (data != null) setState(() => _data = data);
  }

  Future<void> _selecionarHora() async {
    final hora = await showTimePicker(context: context, initialTime: _horaSaida);
    if (!mounted) return;
    if (hora != null) setState(() => _horaSaida = hora);
  }

  Future<void> _tirarFoto({required bool odometro}) async {
    final foto = await _picker.pickImage(
      source: ImageSource.camera,
      preferredCameraDevice: CameraDevice.rear,
      imageQuality: 82,
      maxWidth: 1600,
    );

    if (foto == null || !mounted) return;

    setState(() {
      if (odometro) {
        _fotoOdometro = foto;
      } else {
        _cupomFiscal = foto;
      }
    });
  }

  void _confirmar() {
    if (!_formKey.currentState!.validate()) return;

    if (_houveAbastecimento &&
        (_fotoOdometro == null || _cupomFiscal == null)) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Tire a foto do odômetro e do cupom fiscal.'),
          backgroundColor: AppColors.danger,
        ),
      );
      return;
    }

    Navigator.pop(
      context,
      DiaryStartData(
        data: _formatarDataApi(_data),
        horaSaida: _formatarTimeOfDay(_horaSaida),
        kmInicial: int.parse(_kmController.text),
        origem: _origemController.text.trim(),
        destino: _destinoController.text.trim(),
        obraId: _obraId,
        finalidade: _finalidadeController.text.trim(),
        ocorrencias: _ocorrenciasController.text.trim(),
        houveAbastecimento: _houveAbastecimento,
        posto: _postoController.text.trim(),
        litros: _litrosController.text.trim().replaceAll(',', '.'),
        valorLitro: _valorLitroController.text.trim().replaceAll(',', '.'),
        numeroNota: _numeroNotaController.text.trim(),
        tanqueCheio: _tanqueCheio,
        fotoOdometroPath: _fotoOdometro?.path,
        cupomFiscalPath: _cupomFiscal?.path,
        transportaMaterial: _transportaMaterial,
        material: _materialController.text.trim(),
        numeroMovimentacao: _numeroMovimentacaoController.text.trim(),
        quantidadeMaterial:
            _quantidadeMaterialController.text.trim().replaceAll(',', '.'),
        unidadeMaterial: _unidadeMaterial ?? '',
        observacaoMaterial: _observacaoMaterialController.text.trim(),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final veiculo = widget.estado.veiculo!;

    return DraggableScrollableSheet(
      expand: false,
      initialChildSize: 0.94,
      minChildSize: 0.7,
      maxChildSize: 0.98,
      builder: (context, scrollController) {
        return Form(
          key: _formKey,
          child: Column(
            children: [
              const _SheetHandle(),
              Padding(
                padding: const EdgeInsets.fromLTRB(20, 4, 12, 10),
                child: Row(
                  children: [
                    const Expanded(
                      child: Text(
                        'Iniciar novo diário',
                        style: TextStyle(
                          color: AppColors.ink,
                          fontSize: 20,
                          fontWeight: FontWeight.w800,
                        ),
                      ),
                    ),
                    IconButton(
                      onPressed: () => Navigator.pop(context),
                      icon: const Icon(Icons.close),
                    ),
                  ],
                ),
              ),
              const Divider(height: 1),
              Expanded(
                child: ListView(
                  controller: scrollController,
                  padding: EdgeInsets.fromLTRB(
                    20,
                    18,
                    20,
                    20 + MediaQuery.viewInsetsOf(context).bottom,
                  ),
                  children: [
                    _LinkedVehicleBanner(
                      motorista: widget.estado.motorista.nome,
                      veiculo: veiculo,
                    ),
                    const SizedBox(height: 18),
                    Row(
                      children: [
                        Expanded(
                          child: _PickerField(
                            label: 'Data',
                            value: _formatarData(_data),
                            icon: Icons.calendar_today_outlined,
                            onTap: _selecionarData,
                          ),
                        ),
                        const SizedBox(width: 10),
                        Expanded(
                          child: _PickerField(
                            label: 'Hora de saída',
                            value: _formatarTimeOfDay(_horaSaida),
                            icon: Icons.schedule,
                            onTap: _selecionarHora,
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 16),
                    DropdownButtonFormField<int?>(
                      initialValue: _obraId,
                      decoration: const InputDecoration(
                        labelText: 'Obra ou centro de custo',
                        prefixIcon: Icon(Icons.business_outlined),
                      ),
                      items: [
                        const DropdownMenuItem<int?>(
                          value: null,
                          child: Text('Sem obra vinculada'),
                        ),
                        ...widget.estado.obras.map(
                          (obra) => DropdownMenuItem<int?>(
                            value: obra.id,
                            child: Text(
                              obra.descricao,
                              overflow: TextOverflow.ellipsis,
                            ),
                          ),
                        ),
                      ],
                      onChanged: (valor) => setState(() => _obraId = valor),
                    ),
                    const SizedBox(height: 16),
                    TextFormField(
                      controller: _origemController,
                      textCapitalization: TextCapitalization.sentences,
                      decoration: const InputDecoration(
                        labelText: 'Origem',
                        prefixIcon: Icon(Icons.trip_origin),
                      ),
                      validator: _validarObrigatorio,
                    ),
                    const SizedBox(height: 16),
                    TextFormField(
                      controller: _destinoController,
                      textCapitalization: TextCapitalization.sentences,
                      decoration: const InputDecoration(
                        labelText: 'Destino',
                        prefixIcon: Icon(Icons.location_on_outlined),
                      ),
                      validator: _validarObrigatorio,
                    ),
                    const SizedBox(height: 16),
                    TextFormField(
                      controller: _kmController,
                      keyboardType: TextInputType.number,
                      inputFormatters: [FilteringTextInputFormatter.digitsOnly],
                      decoration: const InputDecoration(
                        labelText: 'KM inicial',
                        prefixIcon: Icon(Icons.speed_outlined),
                        suffixText: 'km',
                      ),
                      validator: (valor) {
                        final km = int.tryParse(valor ?? '');
                        if (km == null || km < 0) return 'Informe um KM válido';
                        return null;
                      },
                    ),
                    const SizedBox(height: 16),
                    TextFormField(
                      controller: _finalidadeController,
                      textCapitalization: TextCapitalization.sentences,
                      decoration: const InputDecoration(
                        labelText: 'Finalidade do deslocamento',
                        prefixIcon: Icon(Icons.assignment_outlined),
                      ),
                    ),
                    const SizedBox(height: 16),
                    TextFormField(
                      controller: _ocorrenciasController,
                      maxLines: 3,
                      textCapitalization: TextCapitalization.sentences,
                      decoration: const InputDecoration(
                        labelText: 'Ocorrências ou observações',
                        alignLabelWithHint: true,
                      ),
                    ),
                    const SizedBox(height: 22),
                    SwitchListTile.adaptive(
                      contentPadding: const EdgeInsets.symmetric(horizontal: 4),
                      value: _transportaMaterial,
                      onChanged: (valor) {
                        setState(() {
                          _transportaMaterial = valor;
                          if (!valor) {
                            _materialController.clear();
                            _numeroMovimentacaoController.clear();
                            _quantidadeMaterialController.clear();
                            _observacaoMaterialController.clear();
                            _unidadeMaterial = null;
                          }
                        });
                      },
                      title: const Text(
                        'Está transportando material?',
                        style: TextStyle(fontWeight: FontWeight.w800),
                      ),
                      subtitle: const Text(
                        'A carga aparecerá para recebimento no app do apontador.',
                      ),
                    ),
                    if (_transportaMaterial) ...[
                      const SizedBox(height: 10),
                      Container(
                        padding: const EdgeInsets.all(16),
                        decoration: BoxDecoration(
                          color: AppColors.background,
                          border: Border.all(color: AppColors.border),
                          borderRadius: BorderRadius.circular(10),
                        ),
                        child: Column(
                          children: [
                            TextFormField(
                              controller: _materialController,
                              textCapitalization: TextCapitalization.sentences,
                              decoration: const InputDecoration(
                                labelText: 'Material',
                                prefixIcon: Icon(Icons.inventory_2_outlined),
                                hintText: 'Ex.: Brita, areia ou massa asfáltica',
                              ),
                              validator: (valor) => _transportaMaterial
                                  ? _validarObrigatorio(valor)
                                  : null,
                            ),
                            const SizedBox(height: 14),
                            TextFormField(
                              controller: _numeroMovimentacaoController,
                              decoration: const InputDecoration(
                                labelText: 'Número da movimentação',
                                prefixIcon: Icon(Icons.numbers_outlined),
                              ),
                              validator: (valor) => _transportaMaterial
                                  ? _validarObrigatorio(valor)
                                  : null,
                            ),
                            const SizedBox(height: 14),
                            Row(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Expanded(
                                  child: TextFormField(
                                    controller: _quantidadeMaterialController,
                                    keyboardType:
                                        const TextInputType.numberWithOptions(
                                      decimal: true,
                                    ),
                                    decoration: const InputDecoration(
                                      labelText: 'Quantidade (opcional)',
                                    ),
                                    onChanged: (_) => setState(() {}),
                                    validator: (valor) {
                                      if (!_transportaMaterial) return null;
                                      if ((valor ?? '').trim().isEmpty) {
                                        if (_unidadeMaterial != null) {
                                          return 'Informe a quantidade';
                                        }
                                        return null;
                                      }
                                      final numero = double.tryParse(
                                        valor!.replaceAll(',', '.'),
                                      );
                                      if (numero == null || numero <= 0) {
                                        return 'Quantidade inválida';
                                      }
                                      return null;
                                    },
                                  ),
                                ),
                                const SizedBox(width: 10),
                                Expanded(
                                  child: DropdownButtonFormField<String?>(
                                    initialValue: _unidadeMaterial,
                                    decoration: const InputDecoration(
                                      labelText: 'Unidade',
                                    ),
                                    items: const [
                                      DropdownMenuItem<String?>(
                                        value: null,
                                        child: Text('Não informar'),
                                      ),
                                      DropdownMenuItem(value: 't', child: Text('t')),
                                      DropdownMenuItem(value: 'kg', child: Text('kg')),
                                      DropdownMenuItem(value: 'm³', child: Text('m³')),
                                      DropdownMenuItem(value: 'un', child: Text('un')),
                                      DropdownMenuItem(
                                        value: 'carga',
                                        child: Text('carga'),
                                      ),
                                    ],
                                    onChanged: (valor) {
                                      setState(() => _unidadeMaterial = valor);
                                    },
                                    validator: (valor) {
                                      if (!_transportaMaterial) return null;
                                      final possuiQuantidade =
                                          _quantidadeMaterialController.text
                                              .trim()
                                              .isNotEmpty;
                                      if (possuiQuantidade && valor == null) {
                                        return 'Selecione';
                                      }
                                      return null;
                                    },
                                  ),
                                ),
                              ],
                            ),
                            const SizedBox(height: 14),
                            TextFormField(
                              controller: _observacaoMaterialController,
                              maxLines: 2,
                              textCapitalization: TextCapitalization.sentences,
                              decoration: const InputDecoration(
                                labelText: 'Observação da carga (opcional)',
                                alignLabelWithHint: true,
                              ),
                            ),
                          ],
                        ),
                      ),
                    ],
                    const SizedBox(height: 22),
                    SwitchListTile.adaptive(
                      contentPadding: const EdgeInsets.symmetric(horizontal: 4),
                      value: _houveAbastecimento,
                      onChanged: (valor) {
                        setState(() => _houveAbastecimento = valor);
                      },
                      title: const Text(
                        'Houve abastecimento?',
                        style: TextStyle(fontWeight: FontWeight.w800),
                      ),
                      subtitle: const Text(
                        'Registre os dados e comprovantes junto com o diário.',
                      ),
                    ),
                    if (_houveAbastecimento) ...[
                      const SizedBox(height: 10),
                      Container(
                        padding: const EdgeInsets.all(16),
                        decoration: BoxDecoration(
                          color: AppColors.background,
                          border: Border.all(color: AppColors.border),
                          borderRadius: BorderRadius.circular(10),
                        ),
                        child: Column(
                          children: [
                            TextFormField(
                              initialValue: veiculo.combustivel,
                              readOnly: true,
                              decoration: const InputDecoration(
                                labelText: 'Combustível do veículo',
                                prefixIcon: Icon(Icons.local_gas_station_outlined),
                              ),
                            ),
                            const SizedBox(height: 14),
                            TextFormField(
                              controller: _postoController,
                              textCapitalization: TextCapitalization.words,
                              decoration: const InputDecoration(
                                labelText: 'Posto ou fornecedor',
                              ),
                              validator: (valor) => _houveAbastecimento
                                  ? _validarObrigatorio(valor)
                                  : null,
                            ),
                            const SizedBox(height: 14),
                            Row(
                              children: [
                                Expanded(
                                  child: TextFormField(
                                    controller: _litrosController,
                                    keyboardType: const TextInputType.numberWithOptions(
                                      decimal: true,
                                    ),
                                    decoration: const InputDecoration(
                                      labelText: 'Litros',
                                      suffixText: 'L',
                                    ),
                                    onChanged: (_) => setState(() {}),
                                    validator: (valor) => _validarDecimalPositivo(
                                      valor,
                                      'Informe os litros',
                                    ),
                                  ),
                                ),
                                const SizedBox(width: 10),
                                Expanded(
                                  child: TextFormField(
                                    controller: _valorLitroController,
                                    keyboardType: const TextInputType.numberWithOptions(
                                      decimal: true,
                                    ),
                                    decoration: const InputDecoration(
                                      labelText: 'Valor por litro',
                                      prefixText: 'R\$ ',
                                    ),
                                    onChanged: (_) => setState(() {}),
                                    validator: (valor) => _validarDecimalPositivo(
                                      valor,
                                      'Informe o valor',
                                    ),
                                  ),
                                ),
                              ],
                            ),
                            const SizedBox(height: 14),
                            InputDecorator(
                              decoration: const InputDecoration(
                                labelText: 'Total calculado',
                                prefixIcon: Icon(Icons.calculate_outlined),
                              ),
                              child: Text(
                                _formatarMoeda(_valorTotal),
                                style: const TextStyle(
                                  color: AppColors.ink,
                                  fontSize: 18,
                                  fontWeight: FontWeight.w800,
                                ),
                              ),
                            ),
                            const SizedBox(height: 14),
                            TextFormField(
                              controller: _numeroNotaController,
                              decoration: const InputDecoration(
                                labelText: 'Número do cupom/nota (opcional)',
                              ),
                            ),
                            const SizedBox(height: 14),
                            _PhotoField(
                              title: 'Foto do odômetro',
                              subtitle: 'Mostre o KM inicial com nitidez.',
                              foto: _fotoOdometro,
                              onCamera: () => _tirarFoto(odometro: true),
                            ),
                            const SizedBox(height: 12),
                            _PhotoField(
                              title: 'Foto do cupom fiscal',
                              subtitle: 'Enquadre valores, litros e data.',
                              foto: _cupomFiscal,
                              onCamera: () => _tirarFoto(odometro: false),
                            ),
                            CheckboxListTile(
                              contentPadding: EdgeInsets.zero,
                              value: _tanqueCheio,
                              onChanged: (valor) {
                                setState(() => _tanqueCheio = valor ?? false);
                              },
                              title: const Text('Tanque completo'),
                              controlAffinity: ListTileControlAffinity.leading,
                            ),
                          ],
                        ),
                      ),
                    ],
                    const SizedBox(height: 22),
                    SizedBox(
                      width: double.infinity,
                      child: FilledButton.icon(
                        onPressed: _confirmar,
                        icon: const Icon(Icons.play_arrow_rounded),
                        label: const Text('Iniciar diário'),
                      ),
                    ),
                    const SizedBox(height: 8),
                    const Text(
                      'O diário ficará em andamento até você finalizar a viagem.',
                      textAlign: TextAlign.center,
                      style: TextStyle(color: AppColors.muted, fontSize: 12),
                    ),
                  ],
                ),
              ),
            ],
          ),
        );
      },
    );
  }
}

class _FinishDiaryData {
  const _FinishDiaryData({required this.horaChegada, required this.kmFinal});

  final String horaChegada;
  final int kmFinal;
}

class _FinishDiarySheet extends StatefulWidget {
  const _FinishDiarySheet({required this.diario});

  final DiaryEntry diario;

  @override
  State<_FinishDiarySheet> createState() => _FinishDiarySheetState();
}

class _FinishDiarySheetState extends State<_FinishDiarySheet> {
  final _formKey = GlobalKey<FormState>();
  final _kmController = TextEditingController();
  var _hora = TimeOfDay.now();

  @override
  void dispose() {
    _kmController.dispose();
    super.dispose();
  }

  Future<void> _selecionarHora() async {
    final hora = await showTimePicker(context: context, initialTime: _hora);
    if (!mounted) return;
    if (hora != null) setState(() => _hora = hora);
  }

  void _confirmar() {
    if (!_formKey.currentState!.validate()) return;

    Navigator.pop(
      context,
      _FinishDiaryData(
        horaChegada: _formatarTimeOfDay(_hora),
        kmFinal: int.parse(_kmController.text),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final diario = widget.diario;

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
              const Center(child: _SheetHandle()),
              const SizedBox(height: 8),
              const Text(
                'Finalizar viagem',
                style: TextStyle(
                  color: AppColors.ink,
                  fontSize: 20,
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
                      '${diario.origem} → ${diario.destino}',
                      style: const TextStyle(
                        color: AppColors.ink,
                        fontWeight: FontWeight.w800,
                      ),
                    ),
                    const SizedBox(height: 3),
                    Text(
                      '${diario.veiculo.placa} · saída ${diario.horaSaida} · '
                      'KM inicial ${_formatarInteiro(diario.kmInicial)}',
                      style: const TextStyle(color: AppColors.inkSoft, fontSize: 12),
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 18),
              _PickerField(
                label: 'Hora de chegada',
                value: _formatarTimeOfDay(_hora),
                icon: Icons.schedule,
                onTap: _selecionarHora,
              ),
              const SizedBox(height: 16),
              TextFormField(
                controller: _kmController,
                autofocus: true,
                keyboardType: TextInputType.number,
                inputFormatters: [FilteringTextInputFormatter.digitsOnly],
                decoration: InputDecoration(
                  labelText: 'KM final',
                  prefixIcon: const Icon(Icons.speed_outlined),
                  suffixText: 'km',
                  helperText: 'Mínimo ${_formatarInteiro(diario.kmInicial)} km',
                ),
                validator: (valor) {
                  final km = int.tryParse(valor ?? '');
                  if (km == null) return 'Informe o KM final';
                  if (km < diario.kmInicial) {
                    return 'Não pode ser menor que o KM inicial';
                  }
                  return null;
                },
              ),
              const SizedBox(height: 22),
              SizedBox(
                width: double.infinity,
                child: FilledButton.icon(
                  onPressed: _confirmar,
                  icon: const Icon(Icons.flag_outlined),
                  label: const Text('Confirmar finalização'),
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

class _LinkedVehicleBanner extends StatelessWidget {
  const _LinkedVehicleBanner({
    required this.motorista,
    required this.veiculo,
  });

  final String motorista;
  final DiaryVehicle veiculo;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: AppColors.primarySoft,
        borderRadius: BorderRadius.circular(9),
      ),
      child: Row(
        children: [
          const Icon(Icons.verified_outlined, color: AppColors.primary),
          const SizedBox(width: 11),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  '$motorista · ${veiculo.placa}',
                  style: const TextStyle(
                    color: AppColors.ink,
                    fontWeight: FontWeight.w800,
                  ),
                ),
                Text(
                  '${veiculo.modelo} · ${veiculo.combustivel.isEmpty ? 'combustível não cadastrado' : veiculo.combustivel}',
                  style: const TextStyle(color: AppColors.inkSoft, fontSize: 12),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _PickerField extends StatelessWidget {
  const _PickerField({
    required this.label,
    required this.value,
    required this.icon,
    required this.onTap,
  });

  final String label;
  final String value;
  final IconData icon;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(8),
      child: InputDecorator(
        decoration: InputDecoration(labelText: label, prefixIcon: Icon(icon)),
        child: Text(value, style: const TextStyle(fontWeight: FontWeight.w700)),
      ),
    );
  }
}

class _PhotoField extends StatelessWidget {
  const _PhotoField({
    required this.title,
    required this.subtitle,
    required this.foto,
    required this.onCamera,
  });

  final String title;
  final String subtitle;
  final XFile? foto;
  final VoidCallback onCamera;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: Colors.white,
        border: Border.all(
          color: foto == null ? AppColors.border : AppColors.success,
        ),
        borderRadius: BorderRadius.circular(8),
      ),
      child: Row(
        children: [
          if (foto == null)
            Container(
              width: 54,
              height: 54,
              decoration: BoxDecoration(
                color: AppColors.primarySoft,
                borderRadius: BorderRadius.circular(7),
              ),
              child: const Icon(Icons.camera_alt_outlined, color: AppColors.primary),
            )
          else
            ClipRRect(
              borderRadius: BorderRadius.circular(7),
              child: Image.file(
                File(foto!.path),
                width: 54,
                height: 54,
                fit: BoxFit.cover,
              ),
            ),
          const SizedBox(width: 11),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(title, style: const TextStyle(fontWeight: FontWeight.w800)),
                const SizedBox(height: 2),
                Text(subtitle, style: const TextStyle(color: AppColors.muted, fontSize: 11)),
              ],
            ),
          ),
          IconButton.filledTonal(
            tooltip: foto == null ? 'Abrir câmera' : 'Tirar novamente',
            onPressed: onCamera,
            icon: Icon(foto == null ? Icons.camera_alt_outlined : Icons.refresh),
          ),
        ],
      ),
    );
  }
}

class _SheetHandle extends StatelessWidget {
  const _SheetHandle();

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 8),
      child: Container(
        width: 42,
        height: 4,
        decoration: BoxDecoration(
          color: AppColors.border,
          borderRadius: BorderRadius.circular(3),
        ),
      ),
    );
  }
}

class _DiaryErrorCard extends StatelessWidget {
  const _DiaryErrorCard({required this.message, required this.onRetry});

  final String message;
  final Future<void> Function() onRetry;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(20),
        child: Column(
          children: [
            const Icon(Icons.link_off, size: 38, color: AppColors.danger),
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

String? _validarObrigatorio(String? valor) {
  if (valor == null || valor.trim().isEmpty) return 'Campo obrigatório';
  return null;
}

String? _validarDecimalPositivo(String? valor, String mensagem) {
  final numero = double.tryParse((valor ?? '').replaceAll(',', '.'));
  if (numero == null || numero <= 0) return mensagem;
  return null;
}

String _formatarDataApi(DateTime data) {
  return '${data.year.toString().padLeft(4, '0')}-'
      '${data.month.toString().padLeft(2, '0')}-'
      '${data.day.toString().padLeft(2, '0')}';
}

String _formatarData(DateTime data) {
  return '${data.day.toString().padLeft(2, '0')}/'
      '${data.month.toString().padLeft(2, '0')}/${data.year}';
}

String _formatarTimeOfDay(TimeOfDay hora) {
  return '${hora.hour.toString().padLeft(2, '0')}:'
      '${hora.minute.toString().padLeft(2, '0')}';
}

String _formatarInteiro(int valor) {
  final texto = valor.toString();
  final partes = <String>[];

  for (var fim = texto.length; fim > 0; fim -= 3) {
    final inicio = (fim - 3).clamp(0, texto.length).toInt();
    partes.insert(0, texto.substring(inicio, fim));
  }

  return partes.join('.');
}

String _formatarMoeda(double valor) {
  final partes = valor.toStringAsFixed(2).split('.');
  return 'R\$ ${_formatarInteiro(int.parse(partes[0]))},${partes[1]}';
}
