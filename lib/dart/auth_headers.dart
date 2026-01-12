import 'token_storage.dart';

class AuthHeaders {
  static Future<Map<String, String>> json() async {
    return {'Content-Type': 'application/json'};
  }

  static Future<Map<String, String>> jsonWithAuth() async {
    final token = await TokenStorage.readToken();
    final headers = <String, String>{'Content-Type': 'application/json'};

    if (token != null && token.isNotEmpty) {
      headers['Authorization'] = 'Bearer $token';
    }
    return headers;
  }
}
