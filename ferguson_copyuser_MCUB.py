# requires: aiohttp, requests
# author: @fergexe 
# version: 1.0.1
# description: CopyUser - копирование профиля пользователя (работает по reply/@username/ID)
# scop: kernel (min) v([__lastest__])

from utils import answer, get_args
from telethon.tl.functions.users import GetFullUserRequest
from telethon.tl.functions.account import UpdateProfileRequest, UpdateEmojiStatusRequest
from telethon.tl.functions.photos import UploadProfilePhotoRequest, DeletePhotosRequest
from telethon import types
import io
import requests
import os
import tempfile


def register(kernel):
    MODULE_NAME = "copyuser"
    
    # Инициализация конфига
    if MODULE_NAME not in kernel.config:
        kernel.config[MODULE_NAME] = {"lang": "ru"}
        kernel.save_config()
    
    MESSAGES = {
        "ru": {
            "user_not_found": "<emoji document_id=5210952531676504517>❌</emoji><b>Не удалось найти пользователя!</b>",
            "specify_user": "<emoji document_id=5832251986635920010>➡️</emoji><b>Укажите пользователя (reply/@username/ID)!</b>",
            "profile_copied": "<emoji document_id=5397916757333654639>➕</emoji> <b>Профиль пользователя скопирован!</b>",
            "username_not_found": "<emoji document_id=5240241223632954241>🚫</emoji> <b>Пользователь не найден!</b>",
            "invalid_username": "<emoji document_id=5240241223632954241>🚫</emoji> <b>Неверный формат юзернейма/ID.</b>",
            "backup_saved": "<emoji document_id=5294096239464295059>🔵</emoji> <b>Ваш данный профиль сохранен. Вы можете вернуть его используя</b> <code>restoreme</code>\n\n<b>⚙️ URL данной Аватарки: {}</b>",
            "no_backup": "❌ <b>Резервная копия не найдена!</b>",
            "profile_restored": "<emoji document_id=5294096239464295059>🔵</emoji> <b>Ваш прошлый профиль возвращен.</b>",
            "error": "😵 Ошибка: {}",
        },
        "en": {
            "user_not_found": "<emoji document_id=5210952531676504517>❌</emoji><b>Failed to find user!</b>",
            "specify_user": "<emoji document_id=5832251986635920010>➡️</emoji><b>Specify user (reply/@username/ID)!</b>",
            "profile_copied": "<emoji document_id=5397916757333654639>➕</emoji> <b>User profile copied!</b>",
            "username_not_found": "<emoji document_id=5240241223632954241>🚫</emoji> <b>User not found!</b>",
            "invalid_username": "<emoji document_id=5240241223632954241>🚫</emoji> <b>Invalid username/ID format.</b>",
            "backup_saved": "<emoji document_id=5294096239464295059>🔵</emoji> <b>Your current profile has been saved. You can restore it using</b> <code>restoreme</code>\n\n<b>⚙️ Current Avatar URL: {}</b>",
            "no_backup": "❌ <b>No backup found!</b>",
            "profile_restored": "<emoji document_id=5294096239464295059>🔵</emoji> <b>Your previous profile has been restored.</b>",
            "error": "😵 Error: {}",
        },
    }
    
    def _lang():
        cfg = kernel.config.get(MODULE_NAME, {})
        return cfg.get("lang", "ru")
    
    def _t(key, *args, **kwargs):
        lang = _lang()
        text = MESSAGES.get(lang, MESSAGES["ru"]).get(key, key)
        if args:
            return text.format(*args)
        return text.format(**kwargs) if kwargs else text
    
    async def upload_to_0x0(photo_bytes):
        """Загружает фото на 0x0.st и возвращает URL"""
        try:
            files = {'file': ('photo.png', photo_bytes)}
            response = requests.post(
                'https://0x0.st',
                files=files,
                data={'secret': True},
                timeout=30
            )
            return response.text.strip()
        except Exception as e:
            kernel.logger.error(f"upload_to_0x0 error: {e}")
            return None
    
    @kernel.register.command("copyuser", alias=["cu"])
    async def copyuser_handler(event):
        """
        Скопировать профиль пользователя
        
        Использование:
            .copyuser [reply/@username/ID]
        """
        try:
            args = get_args(event)
            reply = await event.get_reply_message()
            
            user = None
            
            # Получаем пользователя
            if args:
                try:
                    if args[0].isdigit():
                        user = await kernel.client.get_entity(int(args[0]))
                    else:
                        user = await kernel.client.get_entity(args[0])
                except ValueError:
                    await answer(event, _t("user_not_found"), as_html=True)
                    return
                except Exception:
                    await answer(event, _t("username_not_found"), as_html=True)
                    return
            elif reply:
                user = await reply.get_sender()
            else:
                await answer(event, _t("specify_user"), as_html=True)
                return
            
            # Получаем полную информацию
            full = await kernel.client(GetFullUserRequest(user.id))
            user_info = full.users[0]
            me = await kernel.client.get_me()
            
            # Копируем аватарку
            if full.full_user.profile_photo:
                try:
                    photos = await kernel.client.get_profile_photos(user.id)
                    if photos:
                        # Удаляем текущие аватарки
                        current_photos = await kernel.client.get_profile_photos("me")
                        if current_photos:
                            await kernel.client(DeletePhotosRequest(current_photos))
                        
                        # Скачиваем и загружаем новую
                        photo_path = await kernel.client.download_media(photos[0])
                        await kernel.client(UploadProfilePhotoRequest(
                            file=await kernel.client.upload_file(photo_path)
                        ))
                        if os.path.exists(photo_path):
                            os.remove(photo_path)
                except Exception as e:
                    kernel.logger.debug(f"Avatar copy error: {e}")
            
            # Копируем имя и био
            await kernel.client(UpdateProfileRequest(
                first_name=user_info.first_name if user_info.first_name is not None else "",
                last_name=user_info.last_name if user_info.last_name is not None else "",
                about=full.full_user.about[:70] if full.full_user.about is not None else "",
            ))
            
            # Копируем emoji статус (если premium)
            if hasattr(user_info, 'emoji_status') and user_info.emoji_status and me.premium:
                try:
                    await kernel.client(
                        UpdateEmojiStatusRequest(
                            emoji_status=user_info.emoji_status
                        )
                    )
                except Exception as e:
                    kernel.logger.debug(f"Emoji status copy error: {e}")
            
            await answer(event, _t("profile_copied"), as_html=True)
            
        except Exception as e:
            await kernel.handle_error(e, source=f"{MODULE_NAME}:copyuser", event=event)
            await answer(event, _t("error", str(e)), as_html=True)
    
    @kernel.register.command("backupme", alias=["backupprofile"])
    async def backupme_handler(event):
        """
        Создать резервную копию вашего профиля
        
        Использование:
            .backupme
        """
        try:
            user = await kernel.client.get_me()
            full = await kernel.client(GetFullUserRequest(user.id))
            user_info = full.users[0]
            
            # Получаем аватарку
            avatar_url = None
            photos = await kernel.client.get_profile_photos(user.id)
            if photos:
                photo_bytes = await kernel.client.download_media(photos[0], bytes)
                avatar_url = await upload_to_0x0(photo_bytes)
            
            # Получаем emoji статус
            emoji_status_id = None
            if hasattr(user_info, 'emoji_status') and user_info.emoji_status:
                emoji_status_id = user_info.emoji_status.document_id
            
            # Сохраняем в БД
            backup_data = {
                "first_name": user_info.first_name,
                "last_name": user_info.last_name,
                "about": full.full_user.about,
                "avatar_url": avatar_url,
                "emoji_status_id": emoji_status_id
            }
            
            await kernel.db_set(MODULE_NAME, "backup_data", str(backup_data))
            
            await answer(event, _t("backup_saved", avatar_url or "N/A"), as_html=True)
            
        except Exception as e:
            await kernel.handle_error(e, source=f"{MODULE_NAME}:backupme", event=event)
            await answer(event, _t("error", str(e)), as_html=True)
    
    @kernel.register.command("restoreme", alias=["restoreprofile"])
    async def restoreme_handler(event):
        """
        Восстановить профиль из резервной копии
        
        Использование:
            .restoreme
        """
        try:
            # Получаем из БД
            backup_str = await kernel.db_get(MODULE_NAME, "backup_data")
            
            if not backup_str:
                await answer(event, _t("no_backup"), as_html=True)
                return
            
            # Парсим строку (костыль, но работает)
            # Формат: {'first_name': '...', 'last_name': '...', ...}
            import ast
            try:
                backup_data = ast.literal_eval(backup_str)
            except:
                await answer(event, _t("no_backup"), as_html=True)
                return
            
            me = await kernel.client.get_me()
            
            # Восстанавливаем аватарку
            if backup_data.get("avatar_url"):
                try:
                    # Удаляем текущие
                    current_photos = await kernel.client.get_profile_photos('me')
                    if current_photos:
                        await kernel.client(DeletePhotosRequest(current_photos))
                    
                    # Скачиваем и загружаем
                    response = requests.get(backup_data["avatar_url"], timeout=30)
                    avatar_bytes = io.BytesIO(response.content)
                    
                    await kernel.client(UploadProfilePhotoRequest(
                        file=await kernel.client.upload_file(avatar_bytes)
                    ))
                except Exception as e:
                    kernel.logger.debug(f"Avatar restore error: {e}")
            
            # Восстанавливаем имя и био
            await kernel.client(UpdateProfileRequest(
                first_name=backup_data.get("first_name", "") or "",
                last_name=backup_data.get("last_name", "") or "",
                about=backup_data.get("about", "") or "",
            ))
            
            # Восстанавливаем emoji статус (если premium)
            if backup_data.get("emoji_status_id") and me.premium:
                try:
                    await kernel.client(
                        UpdateEmojiStatusRequest(
                            emoji_status=types.EmojiStatus(
                                document_id=backup_data["emoji_status_id"]
                            )
                        )
                    )
                except Exception as e:
                    kernel.logger.debug(f"Emoji status restore error: {e}")
            
            await answer(event, _t("profile_restored"), as_html=True)
            
        except Exception as e:
            await kernel.handle_error(e, source=f"{MODULE_NAME}:restoreme", event=event)
            await answer(event, _t("error", str(e)), as_html=True)
    
    @kernel.register.command("copyuserlang", alias=["culang"])
    async def copyuser_lang_handler(event):
        """
        Установить язык модуля
        
        Использование:
            .copyuserlang ru | en
        """
        try:
            args = get_args(event)
            
            if not args:
                await answer(
                    event,
                    "<b>Использование:</b> <code>.copyuserlang ru</code> или <code>.copyuserlang en</code>",
                    as_html=True
                )
                return
            
            lang = str(args[0]).lower().strip()
            
            if lang not in ("ru", "en"):
                await answer(
                    event,
                    "<b>Поддерживаются только:</b> <code>ru</code>, <code>en</code>",
                    as_html=True
                )
                return
            
            kernel.config[MODULE_NAME]["lang"] = lang
            kernel.save_config()
            
            await answer(
                event,
                f"✅ <b>Язык установлен:</b> <b>{lang.upper()}</b>",
                as_html=True
            )
            
        except Exception as e:
            await kernel.handle_error(e, source=f"{MODULE_NAME}:lang", event=event)
