import 'package:dio/dio.dart';

import '../storage/secure_token_storage.dart';

class ApiClient {
  ApiClient({
    required String baseUrl,
    required SecureTokenStorage tokenStorage,
    Dio? dio,
  }) : _tokenStorage = tokenStorage,
       _dio =
           dio ??
           Dio(
             BaseOptions(
               baseUrl: baseUrl,
               connectTimeout: const Duration(seconds: 15),
               receiveTimeout: const Duration(seconds: 20),
               headers: {'Accept': 'application/json'},
             ),
           ) {
    _dio.interceptors.add(
      InterceptorsWrapper(
        onRequest: (options, handler) async {
          final token = await _tokenStorage.readAccessToken();
          if (token != null && token.isNotEmpty) {
            options.headers['Authorization'] = 'Bearer $token';
          }
          handler.next(options);
        },
      ),
    );
  }

  final Dio _dio;
  final SecureTokenStorage _tokenStorage;

  String get baseUrl => _dio.options.baseUrl;

  Future<Response<dynamic>> get(String path, {Map<String, dynamic>? query}) =>
      _dio.get<dynamic>(path, queryParameters: query);

  Future<Response<dynamic>> post(String path, {Object? data}) =>
      _dio.post<dynamic>(path, data: data);

  Future<Response<dynamic>> patch(String path, {Object? data}) =>
      _dio.patch<dynamic>(path, data: data);

  void dispose() => _dio.close();
}
