import 'dart:convert';
import 'package:http/http.dart' as http;

import '../config/api_config.dart';
import 'auth_headers.dart';

class NotesApi {
  final String baseUrl;
  NotesApi({this.baseUrl = ApiConfig.baseUrl});

  Future<List<dynamic>> listNotes() async {
    final url = Uri.parse('$baseUrl/notes');
    final res = await http.get(url, headers: await AuthHeaders.jsonWithAuth());

    if (res.statusCode == 200) return jsonDecode(res.body) as List<dynamic>;
    if (res.statusCode == 401)
      throw Exception('Token invalid/expired, login lagi');
    throw Exception('Gagal load notes (${res.statusCode}): ${res.body}');
  }

  Future<void> createNote(String title, String content) async {
    final url = Uri.parse('$baseUrl/notes');
    final res = await http.post(
      url,
      headers: await AuthHeaders.jsonWithAuth(),
      body: jsonEncode({'title': title, 'content': content}),
    );

    if (res.statusCode == 201) return;
    if (res.statusCode == 401)
      throw Exception('Token invalid/expired, login lagi');
    throw Exception('Gagal create (${res.statusCode}): ${res.body}');
  }
}
