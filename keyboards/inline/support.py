import random

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.callback_data import CallbackData

from data.config import support_ids
from db import db
from loader import dp
from translation import _

support_callback = CallbackData("ask_support", "messages", "user_id", "as_user")
cancel_support_callback = CallbackData("cancel_support", "user_id")


async def check_support_available(support_id):
    state = dp.current_state(chat=support_id, user=support_id)
    state_str = str(
        await state.get_state()
    )
    if state_str == "in_support":
        return
    else:
        return support_id


async def get_support_manager():
    random.shuffle(support_ids)
    for support_id in support_ids:
        # Проверим если оператор в данное время не занят
        support_id = await check_support_available(support_id)

        # Если такого нашли, что выводим
        if support_id:
            return support_id
    else:
        return


async def support_keyboard(message,messages, user_id=None):
    lang = db.get_lang(message.from_user.id)
    keyboard = InlineKeyboardMarkup()
    if user_id:
        # Есле указан второй айдишник - значит эта кнопка для оператора

        contact_id = int(user_id)
        as_user = "no"
        text = _("Javob yozish uchun shu tugmani bosing",lang)
        keyboard.add(
            InlineKeyboardButton(
                text=text,
                callback_data=support_callback.new(
                    messages=messages,
                    user_id=contact_id,
                    as_user=as_user
                )
            )
        )

    else:
        # Есле не указан второй айдишник - значит эта кнопка для пользователя
        # и нужно подобрать для него оператора

        contact_id = await get_support_manager()
        as_user = "yes"
        if messages == "many" and contact_id is None:
            # Если не нашли свободного оператора - выходим и говорим, что его нет
            return False
        elif messages == "one" and contact_id is None:
            contact_id = random.choice(support_ids)

        if messages == "one":
            text = _("Texnik yordamga ga xabar yozing",lang)



            keyboard.add(
                InlineKeyboardButton(
                    text=text,
                    callback_data=support_callback.new(
                        messages=messages,
                        user_id=contact_id,
                        as_user=as_user
                    )
                )
            )
            keyboard.add(
                InlineKeyboardButton(
                    text='/',
                    callback_data=cancel_support_callback.new(
                        user_id=contact_id
                    )
                )
            )

            return keyboard


    return keyboard


def cancel_support(messages,user_id):
    lang = db.get_lang(messages.from_user.id)
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=_("Savolimga javob oldim",lang),
                    callback_data=cancel_support_callback.new(
                        user_id=user_id
                    )
                )
            ]
        ]
    )


langMenu=InlineKeyboardMarkup(row_width=2)

langUZ=InlineKeyboardButton(text="O'zbek",callback_data='lang_uz')
langRU=InlineKeyboardButton(text="Русский",callback_data='lang_ru')

langMenu.insert(langUZ)
langMenu.insert(langRU)
def yesno(message,user_id):
    lang = db.get_lang(message.from_user.id)
    ha=_("Ha",lang)
    yoq=_("Yo'q",lang)
    langokno=InlineKeyboardMarkup(row_width=2)

    langok=InlineKeyboardButton(text=ha,callback_data='Ha')
    langno=InlineKeyboardButton(text=yoq,callback_data="yo'q")

    langokno.insert(langok)
    langokno.insert(langno)
    return langokno

