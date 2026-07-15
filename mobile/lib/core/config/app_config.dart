class AppConfig {
  const AppConfig._();

  static const String apiBaseUrl = String.fromEnvironment(
    'API_BASE_URL',
    defaultValue: 'https://gerenciamento.msmind.com.br/api/mobile',
  );

  static const Duration requestTimeout = Duration(seconds: 30);
}
