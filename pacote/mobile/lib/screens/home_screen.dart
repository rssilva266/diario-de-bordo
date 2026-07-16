import 'package:flutter/material.dart';

import '../controllers/session_controller.dart';
import 'diary_screen.dart';
import 'material_screen.dart';
import 'point_screen.dart';

class HomeScreen extends StatefulWidget {
  const HomeScreen({required this.sessionController, super.key});

  final SessionController sessionController;

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  var _indice = 0;

  @override
  Widget build(BuildContext context) {
    final usuario = widget.sessionController.usuario!;
    final podeReceberMateriais = usuario.podeReceberMateriais;
    final paginas = podeReceberMateriais
        ? <Widget>[
            MaterialScreen(
              sessionController: widget.sessionController,
              historico: false,
            ),
            MaterialScreen(
              sessionController: widget.sessionController,
              historico: true,
            ),
            PointScreen(sessionController: widget.sessionController),
          ]
        : <Widget>[
            DiaryScreen(sessionController: widget.sessionController),
            PointScreen(sessionController: widget.sessionController),
          ];

    if (_indice >= paginas.length) _indice = 0;

    return Scaffold(
      body: IndexedStack(
        index: _indice,
        children: paginas,
      ),
      bottomNavigationBar: NavigationBar(
        selectedIndex: _indice,
        onDestinationSelected: (indice) {
          setState(() => _indice = indice);
        },
        destinations: podeReceberMateriais
            ? const [
                NavigationDestination(
                  icon: Icon(Icons.inventory_2_outlined),
                  selectedIcon: Icon(Icons.inventory_2),
                  label: 'Recebimentos',
                ),
                NavigationDestination(
                  icon: Icon(Icons.history_outlined),
                  selectedIcon: Icon(Icons.history),
                  label: 'Histórico',
                ),
                NavigationDestination(
                  icon: Icon(Icons.schedule_outlined),
                  selectedIcon: Icon(Icons.schedule),
                  label: 'Ponto',
                ),
              ]
            : const [
                NavigationDestination(
                  icon: Icon(Icons.route_outlined),
                  selectedIcon: Icon(Icons.route),
                  label: 'Viagens',
                ),
                NavigationDestination(
                  icon: Icon(Icons.schedule_outlined),
                  selectedIcon: Icon(Icons.schedule),
                  label: 'Ponto',
                ),
              ],
      ),
    );
  }
}
