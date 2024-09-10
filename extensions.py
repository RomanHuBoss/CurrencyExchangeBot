from Levenshtein import distance
import requests
import copy
from datetime import datetime
import xml.etree.ElementTree as ETree

from settings import CURRENCIES_VOC_URL, RATES_URL_PREFIX

class APIException(Exception):
    """
    класс ошибок при работе с ботом
    """
    def __init__(self, message: str):
        self._message = message

    def __str__(self):
        return self._message

class API:
    """
    класс API
    """
    @staticmethod
    def get_price(base: str, quote: str, amount: float):
        """
        обработчик запроса к боту на конвертацию валюты
        :param base: код или название валюты, в которую конвертируем
        :param quote: код или название валюты, которая конвертируется
        :param amount: количество валюты, в которую конвертируем
        :return: str
        """
        try:
            if not hasattr(API, 'storage'):
                API.storage = RatesStorage()

            try:
                amount = float(amount)
            except ValueError:
                raise APIException(f"Количество целевой валюты должно быть числом ({ValueError.__name__})")

            if amount <= 0:
                raise APIException(f"Количество целевой валюты должно быть больше нуля ({ValueError.__name__})")

            base_data = API.storage.get_currency_data(base)
            if base_data is None:
                raise APIException(f"Не найдена целевая валюта, название или код которой соответствуют запросу {base} ({APIException.__name__})")

            quote_data = API.storage.get_currency_data(quote)
            if quote_data is None:
                raise APIException(f"Не найдена конвертируемая валюта, название или код которой соответствуют запросу {quote} ({APIException.__name__})")

            if base_data['code'] == quote_data['code']:
                raise APIException(f"Целевая валюта должна отличаться от конвертируемой ({APIException.__name__})")

            base_quantity = round(base_data['rub_rate'] / quote_data['rub_rate'] * amount, 2)

            return (f"Стоимость {amount}  {base_data['code']} ({base_data['rus_name']}/{base_data['eng_name']}) "
                    f"составляет {base_quantity} {quote_data['code']} ({quote_data['rus_name']}/{quote_data['eng_name']})")
        except APIException as e:
            return (f"{e}")

    @staticmethod
    def get_vocabulary():
        """
        обработчик запроса к боту на получение информации о словаре валют
        :return: str
        """

        def align_and_pad(txt: str, width=45, filler=' ', align='c'):
            """
            функция выравнивает строку, дополняя ее нужным числом заданных символов
            :param txt: исходная строка
            :param width: ширина конечной строки
            :param filler: символ для заполнения
            :param align: выравнивание (l - слева, r - справа, c - по центру)
            :return: str
            """
            return {'l': txt.ljust, 'c': txt.center, 'r': txt.rjust}[align](width, filler)

        try:
            rows = []

            if not hasattr(API, 'storage'):
                API.storage = RatesStorage()

            rows.append('СПРАВОЧНИК ВАЛЮТ')
            rows.append('(Код валюты, русское и английское названия)')
            rows.append('-----------------------------------------------------------')

            for item in API.storage.data:
                rows.append(f"{item['code']}, {item['rus_name']}, {item['eng_name']}")

            rows.append('-----------------------------------------------------------')
            rows.append("Чтобы вывести справку, наберите /start или /help")
            return "\n".join(rows)

        except APIException as e:
            return (f"{e}")


class RatesStorage:
    """
    класс-хранилище информации о курсах валют
    """
    def __init__(self):
        self._data_write_only = []
        self._data_read_only = []
        self._cached_date = None

    @staticmethod
    def current_date() -> str:
        """
        Возвращает текущую дату в формате ДД/ММ/ГГГГ
        :return: str
        """
        return datetime.now().strftime("%d/%m/%Y")

    @property
    def data(self):
        """
        Возвращает содержимое хранилища, защищая оригинальный кэш от изменения (см. deepcopy).
        Побочный эффект: если кэш протух, актуализирует его.
        :return: list[dict]
        """

        def lists_match(l1, l2):
            if len(l1) != len(l2):
                return False
            return all(x == y and type(x) == type(y) for x, y in zip(l1, l2))

        if RatesStorage.current_date() != self._cached_date:
            self.fill()

        if not lists_match(self._data_write_only, self._data_read_only):
            self._data_read_only = copy.deepcopy(self._data_write_only)

        return self._data_read_only

    def reset(self):
        self._data_write_only = []
        self._data_read_only = []
        self._cached_date = None

    @staticmethod
    def get_vocabulary():
        """
        получает словарь валют с сайта ЦБ РФ
        :return: dict
        """
        result = {}

        try:
            response = requests.get(CURRENCIES_VOC_URL).text
            tree = ETree.fromstring(response)
            for item in tree.iter("Item"):
                id = item.get("ID")
                rus_name = item.find("Name").text
                eng_name = item.find("EngName").text
                result[id] = {"rus_name": rus_name, "eng_name": eng_name}
        except requests.RequestException as e:
            raise APIException(f"Ошибка! Не удалось получить справочник валют с сайта {CURRENCIES_VOC_URL} ({type(e).__name__})")
        except Exception as e:
            raise APIException(f"Ошибка! Не удалось разобрать справочник валют, полученный с сайта {CURRENCIES_VOC_URL} ({type(e).__name__})")

        return result


    def fill(self):
        """
        заполняет хранилище данными с сайта ЦБ РФ, используя словарь валют
        :return: None
        """
        self.reset()
        self._cached_date = RatesStorage.current_date()
        requested_url = f"{RATES_URL_PREFIX}{self._cached_date}"
        vocabulary = RatesStorage.get_vocabulary()

        try:
            response = requests.get(requested_url).text
            tree = ETree.fromstring(response)

            for item in tree.iter('Valute'):
                id = item.get("ID")
                currency_data = vocabulary[id]
                currency_data["code"] = item.find("CharCode").text
                currency_data["rub_rate"] = float(item.find("VunitRate").text.replace(",", "."))
                self._data_write_only.append(currency_data)

            # искусственнно дополняем данные российским рублём
            self._data_write_only.append({
                "code": "RUR",
                "rus_name": "Российский рубль",
                "eng_name": "Russian Ruble",
                "rub_rate": 1.0
            })

            self._data_read_only = copy.deepcopy(self._data_write_only)
        except requests.RequestException as e:
            raise APIException(f"Ошибка! Не удалось получить информацию о курсах валют с сайта {requested_url} ({type(e).__name__})")
        except Exception as e:
            raise APIException(f"Ошибка! Не удалось разобрать XML, полученный с сайта {requested_url} ({type(e).__name__})")

    def find_currency_by_code(self, code: str) -> dict:
        """
        находит валюту по ее коду
        :param code: str
        :return: dict('rus_name': str, 'eng_name': str, 'code': str, 'rub_rate': float)
        """
        filtered = list(filter(lambda currency: currency["code"] == code, self.data))
        return None if len(filtered) == 0 else filtered[0]

    def get_currency_data(self, request: str) -> dict:
        """
        возвращает информацию о запрашиваемой валюте
        1) пытается найти валюту по строгому соответствию трёхбуквенного кода, английского или русского названий
        2) если п. 1 не сработал, ищет валюту по расстоянию Левенштейна, сопоставляя запрос с английским и русским названиям
        :param request: код валюты либо ее название
        :return: dict('rus_name': str, 'eng_name': str, 'code': str, 'rub_rate': float)
        """

        def equality_comparator(currency, request):
            """
            собственно функция-компаратор для поиска валюты
            :param currency: dict
            :param request: str
            :return: boolean
            """
            lower_request = request.lower()
            return currency["code"].lower() == lower_request or \
                currency["rus_name"].lower() == lower_request or \
                    currency["eng_name"].lower() == lower_request

        equality_filtered = list(filter(lambda currency: equality_comparator(currency, request), self.data))

        if (len(equality_filtered)):
            return equality_filtered[0]

        lev_distances = []
        for currency in self.data:
            rus_distance = distance(currency["rus_name"].lower(), request.lower())
            eng_distance = distance(currency["eng_name"].lower(), request.lower())
            lev_distances.append({"code": currency["code"], "distance": min(rus_distance, eng_distance)})
        lev_distances.sort(key=lambda x:x["distance"])

        return self.find_currency_by_code(lev_distances[0]["code"]) if lev_distances[0]["distance"] <= 3 else None

