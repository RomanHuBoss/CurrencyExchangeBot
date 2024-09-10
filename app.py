import telebot
import re

from settings import TELEBOT_TOKEN
from extensions import API, APIException

bot = telebot.TeleBot(TELEBOT_TOKEN)

@bot.message_handler(commands=['help', 'start'])
def send_welcome(message):
    """
    отправка приветственного сообщения с информацией о доступных командах
    :param message: object
    :return: None
    """
    bot.reply_to(message, """\
Привет! Я бот, конвертирующий валюты.

1) Введите команду /values, чтобы ознакомиться со справочником валют.

2) Введите команду /rates, чтобы ознакомиться с курсами валют.

3) Чтобы узнать, какую сумму в конвертируемой валюте надо потратить для приобретения целевой валюты, введите следующую команду:

<целевая валюта> <конвертируемая валюта> <сумма в целевой валюте>

Кстати, в угловых скобках можно вводить как коды, так и русские или английские названия валют.

А еще, если вы допустите опечатку в названии валюты, я все равно постараюсь это название распознать, используя метрику сопоставления слов "Расстояние Левенштейна"!

Чтобы повторно вывести эту справку, наберите /start или /help
""")

@bot.message_handler(commands=['values'])
def send_vocabulary(message):
    """
    отправка справочника доступных для конвертации валют
    :param message: object
    :return: None
    """
    bot.send_message(message.chat.id, API.get_vocabulary())

@bot.message_handler(commands=['rates'])
def send_rates(message):
    """
    отправка курсов валют
    :param message: object
    :return: None
    """
    bot.send_message(message.chat.id, API.get_rates())

@bot.message_handler(func=lambda message: True)
def handle_message(message):
    """
    отправка результата конвертации валют
    :param message: object
    :return: None
    """
    try:
        regex = r'^\s*<([^>]+)>\s*<([^>]+)>\s<([^>]+)>\s*$'
        match = re.match(regex, message.text)
        if match is None:
            raise APIException(f"Некорректный формат запроса на конвертацию валют ({APIException.__name__})")

        bot.send_message(message.chat.id, API.get_price(match[1], match[2], match[3]))
    except APIException as e:
        bot.send_message(message.chat.id, e)


bot.infinity_polling()

