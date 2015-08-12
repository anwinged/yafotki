import pprint
import datetime
import time

from . import httpclient


class Basement(object):

    def __init__(self, http_client):
        """
        :type http_client: httpclient.HttpClient
        """
        self.__http = http_client

    @property
    def _http(self):
        return self.__http

    def _get_entries_iter(self, service, url, scheme, count=None, page_size=100):
        # проверяем, чтобы максимально в выдаче стояло не больше 100 элементов
        if page_size > 100:
            page_size = 100
        # если количество запрашиваемых элементов не больше 100, столько и запросим
        if count and count < 100:
            page_size = count
        # добавляем параметр лимита в запрос
        next_item = url + ('?' if url.find('?') < 0 else '&') + 'limit={0}'.format(page_size)
        while next_item:
            data = self.__http.get(next_item)
            for i in data['entries']:
                yield scheme(service, i)
                if count is not None:
                    count -= 1
                    if count <= 0:
                        return
            next_item = data['links'].get('next')


class Service(Basement):

    @staticmethod
    def create_using_token(username, token):
        return Service(httpclient.HttpClient.create_using_token(username, token))

    @staticmethod
    def create_using_login(username, password):
        return Service(httpclient.HttpClient.create_using_login(username, password))

    def __init__(self, http_client):
        Basement.__init__(self, http_client)
        self.__data = self._http.service()
        self.__albums_href = self.__data['collections']['album-list']['href']
        self.__photos_href = self.__data['collections']['photo-list']['href']
        self.__tags_href = self.__data['collections']['tag-list']['href']

    def get_albums_iter(self, count=None, page_size=100):
        return self._get_entries_iter(self, self.__albums_href, Album, count, page_size)

    def get_albums(self):
        """
        Возвращает все альбомы. Если альбомов очень много, разумнее
        воспользоваться генератором iter_albums.
        :rtype: list of Album
        """
        return list(self.get_albums_iter())

    def get_photos_iter(self, count=None, page_size=100):
        return self._get_entries_iter(self, self.__photos_href, Photo, count, page_size)

    def get_photos(self):
        """
        Возвращает все фотографии. Если фотографий очень много, разумнее
        воспользоваться генератором iter_photos.
        :rtype: list of Photo
        """
        return list(self.get_photos_iter())

    def get_tags_iter(self, count=None, page_size=100):
        return self._get_entries_iter(self, self.__tags_href, Tag, count, page_size)

    def get_tags(self):
        return list(self.get_tags_iter())

    def create_album(self, title, summary=None, parent=None):
        data = {'title': title, 'summary': summary}
        if parent:
            if not isinstance(parent, Album):
                raise ValueError('parent must be Album reference')
            data['links'] = {'album': parent.link_self}
        responce = self._http.put(self.__albums_href, data)
        return Album(self, responce)


class Entry(Basement):

    @staticmethod
    def _convert_time(ts):
        if not ts:
            return None
        dt = datetime.datetime.strptime(ts, '%Y-%m-%dT%H:%M:%SZ')
        dt = dt - datetime.timedelta(seconds=time.timezone)
        return dt

    def __init__(self, service, data):
        Basement.__init__(self, service._http)
        self.__service = service
        self.__data = data

        self.id = data.get('id')
        self.title = data.get('title')
        self.author = data.get('author')
        self.updated = self._convert_time(data.get('updated'))

        links = data.get('links', {})
        self.link_self = links.get('self')
        self.link_edit = links.get('edit')
        self.link_alternate = links.get('alternate')

    @property
    def service(self):
        return self.__service

    def _edit(self, updated_fields):
        new_data = self._http.put(self.link_self, updated_fields)
        self.__init__(self.service, new_data)

    def get_raw_data(self):
        return self.__data

    def refresh(self):
        data = self._http.get(self.link_self)
        self.__init__(self.service, data)

    def delete(self):
        self._http.delete(self.link_self)

    def __eq__(self, other):
        return self.id == other.id


class Album(Entry):

    def __init__(self, service, data):
        Entry.__init__(self, service, data)

        self.summary = data.get('summary')
        self.published = self._convert_time(data.get('published'))
        self.edited = self._convert_time(data.get('edited'))
        self.protected = data.get('protected')
        self.password = data.get('password')
        self.count = data.get('imageCount')

        links = data.get('links', {})
        self.link_photos = links.get('photos')
        self.link_cover = links.get('cover')
        self.link_ymapsml = links.get('ymapsml')

    def upload(self, data, mimetype):
        responce = self._http.upload(self.link_photos, data, mimetype)
        return Photo(self.service, responce)

    def upload_file(self, filename):
        responce = self._http.upload_file(self.link_photos, filename)
        return Photo(self.service, responce)

    def edit(self, title=None, summary=None, parent=None):
        data = {'title': title, 'summary': summary}
        if parent is not None:
            if not isinstance(parent, Album):
                raise ValueError('parent must be Album reference')
            data['links'] = {'album': parent.link_self}
        self._edit(data)

    def get_photos_iter(self, count=None, page_size=100):
        return self._get_entries_iter(self.service, self.link_photos, Photo, count, page_size)

    def get_photos(self):
        return list(self.get_photos_iter())

    def create_album(self, title, summary=None):
        return self.service.create_album(title, summary, self)


class Photo(Entry):

    def __init__(self, service, data):
        Entry.__init__(self, service, data)

        self.content = data.get('content')
        self.published = self._convert_time(data.get('published'))
        self.edited = self._convert_time(data.get('edited'))
        self.access = data.get('access')
        self.xxx = data.get('xxx')
        self.hide_original = data.get('hideOriginal')
        self.disable_comments = data.get('disableComments')

        links = data.get('links', {})
        self.link_edit_media = links.get('editMedia')
        self.link_album = links.get('album')

        images = data.get('img', {})
        self.images = {name: Image(self, name, data) for name, data in images.items()}

    def edit(self, title=None, summary=None, xxx=None,
             disable_comments=None, hide_original=None, access=None):
        data = {}
        if title is not None:
            data['title'] = title
        if summary is not None:
            data['summary'] = summary
        if xxx is not None:
            data['xxx'] = bool(xxx)
        if disable_comments is not None:
            data['disableComments'] = bool(disable_comments)
        if hide_original is not None:
            data['hideOriginal'] = bool(hide_original)
        if access is not None:
            data['access'] = access
        self._edit(data)


class Image(object):
    def __init__(self, photo, name, data):
        self.photo = photo
        self.name = name
        self.width = data['width']
        self.height = data['height']
        self.size = data.get('bytesize')
        self.href = data['href']

    def download(self):
        return self.photo._http.download(self.href)

    def __repr__(self):
        return '<{} {}x{}>'.format(self.name, self.width, self.height)


class Tag(object):

    def __init__(self, data):
        self.data = data

    def __str__(self):
        return pprint.pformat(self.data)
