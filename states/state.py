from aiogram.dispatcher.filters.state import StatesGroup, State


class answer(StatesGroup):
    A1 = State()
    A2 = State()


class language(StatesGroup):
    lang = State()


class questions(StatesGroup):
    answer = State()


class RegistrationStates(StatesGroup):
    lang = State()
    name = State()
    phone = State()
    end = State()
    number = State()
    help = State()
    contact = State()
    waiting_for_parameters = State()  # Ожидание ввода параметров A, B, C, X, Y, Z
    waiting_for_file = State()        # Ожидание загрузки Excel-файла
    address = State()
    status = State()
    employees = State()
    custom_status = State()


class TimeSelection(StatesGroup):
    time = State()


class ImageCollection(StatesGroup):
    waiting_for_images = State()