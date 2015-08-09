import pprint
import datetime
import time

from . import httpclient


class YandexError(Exception):
    pass


class Service(object):

    @staticmethod
    def create_using_token(username, token):
        return Service(httpclient.HttpClient.create_using_token(username, token))

    @staticmethod
    def create_using_login(username, password):
        return Service(httpclient.HttpClient.create_using_login(username, password))

    def __init__(self, http_client):
        """
        Инициализировать работу с сервисом Яндекс.Фотки
        @param username: имя пользователя
        @param password: пароль
        @param token: авторизационный токен, может быть указан вместо пароля
        """
        self.http = http_client

        self.data = self.http.service()
        self.albums_href = self.data['collections']['album-list']['href']
        self.photos_href = self.data['collections']['photo-list']['href']
        self.tags_href = self.data['collections']['tag-list']['href']

    def __get_entries_iter(self, url, scheme, count=None, rlimit=100):
        """
        Возвращает итератор по объектам, которые определяются параметром scheme.

        @param url:    адрес коллекции
        @param scheme: Объект, в который будут преобразованы элементы
        @type  count:  int
        @param count:  количество возвращаемых объектов,
                       None - все объекты
        @type  rlimit: int
        @param rlimit: количество объектов, возвращаемых в одном запросе,
                       но не больше 100 (ограничение Яндекс для постраничной
                       выдачи коллекций)
        @rtype:        __generator
        """
        # проверяем, чтобы максимально в выдаче стояло не больше 100 элементов
        if rlimit > 100:
            rlimit = 100
        # если количество запрашиваемых элементов не больше 100, столько и запросим
        if count and count < 100:
            rlimit = count
        # добавляем параметр лимита в запрос
        next_item = url + ('?' if url.find('?') < 0 else '&') + 'limit={0}'.format(rlimit)
        while next_item:
            data = self.http.request(next_item)
            for i in data['entries']:
                yield scheme(self, i)
                if count is not None:
                    count -= 1
                    if count <= 0:
                        return
            next_item = data['links'].get('next')

    def get_albums_iter(self, count=None, rlimit=100):
        """
        Возвращает итератор по альбомам. Если вы хотите построить иерархию альбомов,
        разумнее воспользоваться методом get_albums для получения сразу всех альбомов.
        @type  count: int
        @param count: количество возвращаемых альбомов,
                      None - все альбомы
        @type  rlimit: int
        @param rlimit: количество альбомов, возвращаемых в одном запросе,
                       но не больше 100 (ограничение Яндекс для постраничной
                       выдачи коллекций)
        @rtype: __generator of YandexAlbum
        """
        return self.__get_entries_iter(self.albums_href, Album, count, rlimit)

    def get_albums(self):
        """
        Возвращает все альбомы. Если альбомов очень много, разумнее
        воспользоваться генератором iter_albums.
        @rtype: list of YandexAlbum
        """
        return list(self.get_albums_iter())

    def get_photos_iter(self, count=None, rlimit=100):
        """
        @type  count: int
        @param count: количество возвращаемых фотографий,
                      None - все фотографии
        @type  rlimit: int
        @param rlimit: количество фотографий, возвращаемых в одном запросе,
                       но не больше 100 (ограничение Яндекс для постраничной
                       выдачи коллекций)
        @rtype: __generator of YandexPhoto
        """
        return self.__get_entries_iter(self.photos_href, Photo, count, rlimit)

    def get_photos(self):
        """
        Возвращает все фотографии. Если фотографий очень много, разумнее
        воспользоваться генератором iter_photos.
        @rtype: list of YandexPhoto
        """
        return list(self.get_photos_iter())

    def get_tags_iter(self, count=None, rlimit=100):
        return self.__get_entries_iter(self.tags_href, Tag, count, rlimit)

    def get_tags(self):
        return list(self.get_tags_iter())

    def create_album(self, title, summary=None, parent=None):
        """
        Создать новый альбом
        @param title: Название
        @param summary: Описание
        @type parent: YandexAlbum
        @param parent: Родительский альбом
        @return: Новый созданный альбом
        """
        data = {'title': title}
        if summary:
            data['summary'] = summary
        if parent:
            data['links'] = {'album': parent.link_self}
        answer = self.http.put(self.albums_href, data)
        return YandexAlbum(self, answer)

    def __str__(self):
        return pprint.pformat(self.data)

    @property
    def id(self):
        """Уникальный идентификатор сущности"""
        return None

    @property
    def link_self(self):
        return None


class YandexEntry(object):
    def __init__(self, service, data):
        """
        @type   service: YandexService
        @type   data: dict
        @param  data: словарь параметров сущности
        """
        self.service = service
        self.data = data

    @staticmethod
    def convert_time(ts, tz=True):
        if not ts:
            return None
        dt = datetime.datetime.strptime(ts, '%Y-%m-%dT%H:%M:%SZ')
        if tz:
            dt = dt - datetime.timedelta(seconds=time.timezone)
        return dt

    @property
    def id(self):
        """Уникальный идентификатор сущности"""
        return self.data['id']

    @property
    def title(self):
        """Заголовок сущности"""
        return self.data.get('title', '')

    def link(self, name='self'):
        return self.data['links'].get(name)

    @property
    def link_self(self):
        return self.link('self')

    @property
    def link_edit(self):
        return self.link('edit')

    @property
    def link_parent(self):
        return self.link('album')

    @property
    def link_alt(self):
        return self.link('alternate')

    @property
    def created(self):
        return self.convert_time(self.data.get('created'), False)

    @property
    def edited(self):
        return self.convert_time(self.data.get('edited'))

    @property
    def published(self):
        return self.convert_time(self.data.get('published'))

    def update(self):
        self.data = self.service.request(self.link_self)

    def edit(self, upd_data):
        data = self.service.request(self.link_edit)
        data.update(upd_data)
        data = json.dumps(data)
        headers = {'Content-Type': 'application/json;  type=entry'}
        self.data = self.service.request(self.link_self, data, headers, method='PUT')

    def delete(self):
        self.service.request(self.link_self, code=204, method='DELETE')

    # def __str__(self):
    # return pprint.pformat(self.data)

    def __eq__(self, other):
        return self.id == other.id


class YandexAlbum(YandexEntry):
    @property
    def link_photos(self):
        return self.link('photos')

    @property
    def photos(self):
        return list(self.iter_photos())

    @property
    def count(self):
        return self.data.get('imageCount', 0)

    def upload(self, filename):
        # При загрузке данных надо обернуть все в bytearray, иначе происходит ошибка Unicode
        # чертовы строки в python
        # http://bugs.python.org/issue12398
        data = bytearray(open(filename, 'rb').read())
        mimetype = mimetypes.guess_type(filename)[0] or 'application/octet-stream'
        headers = {'Content-Type': mimetype}
        answer = self.service.request(self.link_photos, data, headers, code=201)
        photo = YandexPhoto(self.service, answer)
        return photo

    def edit(self, title=None, summary=None, parent=None):
        data = {}
        if title is not None:
            data['title'] = title
        if summary is not None:
            data['summary'] = summary
        if parent is not None:
            data['links'] = {'album': parent.get_link()}
        YandexEntry.edit(self, data)

    def iter_photos(self, count=None, rlimit=100):
        return self.service.iter_entries(self.link_photos, YandexPhoto, count, rlimit)

    def create_album(self, title, summary=None):
        return self.service.create_album(title, summary, self)


class YandexPhoto(YandexEntry):
    def __init__(self, service, data):
        YandexEntry.__init__(self, service, data)
        imgs = self.data['img']
        self.images = sorted([YandexImage(self, name, imgs[name]) for name in imgs],
                             key=lambda x: x.w)

    def image(self, name):
        return next((x for x in self.images if x.name == name), None)

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
        YandexEntry.edit(self, data)

    @property
    def tags(self):
        return self.data.get('tags', {})


class YandexImage(object):
    def __init__(self, photo, name, data):
        self.photo = photo
        self.name = name
        self.w = data['width']
        self.h = data['height']
        self.size = data.get('bytesize')
        self.href = data['href']

    def download(self):
        return urllib.request.urlopen(self.href).read()

    def __repr__(self):
        return '<{} {}x{}>'.format(self.name, self.w, self.h)


class YandexTag(object):
    def __init__(self, data):
        self.data = data

    def __str__(self):
        return pprint.pformat(self.data)
