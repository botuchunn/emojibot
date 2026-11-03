"""
premium_emoji.py — botdagi barcha oddiy emojilarni PREMIUM (custom) emojiga
avtomatik almashtiradi.

QANDAY ISHLAYDI
  * Kod ichidagi matnlarni o'zgartirish shart emas. Bot Telegramga so'rov
    yuborishdan oldin (middleware orqali) matndagi har bir oddiy emojini
    topadi va unga custom_emoji entity biriktiradi.
  * Inline tugmalardagi bosh emoji ``icon_custom_emoji_id`` ga aylantiriladi.
  * Agar biror emoji uchun ID kiritilmagan bo'lsa, u oddiy emoji bo'lib qoladi
    (hech narsa buzilmaydi).

ID LARNI QANDAY KIRITISH (admin uchun)
  1. Botga /pe_add yuboring.
  2. Premium emojilarni xabar qilib yuboring (xohlagancha, bitta xabarda ham bo'ladi).
     Bot har bir premium emojining asosiy (oddiy) belgisini aniqlab,
     avtomatik saqlaydi: 👋 premium -> 👋 almashtiriladi.
  3. /pe_done — tugatish.
  Qo'shimcha: /pe_list — ro'yxat, /pe_del <emoji> — o'chirish.

  ID ro'yxati bor bo'lsa: /pe_ids buyrug'idan keyin ID larni yozing (har qanday
  formatda). Bot har bir ID ning asosiy emojisini Telegramdan o'zi so'rab
  aniqlaydi va saqlaydi — qaysi ID qaysi emojiga tegishli ekanini bilish shart emas.

  Mapping ``premium_emoji.json`` faylida saqlanadi, bot qayta ishga
  tushirilmasdan darhol kuchga kiradi.
"""

import json
import logging
import os
import re
from typing import Callable, Dict, List, Optional

from aiogram import F, Router
from aiogram.client.session.middlewares.base import BaseRequestMiddleware
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    InlineKeyboardMarkup,
    KeyboardButton,
    Message,
    MessageEntity,
    ReplyKeyboardMarkup,
)

log = logging.getLogger(__name__)

PE_FILE = os.path.join(os.path.dirname(__file__), "premium_emoji.json")
VS16 = "\ufe0f"

# {"👋": "5368324170671202286", ...}  (kalit VS16 siz saqlanadi)
_MAP: Dict[str, str] = {}
_REGEX: Optional[re.Pattern] = None


def _utf16_len(s: str) -> int:
    return len(s.encode("utf-16-le")) // 2


def _norm(ch: str) -> str:
    return ch.replace(VS16, "")


# ---------------------------------------------------------------- storage

def _rebuild_regex() -> None:
    global _REGEX
    if not _MAP:
        _REGEX = None
        return
    keys = sorted(_MAP.keys(), key=len, reverse=True)
    parts = []
    for k in keys:
        # har bir belgidan keyin ixtiyoriy VS16 (⬅️, ℹ️, ✍️ kabi emojilar uchun)
        parts.append("".join(re.escape(c) + VS16 + "?" for c in k))
    _REGEX = re.compile("|".join(parts))


def load_map() -> Dict[str, str]:
    global _MAP
    try:
        with open(PE_FILE, encoding="utf-8") as f:
            raw = json.load(f)
        _MAP = {_norm(k): str(v) for k, v in raw.items() if v}
    except FileNotFoundError:
        _MAP = {}
    except Exception:
        log.exception("premium_emoji.json o'qishda xato")
        _MAP = {}
    _rebuild_regex()
    return _MAP


def save_map() -> None:
    tmp = PE_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(_MAP, f, ensure_ascii=False, indent=2)
    os.replace(tmp, PE_FILE)
    _rebuild_regex()


def set_emoji(char: str, emoji_id: str) -> None:
    _MAP[_norm(char)] = str(emoji_id)


def del_emoji(char: str) -> bool:
    return _MAP.pop(_norm(char), None) is not None


# ------------------------------------------------------------- conversion

def add_entities(text: Optional[str], entities: Optional[List[MessageEntity]]):
    """Matndagi oddiy emojilarga custom_emoji entity qo'shadi.

    Emoji belgisi matnda qoladi (entity uning ustiga qo'yiladi), shuning uchun
    boshqa entity'larning offsetlari o'zgarmaydi.
    """
    if not text or _REGEX is None:
        return text, entities

    entities = list(entities or [])
    covered = [(e.offset, e.offset + e.length) for e in entities if e.type == "custom_emoji"]
    added = False

    for m in _REGEX.finditer(text):
        start = _utf16_len(text[: m.start()])
        length = _utf16_len(m.group(0))
        if any(s < start + length and start < e for s, e in covered):
            continue  # bu joyda allaqachon custom emoji bor
        emoji_id = _MAP.get(_norm(m.group(0)))
        if not emoji_id:
            continue
        entities.append(
            MessageEntity(type="custom_emoji", offset=start, length=length, custom_emoji_id=emoji_id)
        )
        added = True

    if not added:
        return text, entities or None
    entities.sort(key=lambda e: e.offset)
    return text, entities


def _lead_emoji(text: str):
    """Tugma matni boshidagi emoji (agar mapping'da bo'lsa) -> (id, qolgan matn)."""
    if not text or _REGEX is None:
        return None, text
    m = _REGEX.match(text)
    if not m:
        return None, text
    emoji_id = _MAP.get(_norm(m.group(0)))
    if not emoji_id:
        return None, text
    rest = text[m.end():].lstrip()
    if not rest:  # faqat emoji bo'lsa, tugma matni bo'sh bo'lib qolmasin
        return None, text
    return emoji_id, rest


def convert_markup(markup):
    if isinstance(markup, InlineKeyboardMarkup):
        rows = []
        changed = False
        for row in markup.inline_keyboard:
            new_row = []
            for btn in row:
                if btn.icon_custom_emoji_id is None:
                    emoji_id, rest = _lead_emoji(btn.text)
                    if emoji_id:
                        btn = btn.model_copy(update={"text": rest, "icon_custom_emoji_id": emoji_id})
                        changed = True
                new_row.append(btn)
            rows.append(new_row)
        return markup.model_copy(update={"inline_keyboard": rows}) if changed else markup

    if isinstance(markup, ReplyKeyboardMarkup):
        rows = []
        changed = False
        for row in markup.keyboard:
            new_row = []
            for btn in row:
                if isinstance(btn, KeyboardButton) and btn.icon_custom_emoji_id is None:
                    emoji_id, rest = _lead_emoji(btn.text)
                    if emoji_id:
                        btn = btn.model_copy(update={"text": rest, "icon_custom_emoji_id": emoji_id})
                        changed = True
                new_row.append(btn)
            rows.append(new_row)
        return markup.model_copy(update={"keyboard": rows}) if changed else markup

    return markup


class PremiumEmojiMiddleware(BaseRequestMiddleware):
    """Har bir chiquvchi so'rovni (sendMessage, editMessageText, captionlar,
    tugmalar) premium emojiga o'giradi."""

    async def __call__(self, make_request, bot, method):
        if _MAP:
            try:
                self._patch(method)
            except Exception:
                log.exception("premium emoji almashtirishda xato (oddiy emoji yuboriladi)")
        return await make_request(bot, method)

    @staticmethod
    def _patch(method) -> None:
        # HTML/Markdown ishlatilgan xabarlarga tegmaymiz (offsetlar buziladi)
        # aiogram parse_mode ni Default(...) sentinel sifatida ham saqlaydi —
        # faqat haqiqiy str (HTML/Markdown) bo'lsa o'tkazib yuboramiz.
        if isinstance(getattr(method, "parse_mode", None), str):
            pass
        else:
            if getattr(method, "text", None) and hasattr(method, "entities"):
                t, e = add_entities(method.text, method.entities)
                method.entities = e
            if getattr(method, "caption", None) and hasattr(method, "caption_entities"):
                t, e = add_entities(method.caption, method.caption_entities)
                method.caption_entities = e

        rm = getattr(method, "reply_markup", None)
        if rm is not None:
            method.reply_markup = convert_markup(rm)


# ------------------------------------------------------- admin buyruqlari

class PEState(StatesGroup):
    learning = State()


def build_router(is_admin: Callable[[int], bool]) -> Router:
    r = Router(name="premium_emoji")

    @r.message(Command("pe_add"))
    async def pe_add(message: Message, state: FSMContext):
        if not is_admin(message.from_user.id):
            return
        await state.set_state(PEState.learning)
        await message.answer(
            "Premium emojilarni yuboring (bir nechta bo'lishi mumkin).\n"
            "Har biri o'zining oddiy belgisi o'rniga ishlatiladi.\n"
            "Tugatish: /pe_done"
        )

    @r.message(Command("pe_ids"))
    async def pe_ids(message: Message):
        if not is_admin(message.from_user.id):
            return
        raw = (message.text or "").split(maxsplit=1)
        ids = list(dict.fromkeys(re.findall(r"\d{10,20}", raw[1] if len(raw) > 1 else "")))
        if not ids:
            await message.answer("Ishlatilishi: /pe_ids 5368324170671202286 5368324170671202287 ...")
            return

        found = {}
        for i in range(0, len(ids), 200):
            chunk = ids[i:i + 200]
            try:
                stickers = await message.bot.get_custom_emoji_stickers(custom_emoji_ids=chunk)
            except Exception as e:
                await message.answer(f"Telegramdan so'rashda xatolik: {e}")
                return
            for st in stickers:
                if st.custom_emoji_id and st.emoji:
                    found[st.custom_emoji_id] = st.emoji

        saved, dup, missing = [], [], []
        seen = set()
        for cid in ids:  # xabardagi tartib: bir emoji uchun birinchi ID olinadi
            base = found.get(cid)
            if not base:
                missing.append(cid)
                continue
            key = _norm(base)
            if key in seen:
                dup.append(f"{base} {cid}")
                continue
            seen.add(key)
            set_emoji(base, cid)
            saved.append(f"{base} {cid}")
        save_map()

        text = f"Saqlandi ({len(saved)} ta):\n" + ("\n".join(saved) or "-")
        if dup:
            text += "\n\nBir xil emoji takrorlandi (o'tkazib yuborildi):\n" + "\n".join(dup)
        if missing:
            text += "\n\nTopilmadi (ID noto'g'ri bo'lishi mumkin):\n" + "\n".join(missing)
        await message.answer(text)

    @r.message(Command("pe_done"))
    async def pe_done(message: Message, state: FSMContext):
        if not is_admin(message.from_user.id):
            return
        await state.clear()
        await message.answer(f"Tayyor. Jami {len(_MAP)} ta premium emoji saqlangan.")

    @r.message(Command("pe_list"))
    async def pe_list(message: Message):
        if not is_admin(message.from_user.id):
            return
        if not _MAP:
            await message.answer("Hali premium emoji qo'shilmagan. /pe_add")
            return
        text = ""
        ents: List[MessageEntity] = []
        for ch, eid in _MAP.items():
            off = _utf16_len(text)
            text += ch
            ents.append(MessageEntity(type="custom_emoji", offset=off, length=_utf16_len(ch), custom_emoji_id=eid))
            text += f" {ch}  ->  {eid}\n"
        await message.answer(text, entities=ents)

    @r.message(Command("pe_del"))
    async def pe_del(message: Message):
        if not is_admin(message.from_user.id):
            return
        arg = (message.text or "").split(maxsplit=1)
        if len(arg) < 2:
            await message.answer("Ishlatilishi: /pe_del 👋")
            return
        removed = [c for c in re.findall(r"\S", arg[1]) if c != VS16 and del_emoji(c)]
        save_map()
        await message.answer(f"O'chirildi: {' '.join(removed) or 'hech narsa topilmadi'}")

    @r.message(PEState.learning, F.entities)
    async def pe_learn(message: Message):
        if not is_admin(message.from_user.id):
            return
        text = message.text or ""
        u16 = text.encode("utf-16-le")
        saved = []
        for e in message.entities or []:
            if e.type != "custom_emoji" or not e.custom_emoji_id:
                continue
            base = u16[e.offset * 2:(e.offset + e.length) * 2].decode("utf-16-le")
            if not base:
                continue
            set_emoji(base, e.custom_emoji_id)
            saved.append(base)
        if not saved:
            await message.answer("Bu xabarda premium emoji topilmadi. Premium emoji yuboring yoki /pe_done.")
            return
        save_map()
        await message.answer(f"Saqlandi: {' '.join(saved)}  (jami {len(_MAP)} ta)")

    @r.message(PEState.learning)
    async def pe_learn_other(message: Message):
        if message.text and message.text.startswith("/"):
            return
        await message.answer("Premium emoji yuboring yoki /pe_done bilan tugating.")

    return r


def setup(dp, bot, is_admin: Callable[[int], bool]) -> None:
    """main() ichida chaqiriladi: mappingni yuklaydi, middleware va routerni ulaydi."""
    load_map()
    bot.session.middleware(PremiumEmojiMiddleware())
    dp.include_router(build_router(is_admin))
    log.info("premium_emoji: %d ta emoji yuklandi", len(_MAP))
