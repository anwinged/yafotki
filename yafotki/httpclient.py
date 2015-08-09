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
        token = HttpClient.auth(username, password)
        return HttpClient(username, token)

    @staticmethod
    def http_request(url, headers=None, data=None, method=None, retcode=http.client.OK):
        headers = headers or {}
        request = urllib.request.Request(url, data=data, headers=headers, method=method)
        responce = urllib.request.urlopen(request)
        if responce.status != retcode:
            raise http.client.HTTPException()
        return responce.read().decode('utf-8')

    @staticmethod
    def extract(tag, text):
        pattern = '<{0}>(.*?)</{0}>'.format(tag)
        match = re.search(pattern, text)
        if not match:
            raise ValueError('Tag not found')
        return match.group(1)

    @staticmethod
    def auth(username, password):
        answer = HttpClient.http_request(HttpClient.URL_AUTH_KEY)
        # Извлечение данных об открытом ключе
        public_key = HttpClient.extract('key', answer)
        request_id = HttpClient.extract('request_id', answer)
        # Шаг 2. Шифрование данных открытым ключом
        message = '<credentials login="{0}" password="{1}"/>'
        message = message.format(username, password)
        encoded = rsaencoder.encode(public_key, message)
        # Шаг 3. Передеча данных на сервер яндекса
        headers = {'Content-Type': 'application/x-www-form-urlencoded'}
        params = {'request_id': request_id, 'credentials': encoded}
        data = urllib.parse.urlencode(params).encode()
        responce = HttpClient.http_request(HttpClient.URL_AUTH_TOKEN, headers, data, method='POST')
        return HttpClient.extract('token', responce)

    def __init__(self, username, token):
        self.username = username
        self.token = token

    def request(self, url, headers=None, data=None, method=None, retcode=http.client.OK):
        request_headers = {
            'Accept': 'application/json',
            'Authorization': 'FimpToken realm="fotki.yandex.ru", token="{0}"'.format(self.token),
        }
        request_headers.update(headers or {})
        responce = self.http_request(url, request_headers, data, method, retcode)
        return json.loads(responce)

    def get(self, url):
        return self.request(url, method='GET')

    def put(self, url, data):
        headers = {'Content-Type': 'application/json;  type=entry'}
        data = json.dumps(data).encode('utf-8')
        return self.request(url, headers, data, 'PUT', http.client.OK)

    def delete(self, url):
        return self.request(url, method='DELETE', retcode=http.client.NO_CONTENT)

    def service(self):
        url = self.URL_SERVICE_DOC.format(author=self.username)
        return self.get(url)

    def upload(self, url, filename):
        mimetype = mimetypes.guess_type(filename)[0] or 'application/octet-stream'
        headers = {'Content-Type': mimetype}
        data = bytes(open(filename, 'rb').read())
        return self.request(url, headers, data, 'POST', http.client.CREATED)

    def download(self, url):
        pass