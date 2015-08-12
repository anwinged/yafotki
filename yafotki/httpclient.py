import urllib.request
import urllib.parse
import http.client
import mimetypes
import json
import re

from . import rsaencoder

__author__ = 'Anton Vakhrushev'


class HttpClient(object):

    URL_AUTH_KEY = 'http://auth.mobile.yandex.ru/yamrsa/key/'
    URL_AUTH_TOKEN = 'http://auth.mobile.yandex.ru/yamrsa/token/'
    URL_SERVICE_DOC = 'http://api-fotki.yandex.ru/api/users/{author}/'

    @staticmethod
    def create_using_token(username, token):
        return HttpClient(username, token)

    @staticmethod
    def create_using_login(username, password):
        token = HttpClient.__auth(username, password)
        return HttpClient(username, token)

    @staticmethod
    def __http_request(url, headers=None, data=None, method=None, retcode=http.client.OK):
        headers = headers or {}
        request = urllib.request.Request(url, data=data, headers=headers, method=method)
        responce = urllib.request.urlopen(request)
        if responce.status != retcode:
            raise http.client.HTTPException()
        return responce.read()

    @staticmethod
    def __http_request_str(url, headers=None, data=None, method=None, retcode=http.client.OK):
        responce = HttpClient.__http_request(url, headers, data, method, retcode)
        return responce.decode('utf-8')

    @staticmethod
    def __extract(tag, text):
        pattern = '<{0}>(.*?)</{0}>'.format(tag)
        match = re.search(pattern, text)
        if not match:
            raise ValueError('Tag not found')
        return match.group(1)

    @staticmethod
    def __auth(username, password):
        answer = HttpClient.__http_request_str(HttpClient.URL_AUTH_KEY)
        # Извлечение данных об открытом ключе
        public_key = HttpClient.__extract('key', answer)
        request_id = HttpClient.__extract('request_id', answer)
        # Шаг 2. Шифрование данных открытым ключом
        message = '<credentials login="{0}" password="{1}"/>'
        message = message.format(username, password)
        encoded = rsaencoder.encode(public_key, message)
        # Шаг 3. Передеча данных на сервер яндекса
        headers = {'Content-Type': 'application/x-www-form-urlencoded'}
        params = {'request_id': request_id, 'credentials': encoded}
        data = urllib.parse.urlencode(params).encode()
        responce = HttpClient.__http_request_str(HttpClient.URL_AUTH_TOKEN, headers, data, method='POST')
        return HttpClient.__extract('token', responce)

    def __init__(self, username, token):
        self.__username = username
        self.__token = token

    def get_token(self):
        return self.__token

    def __get_headers(self, headers=None):
        default = {
            'Accept': 'application/json',
            'Authorization': 'FimpToken realm="fotki.yandex.ru", token="{0}"'.format(self.__token),
        }
        default.update(headers or {})
        return default

    def __request(self, url, headers=None, data=None, method=None, retcode=http.client.OK):
        headers = self.__get_headers(headers)
        responce = self.__http_request_str(url, headers, data, method, retcode)
        return json.loads(responce)

    def get(self, url):
        return self.__request(url, method='GET')

    def put(self, url, data):
        headers = {'Content-Type': 'application/json;  type=entry'}
        filtered = {k: v for k, v in data.iter_items() if v is not None}
        data = json.dumps(filtered).encode('utf-8')
        return self.__request(url, headers, data, 'PUT', http.client.OK)

    def delete(self, url):
        return self.__request(url, method='DELETE', retcode=http.client.NO_CONTENT)

    def service(self):
        url = self.URL_SERVICE_DOC.format(author=self.__username)
        return self.get(url)

    def upload(self, url, data, mimetype):
        headers = {'Content-Type': mimetype}
        return self.__request(url, headers, data, 'POST', http.client.CREATED)

    def upload_file(self, url, filename):
        mimetype = mimetypes.guess_type(filename)[0] or 'application/octet-stream'
        data = bytes(open(filename, 'rb').read())
        return self.upload(url, data, mimetype)

    def download(self, url):
        pass