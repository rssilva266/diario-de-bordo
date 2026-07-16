class UserModel {
  const UserModel({
    required this.id,
    required this.nome,
    required this.usuario,
    required this.perfil,
    required this.empresa,
    this.email,
    this.colaboradorVinculado = false,
    this.trocarSenha = false,
    this.podeReceberMateriais = false,
  });

  final int id;
  final String nome;
  final String usuario;
  final String perfil;
  final String empresa;
  final String? email;
  final bool colaboradorVinculado;
  final bool trocarSenha;
  final bool podeReceberMateriais;

  factory UserModel.fromJson(Map<String, dynamic> json) {
    return UserModel(
      id: json['id'] as int,
      nome: json['nome'] as String,
      usuario: json['usuario'] as String,
      perfil: json['perfil'] as String,
      empresa:
          (json['empresa'] as Map<String, dynamic>?)?['nome'] as String? ?? '',
      email: json['email'] as String?,
      colaboradorVinculado: json['colaborador_vinculado'] as bool? ?? false,
      trocarSenha: json['trocar_senha'] as bool? ?? false,
      podeReceberMateriais: json['pode_receber_materiais'] as bool? ?? false,
    );
  }

  String get primeiroNome {
    final nomeLimpo = nome.trim();
    if (nomeLimpo.isEmpty) return 'Usuário';
    return nomeLimpo.split(RegExp(r'\s+')).first;
  }

  String get inicial => primeiroNome.substring(0, 1).toUpperCase();
}
