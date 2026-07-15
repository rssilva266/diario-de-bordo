class ApiException implements Exception {
  const ApiException(
    this.message, {
    this.statusCode,
    this.networkFailure = false,
  });

  final String message;
  final int? statusCode;
  final bool networkFailure;

  bool get sessaoExpirada => statusCode == 401;

  @override
  String toString() => message;
}
