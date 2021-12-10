from configparser import ConfigParser
import re
import datetime
import time

from requests import Timeout

from tgBot import UpdateException, MessageHandlerAbs, TelegramBotCreator, Keyboard, Options, InlineKeyboard, \
    ReplyKeyboard, tg_object_classes, RemoveReplyKeyboard


def to_keyboard(keys: list, inline=False, k=2):
    result = []
    for index, key in enumerate(keys):
        result.append(InlineKeyboard.InlineButton(key[0], key[1]) if inline else ReplyKeyboard.ReplyButton(key))
        if index % k == k - 1 and index < len(keys) - 1:
            result.append(Keyboard.NewLine)
    return InlineKeyboard(result) if inline else ReplyKeyboard(result)


class AccessGuard:
    def __init__(self):
        self.permissions = {}
        self.last_role = None

    def __mcaller(self, method):
        self.permissions[method] = self.last_role
        self.last_role = None
        return method

    def access(self, role):
        self.last_role = role
        return self.__mcaller

    def get_permission(self, method):
        if method in self.permissions:
            return self.permissions[method]
        return "any"


ag = AccessGuard()


smiles = {
    "back": "🔙",
    "accept": "✅",
    "deny": "🚫",
    "male": "👨‍🦳",
    "female": "👩"
}


class MessageHandler(MessageHandlerAbs):
    @staticmethod
    def new_user(user, bot):
        bot.data["users"].append(str(user.id))

        if str(user.id) not in bot.data["admins"]:
            user.send("Салют! Присоединяйтесь к ежегодной игре тайного санты. "
                      "Каждый участник получит подарок, так как каждый участник "
                      "не только сам сможет стать сантой, но и у каждого из вас "
                      "будет свой тайный санты. Правила игры просты, жмите кнопку "
                      "участвовать и давайте знакомиться. Игра полностью анонимная, "
                      "контактные данные не будут переданы ни одному из участников игры.",
                      to_keyboard([
                          "Участвовать" + smiles["accept"]
                      ]))
            user.data["stage"] = "start_idle"
        else:
            user.send("Приветствуем администратора", to_keyboard(["В меню" + smiles["back"]]))
            user.data["stage"] = "start"

    @staticmethod
    def start(user, bot):
        MessageHandler.open_menu(user, bot)

    @staticmethod
    def undefined_action(user, bot, open_menu=True):
        user.send("Неопознанное действие!")
        if open_menu:
            MessageHandler.open_menu(user, bot)

    @staticmethod
    def undefined_data(user, bot):
        user.send("Данные указаны в неверном формате!")

    @staticmethod
    def start_idle(user, bot):
        if smiles["accept"] not in user.get():
            MessageHandler.undefined_action(user, bot, False)
            return
        user.data["stage"] = "blitz_sex"
        user.send("Укажите ваш пол", to_keyboard(["Мужской", "Женский"]))

    @staticmethod
    def blitz_sex(user, bot):
        if user.get().lower() not in ["мужской", "женский"]:
            user.send("Пол указан неверно, попробуйте еще раз")
            return

        user.data["sex"] = user.get().lower()
        user.send("Отлично, теперь укажите дату вашего рождения в формате: 01.01.1970", RemoveReplyKeyboard())
        user.data["stage"] = "blitz_birth"

    @staticmethod
    def blitz_birth(user, bot):
        try:
            user.data["birthdate"] = parse_date(user.get())
            user.data["stage"] = "blitz_hobby"
            user.send("Отлично, теперь расскажите немного о себе и о своих хобби (не более 100 символов)")
        except:
            user.send("Дата введена в неверном формате. Попробуйте еще раз")

    @staticmethod
    def blitz_hobby(user, bot):
        if len(user.get()) > 100:
            user.send("Вы ввели слишком длинный текст. Попробуйте еще раз (не более 100 символов)")
            return

        user.data["stage"] = "idle"
        user.data["hobby"] = user.get()
        user.send("Вы зарегистрированы. Теперь осталось дождаться окончания первого этапа "
                  "набора участников. 11 декабря мы назначим вас тайным санта и пришлем "
                  "информацию об участнике, чтобы вы смогли подобрать подходящий сувенир для него. "
                  "Так же ваш тайный санта получит информаицю о вас) Никто не останется без внимания.")

    @staticmethod
    def send_to_all_users(bot, message, keyboard=None, to_admins=False):
        admins = bot.data["admins"]
        users = bot.data["users"]
        for user_id in users:
            if to_admins and user_id not in admins:
                continue
            bot.load_user(user_id)
            user = bot.get_users()[user_id]
            if "notifies" in user.data:
                continue

            if keyboard:
                user.send(message, keyboard)
            else:
                user.send(message)

    @staticmethod
    def idle(user, bot):
        user.send("Дождитесь окончания периода регистрации 11 декабря")

    @staticmethod
    def open_menu(user, bot):
        user.data["stage"] = "menu"
        user.send("Меню", to_keyboard([
            "Участники" + smiles["male"],
            "Рассылка" + smiles["accept"]
        ]))

    @staticmethod
    def menu(user, bot):
        if smiles["back"] in user.get():
            MessageHandler.open_menu(user, bot)
        elif smiles["male"] in user.get():
            for user_id in bot.data["users"]:
                bot.load_user(user_id)
                o_user = bot.get_users()[user_id]
                if "active" in o_user.data and o_user.data["active"]:
                    user.send(get_user_str(o_user), to_keyboard([("Исключить", o_user.id)]))
        elif smiles["accept"] in user.get():
            user.send("Введите сообщение для рассылки", to_keyboard(["В меню" + smiles["back"]]))
            user.data["stage"] = "notify"
        else:
            MessageHandler.undefined_action(user, bot)

    @staticmethod
    def notify(user, bot):
        if smiles["back"] not in user.get():
            message = user.get()
            MessageHandler.send_to_all_users(bot, message, keyboard=to_keyboard(
                [("Отказаться от рассылки" + smiles["deny"], f"-")]
                , inline=True))

        MessageHandler.open_menu(user, bot)

    @staticmethod
    def access_deny(user, bot):
        user.send(f"Вам запрещено данное действие")
        MessageHandler.open_menu(user, bot)

    @staticmethod
    def handle_text(user, bot):
        admin = user.id in bot.data["admins"]
        method_name = user.data["stage"]
        method = eval(f"MessageHandler.{method_name}")
        permission = ag.get_permission(method)

        if permission == "any":
            method(user, bot)
        elif permission == "admin" and admin:
            method(user, bot)
        else:
            MessageHandler.access_deny(user, bot)

    @staticmethod
    def handle_click(user, update, bot):
        source = update.inner_source["data"]
        if source == "-":
            user.data["notifies"] = False
            user.send("Вы отказались от рассылки")
            return
        if not source.startswith("+"):
            bot.load_user(source)
            user = bot.get_users()[source]
            user.data["active"] = False
            message = f"Администратор {user.id} исключил Санту: {source}"
            MessageHandler.send_to_all_users(bot, message, to_keyboard([("Вернуть", f"+{source}")], inline=True),
                                             to_admins=True)
        else:
            user_id = source[1:]
            bot.load_user(user_id)
            user = bot.get_users()[user_id]
            user.data["active"] = True
            message = f"Администратор {user.id} вернул Санту: {user_id}"
            MessageHandler.send_to_all_users(bot, message, to_admins=True)

    @staticmethod
    def handle(user, update, bot):
        if type(update) == tg_object_classes.Updater.CallbackQuery:
            MessageHandler.handle_click(user, update, bot)
        else:
            MessageHandler.handle_text(user, bot)


def get_age(birth):
    now = datetime.datetime.now()
    if birth > now:
        return 0
    diff = (now - birth).total_seconds()
    if diff < 0:
        diff = -diff + time.time()
    return datetime.datetime.fromtimestamp(diff).year


def get_user_str(user):
    user_id = user.id
    sex = user.data["sex"]
    age = get_age(user.data["birthdate"])
    hobby = user.data["hobby"]
    return f"ID: {user_id}\nПол: {sex}\nВозраст: {age}\nХобби: {hobby}"


def hail_if_birthday(user):
    now = datetime.datetime.now()
    birthday = user.data["birthdate"]
    if now.month == birthday.month and now.day == birthday.day and now.hour + 2 == 13:
        if "hail" not in user.data or not user.data["hail"]:
            user.send("Поздравляем вас с днем рождения. В честь дня рождения в кофейни ждет ваш "
                      "праздничный бестактный кофе. Действует при предъявлении паспорта.", keyboard=to_keyboard(
                          [("Отказаться от рассылки" + smiles["deny"], f"-")], inline=True))
            user.data["hail"] = True
    else:
        user.data["hail"] = False


def switch(bot):
    pass


def loop_function(bot):
    users = bot.data["users"]
    for user_id in users:
        bot.load_user(user_id)
        user = bot.get_users()[user_id]
        if "birthdate" in user.data and "notifies" not in user.data:
            hail_if_birthday(user)
        if "hobby" not in user.data or "active" in user.data:
            continue

        message = f"Новый Санта:\n{get_user_str(user)}"
        MessageHandler.send_to_all_users(bot, message, to_keyboard([("Исключить", f"{user.id}")],
                                                                   inline=True), to_admins=True)
        user.data["active"] = True
        return


def parse_date(datestr):
    d, m, y = map(int, datestr.split("."))
    return datetime.datetime(year=y, month=m, day=d)


def main():
    config = ConfigParser()
    config.read("config.ini")
    config = config["DEFAULT"]
    cooldown = int(config["cooldown"])
    token = config["access_token"]
    admins = config["admins"].split(",")

    options = Options()
    options.request_timeout = 3
    options.serializer_path = "./serialized_data"
    options.loop_function = loop_function
    options.check_interval = cooldown

    bot = TelegramBotCreator(token, MessageHandler, options)
    bot.data["admins"] = admins
    if "users" not in bot.data:
        bot.data["users"] = []
    if "step2" not in bot.data:
        bot.data["step2"] = False

    while True:
        try:
            bot.mainloop()
        except (UpdateException, Timeout, ConnectionError):
            pass


if __name__ == "__main__":
    main()
