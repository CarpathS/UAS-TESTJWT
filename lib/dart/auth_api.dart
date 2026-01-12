import 'dart:convert';
import 'package:http/http.dart' as http;

import '../config/api_config.dart';
import 'token_storage.dart';

class AuthApi {
  final String baseUrl;
  AuthApi({this.baseUrl = ApiConfig.baseUrl});

  Future<void> register({
    required String email,
    required String password,
  }) async {
    final url = Uri.parse('$baseUrl/register');
    final res = await http.post(
      url,
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({'email': email, 'password': password}),
    );

    if (res.statusCode == 201) return;

    throw Exception('Register gagal (${res.statusCode}): ${res.body}');
  }

  Future<void> login({required String email, required String password}) async {
    final url = Uri.parse('$baseUrl/login');
    final res = await http.post(
      url,
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({'email': email, 'password': password}),
    );

    if (res.statusCode == 200) {
      final data = jsonDecode(res.body) as Map<String, dynamic>;
      final token = data['access_token'] as String;
      await TokenStorage.saveToken(token);
      return;
    }

    throw Exception('Login gagal (${res.statusCode}): ${res.body}');
  }

  Future<void> logout() async {
    await TokenStorage.clearToken();
  }
}
