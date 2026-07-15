import 'package:flutter/material.dart';

import '../controllers/session_controller.dart';
import 'diary_screen.dart';
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
    return Scaffold(
      body: IndexedStack(
        index: _indice,
        children: [
          DiaryScreen(sessionController: widget.sessionController),
          PointScreen(sessionController: widget.sessionController),
        ],
      ),
      bottomNavigationBar: NavigationBar(
        selectedIndex: _indice,
        onDestinationSelected: (indice) {
          setState(() => _indice = indice);
        },
        destinations: const [
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
