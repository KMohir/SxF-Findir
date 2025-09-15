from aiogram import types
from aiogram.dispatcher.handler import CancelHandler
from aiogram.dispatcher.middlewares import BaseMiddleware
from utils.db_api.security_db import check_user_access, check_group_access, is_admin
from utils.logger import log_security_event, log_group_event
from data.config import SECURITY_ENABLED, AUTO_LEAVE_GROUPS

class SecurityMiddleware(BaseMiddleware):
    """
    Middleware для проверки безопасности пользователей и групп
    """
    
    def __init__(self):
        super().__init__()

    async def on_process_message(self, message: types.Message, data: dict):
        """Проверка безопасности для каждого сообщения"""
        
        if not SECURITY_ENABLED:
            return
        
        user_id = message.from_user.id
        chat_type = message.chat.type
        
        # Исключения для админов
        if await is_admin(user_id):
            return
        
        # Проверка в приватных чатах
        if chat_type == 'private':
            await self._check_private_chat(message)
        
        # Проверка в группах
        elif chat_type in ['group', 'supergroup']:
            await self._check_group_chat(message)
    
    async def _check_private_chat(self, message: types.Message):
        """Проверка доступа в приватном чате"""
        user_id = message.from_user.id
        
        # Разрешаем команду /start для незарегистрированных
        if message.text and message.text.startswith('/start'):
            return
        
        if not await check_user_access(user_id):
            log_security_event("ACCESS_DENIED", user_id, "Попытка использования бота без регистрации")
            
            await message.answer(
                "❌ <b>Доступ запрещён</b>\n\n"
                "🔐 Для использования бота необходима регистрация и одобрение администратором.\n\n"
                "📝 Напишите /start для начала процесса регистрации.",
                parse_mode='HTML'
            )
            raise CancelHandler()
    
    async def _check_group_chat(self, message: types.Message):
        """Проверка доступа в группе"""
        chat_id = message.chat.id
        
        if not await check_group_access(chat_id):
            log_group_event("UNAUTHORIZED_GROUP", chat_id, f"Группа: {message.chat.title}")
            
            if AUTO_LEAVE_GROUPS:
                await message.answer(
                    "❌ <b>Группа не авторизована</b>\n\n"
                    "🚪 Бот покидает группу...\n"
                    "📞 Для получения доступа обратитесь к администратору.",
                    parse_mode='HTML'
                )
                await message.bot.leave_chat(chat_id)
            else:
                await message.answer(
                    "⚠️ <b>Группа не авторизована</b>\n\n"
                    "📝 Обратитесь к администратору для получения доступа к боту.",
                    parse_mode='HTML'
                )
            
            raise CancelHandler()

    async def on_process_callback_query(self, callback_query: types.CallbackQuery, data: dict):
        """Проверка безопасности для callback запросов"""
        
        if not SECURITY_ENABLED:
            return
        
        user_id = callback_query.from_user.id
        
        # Исключения для админов
        if await is_admin(user_id):
            return
        
        # Проверка только в приватных чатах
        if callback_query.message.chat.type == 'private':
            if not await check_user_access(user_id):
                log_security_event("CALLBACK_ACCESS_DENIED", user_id, f"Data: {callback_query.data}")
                
                await callback_query.answer(
                    "❌ Доступ запрещён! Пройдите регистрацию через /start",
                    show_alert=True
                )
                raise CancelHandler() 