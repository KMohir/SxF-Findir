from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

from translation import _


def get_lang_for_button(message):
    button = ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="Yangiliklarni soat nechida olishni hohlaysiz?")
            ],
            [
                KeyboardButton(text="FAQ ?")
            ],
            [
                KeyboardButton(text="Centris Towers bilan bog'lanish")
            ],
            [
                KeyboardButton(text="Bino bilan tanishish")
            ],
        ],
        resize_keyboard=True
    )
    return button


def key():
    keyboardcontakt = ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="Kontakni yuborish", request_contact=True)
            ],
        ],
        resize_keyboard=True
    )
    return keyboardcontakt