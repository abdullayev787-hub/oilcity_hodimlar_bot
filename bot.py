import logging
import asyncio
from datetime import datetime
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder

# ─── SOZLAMALAR ───────────────────────────────────────────────────────────────
TOKEN = "8275356374:AAFAvVfWMPY0UOiIr4G91SjuVQq6I-zZgZ0"
BOSH_RAHBAR_ID = 7674070246

# Filiallar
FILIALLAR = {
    "filial_1": "1-Filial",
    "filial_2": "2-Filial",
    "filial_3": "3-Filial",
}

# Lavozimlar
LAVOZIMLAR = {
    "usta": "🔧 Usta",
    "shogird": "🔧 Shogird yordamchi",
    "servis_rahbar": "🔧 Servis rahbari",
    "sotuvchi": "🛒 Sotuvchi",
    "sotuv_rahbar": "🛒 Sotuv rahbari",
}

# Checklist — Usta / Shogird
USTA_ERTALAB = [
    "Ishxonani ochdim",
    "Hamma yoqni supurdim va tozaladim",
    "Changlarni artdim",
    "Klyuchlar joy-joyida va soz ekanligini tekshirdim",
    "Axlatlarni olib chiqdim",
    "Mijoz kutib olishga tayyorman",
]

USTA_KECHQURUN = [
    "Barcha klyuchlar joy-joyida va sozligini tekshirdim",
    "Ishxona tartibga keltirildi",
    "Servis rahbariga hisobot berdim",
]

# Checklist — Servis rahbari
SERVIS_RAHBAR_VAZIFALAR = [
    "Usta/shogirdlardan hisobotlarni qabul qildim",
    "Ishlar qo'llanmaga muvofiqligini tekshirdim",
    "Yangi xodimlar bilan dars o'tdim (agar bor bo'lsa)",
    "Kechki yakuniy hisobotni tayyorladim",
]

# Checklist — Sotuvchi ertalab
SOTUVCHI_ERTALAB = [
    "Ishxonani ochdim, supurdim, oynalarni artdim",
    "Ish stolini tartibga keltirdim",
    "Ratsiyani tekshirib, aloqani sozladim",
    "Mahsulotlarni stellajga joylаshtirdim",
    "Kelgan tovarlarni tushirib, skladga joylаshtirdim",
    "Kompyuterni yoqdim, programmada smena ochdim",
    "Wi-Fi ishlayaptimi — tekshirdim",
    "Plastik (POS) apparat ishlayaptimi — tekshirdim",
]

SOTUVCHI_KUN = [
    "Mijozlarga savdo skriptiga amal qildim",
    "Kam qolgan tovarlarni daftarga yozdim",
    "Mijozlar bazaga kiritildi",
]

SOTUVCHI_KECHQURUN = [
    "Smena yopildi",
    "Kassa hisobi topshirildi",
    "Sotuv rahbariga hisobot berdim",
]

# Checklist — Sotuv rahbari
SOTUV_RAHBAR_VAZIFALAR = [
    "Kam qolgan tovarlarni filialga bildirdim",
    "Kunlik savdo ma'lumotlarini yig'dim",
    "Kassani yopdim va hisob-kitob qildim",
    "Sotuvchilar standartlarga amal qilganini tekshirdim",
]

# ─── STATE ────────────────────────────────────────────────────────────────────
class Royxat(StatesGroup):
    filial_tanlash = State()
    lavozim_tanlash = State()
    ism_kiritish = State()

class ChecklistState(StatesGroup):
    bajarilmoqda = State()

# ─── XODIMLAR MA'LUMOTLARI (xotirada) ────────────────────────────────────────
xodimlar = {}        # {user_id: {ism, filial, lavozim}}
smenalar = {}        # {user_id: {boshlangan, checklist, bajarilgan}}
hisobotlar = {}      # {sana: [{user_id, ism, filial, lavozim, ...}]}

# ─── BOT ──────────────────────────────────────────────────────────────────────
bot = Bot(token=TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

logging.basicConfig(level=logging.INFO)

# ─── YORDAMCHI FUNKSIYALAR ────────────────────────────────────────────────────
def lavozim_checklisti(lavozim: str, vaqt: str = "ertalab"):
    if lavozim == "usta" or lavozim == "shogird":
        return USTA_ERTALAB if vaqt == "ertalab" else USTA_KECHQURUN
    elif lavozim == "servis_rahbar":
        return SERVIS_RAHBAR_VAZIFALAR
    elif lavozim == "sotuvchi":
        if vaqt == "ertalab":
            return SOTUVCHI_ERTALAB
        elif vaqt == "kun":
            return SOTUVCHI_KUN
        else:
            return SOTUVCHI_KECHQURUN
    elif lavozim == "sotuv_rahbar":
        return SOTUV_RAHBAR_VAZIFALAR
    return []

def checklist_klaviatura(items, bajarilganlar):
    builder = InlineKeyboardBuilder()
    for i, item in enumerate(items):
        emoji = "✅" if i in bajarilganlar else "☐"
        builder.button(
            text=f"{emoji} {item}",
            callback_data=f"check_{i}"
        )
        builder.adjust(1)
    builder.button(text="📤 Hisobotni yuborish", callback_data="hisobot_yuborish")
    builder.adjust(1)
    return builder.as_markup()

def asosiy_menyu(lavozim):
    builder = ReplyKeyboardBuilder()
    builder.button(text="🌅 Smena ochish")
    builder.button(text="☀️ Kun davomi cheklisti")
    builder.button(text="🌙 Smena yopish")
    builder.button(text="📊 Mening hisobotim")
    builder.adjust(2)
    return builder.as_markup(resize_keyboard=True)

def admin_menyu():
    builder = ReplyKeyboardBuilder()
    builder.button(text="📊 Bugungi hisobot")
    builder.button(text="👥 Barcha xodimlar")
    builder.button(text="🏢 Filial holati")
    builder.button(text="⚠️ Bajarmaganlar")
    builder.adjust(2)
    return builder.as_markup(resize_keyboard=True)

# ─── /START ───────────────────────────────────────────────────────────────────
@dp.message(Command("start"))
async def start(message: types.Message, state: FSMContext):
    user_id = message.from_user.id

    if user_id == BOSH_RAHBAR_ID:
        await message.answer(
            "👋 Salom, Nodirjon aka!\n\n"
            "🏢 *OilCity Nazorat Tizimi*\n"
            "Barcha filiallar va xodimlarni shu yerdan kuzating.",
            parse_mode="Markdown",
            reply_markup=admin_menyu()
        )
        return

    if user_id in xodimlar:
        xodim = xodimlar[user_id]
        await message.answer(
            f"👋 Qaytib keldingiz, {xodim['ism']}!\n"
            f"🏢 {FILIALLAR[xodim['filial']]} | {LAVOZIMLAR[xodim['lavozim']]}",
            reply_markup=asosiy_menyu(xodim['lavozim'])
        )
        return

    # Yangi xodim — filial tanlash
    builder = InlineKeyboardBuilder()
    for key, nom in FILIALLAR.items():
        builder.button(text=f"🏢 {nom}", callback_data=f"filial_{key}")
    builder.adjust(1)

    await message.answer(
        "👋 Salom! *OilCity Hodimlar Botiga xush kelibsiz!*\n\n"
        "Ro'yxatdan o'tish uchun filialni tanlang:",
        parse_mode="Markdown",
        reply_markup=builder.as_markup()
    )
    await state.set_state(Royxat.filial_tanlash)

# ─── RO'YXATDAN O'TISH ────────────────────────────────────────────────────────
@dp.callback_query(Royxat.filial_tanlash, F.data.startswith("filial_"))
async def filial_tanlandi(call: types.CallbackQuery, state: FSMContext):
    filial = call.data.replace("filial_", "")
    await state.update_data(filial=filial)

    builder = InlineKeyboardBuilder()
    for key, nom in LAVOZIMLAR.items():
        builder.button(text=nom, callback_data=f"lavozim_{key}")
    builder.adjust(1)

    await call.message.edit_text(
        f"✅ *{FILIALLAR[filial]}* tanlandi!\n\nLavozimingizni tanlang:",
        parse_mode="Markdown",
        reply_markup=builder.as_markup()
    )
    await state.set_state(Royxat.lavozim_tanlash)

@dp.callback_query(Royxat.lavozim_tanlash, F.data.startswith("lavozim_"))
async def lavozim_tanlandi(call: types.CallbackQuery, state: FSMContext):
    lavozim = call.data.replace("lavozim_", "")
    await state.update_data(lavozim=lavozim)

    await call.message.edit_text(
        f"✅ *{LAVOZIMLAR[lavozim]}* tanlandi!\n\nIsmingizni kiriting:",
        parse_mode="Markdown"
    )
    await state.set_state(Royxat.ism_kiritish)

@dp.message(Royxat.ism_kiritish)
async def ism_kiritildi(message: types.Message, state: FSMContext):
    data = await state.get_data()
    user_id = message.from_user.id
    ism = message.text.strip()

    xodimlar[user_id] = {
        "ism": ism,
        "filial": data["filial"],
        "lavozim": data["lavozim"],
        "qoshilgan": datetime.now().strftime("%d.%m.%Y")
    }

    await state.clear()

    # Rahbarga xabar
    await bot.send_message(
        BOSH_RAHBAR_ID,
        f"👤 *Yangi xodim qo'shildi!*\n\n"
        f"Ism: {ism}\n"
        f"Filial: {FILIALLAR[data['filial']]}\n"
        f"Lavozim: {LAVOZIMLAR[data['lavozim']]}\n"
        f"Sana: {datetime.now().strftime('%d.%m.%Y %H:%M')}",
        parse_mode="Markdown"
    )

    await message.answer(
        f"🎉 Ro'yxatdan muvaffaqiyatli o'tdingiz!\n\n"
        f"👤 Ism: *{ism}*\n"
        f"🏢 Filial: *{FILIALLAR[data['filial']]}*\n"
        f"💼 Lavozim: *{LAVOZIMLAR[data['lavozim']]}*\n\n"
        f"Endi smena ochasiz! 👇",
        parse_mode="Markdown",
        reply_markup=asosiy_menyu(data["lavozim"])
    )

# ─── SMENA OCHISH ─────────────────────────────────────────────────────────────
@dp.message(F.text == "🌅 Smena ochish")
async def smena_ochish(message: types.Message, state: FSMContext):
    user_id = message.from_user.id

    if user_id not in xodimlar:
        await message.answer("⚠️ Avval /start orqali ro'yxatdan o'ting!")
        return

    xodim = xodimlar[user_id]
    lavozim = xodim["lavozim"]
    items = lavozim_checklisti(lavozim, "ertalab")

    smenalar[user_id] = {
        "boshlangan": datetime.now().strftime("%H:%M"),
        "sana": datetime.now().strftime("%d.%m.%Y"),
        "ertalab": set(),
        "kun": set(),
        "kechqurun": set(),
        "holat": "ochiq"
    }

    await state.update_data(vaqt="ertalab", items=items)
    await state.set_state(ChecklistState.bajarilmoqda)

    await message.answer(
        f"🌅 *Ertalabki smena boshlandi!*\n"
        f"⏰ Vaqt: {smenalar[user_id]['boshlangan']}\n\n"
        f"Quyidagi vazifalarni bajaring:",
        parse_mode="Markdown",
        reply_markup=checklist_klaviatura(items, set())
    )

    # Rahbarga xabar
    await bot.send_message(
        BOSH_RAHBAR_ID,
        f"🌅 *Smena ochildi*\n"
        f"👤 {xodim['ism']}\n"
        f"🏢 {FILIALLAR[xodim['filial']]}\n"
        f"💼 {LAVOZIMLAR[lavozim]}\n"
        f"⏰ {smenalar[user_id]['boshlangan']}",
        parse_mode="Markdown"
    )

# ─── CHEKLIST BELGILASH ───────────────────────────────────────────────────────
@dp.callback_query(ChecklistState.bajarilmoqda, F.data.startswith("check_"))
async def check_belgilash(call: types.CallbackQuery, state: FSMContext):
    user_id = call.from_user.id
    idx = int(call.data.replace("check_", ""))
    data = await state.get_data()
    items = data.get("items", [])
    vaqt = data.get("vaqt", "ertalab")

    if user_id not in smenalar:
        await call.answer("⚠️ Smena ochilmagan!")
        return

    bajarilganlar = smenalar[user_id].get(vaqt, set())
    if idx in bajarilganlar:
        bajarilganlar.discard(idx)
    else:
        bajarilganlar.add(idx)
    smenalar[user_id][vaqt] = bajarilganlar

    await call.message.edit_reply_markup(
        reply_markup=checklist_klaviatura(items, bajarilganlar)
    )
    await call.answer("✅ Belgilandi!" if idx in bajarilganlar else "☐ Bekor qilindi")

# ─── HISOBOT YUBORISH ─────────────────────────────────────────────────────────
@dp.callback_query(F.data == "hisobot_yuborish")
async def hisobot_yuborish(call: types.CallbackQuery, state: FSMContext):
    user_id = call.from_user.id

    if user_id not in xodimlar or user_id not in smenalar:
        await call.answer("⚠️ Ma'lumot topilmadi!")
        return

    xodim = xodimlar[user_id]
    smena = smenalar[user_id]
    data = await state.get_data()
    items = data.get("items", [])
    vaqt = data.get("vaqt", "ertalab")
    bajarilganlar = smena.get(vaqt, set())

    bajarildi = len(bajarilganlar)
    jami = len(items)
    foiz = int((bajarildi / jami) * 100) if jami > 0 else 0

    # Bajarilmagan vazifalar
    bajarilmaganlar = [items[i] for i in range(jami) if i not in bajarilganlar]

    hisobot = (
        f"📋 *Cheklist hisoboti*\n\n"
        f"👤 {xodim['ism']}\n"
        f"🏢 {FILIALLAR[xodim['filial']]}\n"
        f"💼 {LAVOZIMLAR[xodim['lavozim']]}\n"
        f"⏰ {datetime.now().strftime('%d.%m.%Y %H:%M')}\n"
        f"📌 Vaqt: {'Ertalab' if vaqt == 'ertalab' else 'Kun davomi' if vaqt == 'kun' else 'Kechqurun'}\n\n"
        f"✅ Bajarildi: {bajarildi}/{jami} ({foiz}%)\n"
    )

    if bajarilmaganlar:
        hisobot += f"\n⚠️ *Bajarilmagan vazifalar:*\n"
        for v in bajarilmaganlar:
            hisobot += f"  • {v}\n"
    else:
        hisobot += "\n🎉 Barcha vazifalar bajarildi!"

    # Rahbarga yuborish
    await bot.send_message(BOSH_RAHBAR_ID, hisobot, parse_mode="Markdown")

    # Filial rahbariga yuborish (hozircha rahbarga)
    await call.message.answer(
        f"✅ *Hisobot muvaffaqiyatli yuborildi!*\n\n"
        f"Bajarildi: {bajarildi}/{jami} ({foiz}%)",
        parse_mode="Markdown",
        reply_markup=asosiy_menyu(xodim["lavozim"])
    )
    await state.clear()

# ─── KUN DAVOMI ───────────────────────────────────────────────────────────────
@dp.message(F.text == "☀️ Kun davomi cheklisti")
async def kun_cheklisti(message: types.Message, state: FSMContext):
    user_id = message.from_user.id

    if user_id not in xodimlar:
        await message.answer("⚠️ Avval /start orqali ro'yxatdan o'ting!")
        return

    xodim = xodimlar[user_id]
    lavozim = xodim["lavozim"]
    items = lavozim_checklisti(lavozim, "kun")

    if not items:
        await message.answer("ℹ️ Bu lavozim uchun kun davomi cheklisti mavjud emas.")
        return

    await state.update_data(vaqt="kun", items=items)
    await state.set_state(ChecklistState.bajarilmoqda)

    await message.answer(
        "☀️ *Kun davomi vazifalari:*",
        parse_mode="Markdown",
        reply_markup=checklist_klaviatura(items, set())
    )

# ─── SMENA YOPISH ─────────────────────────────────────────────────────────────
@dp.message(F.text == "🌙 Smena yopish")
async def smena_yopish(message: types.Message, state: FSMContext):
    user_id = message.from_user.id

    if user_id not in xodimlar:
        await message.answer("⚠️ Avval /start orqali ro'yxatdan o'ting!")
        return

    xodim = xodimlar[user_id]
    lavozim = xodim["lavozim"]
    items = lavozim_checklisti(lavozim, "kechqurun")

    await state.update_data(vaqt="kechqurun", items=items)
    await state.set_state(ChecklistState.bajarilmoqda)

    await message.answer(
        "🌙 *Kechki smena yopilmoqda...*\n\nVazifalarni bajaring:",
        parse_mode="Markdown",
        reply_markup=checklist_klaviatura(items, set())
    )

# ─── MENING HISOBOTIM ─────────────────────────────────────────────────────────
@dp.message(F.text == "📊 Mening hisobotim")
async def mening_hisobotim(message: types.Message):
    user_id = message.from_user.id

    if user_id not in xodimlar:
        await message.answer("⚠️ Avval /start orqali ro'yxatdan o'ting!")
        return

    xodim = xodimlar[user_id]
    smena = smenalar.get(user_id, {})

    ertalab = len(smena.get("ertalab", set()))
    kun = len(smena.get("kun", set()))
    kechqurun = len(smena.get("kechqurun", set()))

    await message.answer(
        f"📊 *Bugungi hisobotim*\n\n"
        f"👤 {xodim['ism']}\n"
        f"🏢 {FILIALLAR[xodim['filial']]}\n"
        f"💼 {LAVOZIMLAR[xodim['lavozim']]}\n\n"
        f"🌅 Ertalab: {ertalab} vazifa bajarildi\n"
        f"☀️ Kun davomi: {kun} vazifa bajarildi\n"
        f"🌙 Kechqurun: {kechqurun} vazifa bajarildi\n\n"
        f"📅 Sana: {datetime.now().strftime('%d.%m.%Y')}",
        parse_mode="Markdown"
    )

# ─── ADMIN — BUGUNGI HISOBOT ──────────────────────────────────────────────────
@dp.message(F.text == "📊 Bugungi hisobot")
async def bugungi_hisobot(message: types.Message):
    if message.from_user.id != BOSH_RAHBAR_ID:
        return

    if not xodimlar:
        await message.answer("ℹ️ Hozircha xodimlar ro'yxatdan o'tmagan.")
        return

    matn = f"📊 *Bugungi hisobot — {datetime.now().strftime('%d.%m.%Y')}*\n\n"

    for filial_key, filial_nom in FILIALLAR.items():
        matn += f"🏢 *{filial_nom}*\n"
        filial_xodimlari = [
            (uid, x) for uid, x in xodimlar.items()
            if x["filial"] == filial_key
        ]
        if not filial_xodimlari:
            matn += "  — Xodim yo'q\n"
        for uid, x in filial_xodimlari:
            smena = smenalar.get(uid, {})
            holat = "✅ Aktiv" if smena.get("holat") == "ochiq" else "⭕ Smena ochilmagan"
            matn += f"  👤 {x['ism']} ({LAVOZIMLAR[x['lavozim']].split()[-1]}) — {holat}\n"
        matn += "\n"

    await message.answer(matn, parse_mode="Markdown")

# ─── ADMIN — BARCHA XODIMLAR ─────────────────────────────────────────────────
@dp.message(F.text == "👥 Barcha xodimlar")
async def barcha_xodimlar(message: types.Message):
    if message.from_user.id != BOSH_RAHBAR_ID:
        return

    if not xodimlar:
        await message.answer("ℹ️ Hozircha xodimlar ro'yxatdan o'tmagan.")
        return

    matn = f"👥 *Barcha xodimlar ({len(xodimlar)} ta)*\n\n"
    for uid, x in xodimlar.items():
        matn += (
            f"👤 {x['ism']}\n"
            f"   🏢 {FILIALLAR[x['filial']]} | 💼 {LAVOZIMLAR[x['lavozim']]}\n"
            f"   📅 Qo'shilgan: {x['qoshilgan']}\n\n"
        )

    await message.answer(matn, parse_mode="Markdown")

# ─── ADMIN — FILIAL HOLATI ────────────────────────────────────────────────────
@dp.message(F.text == "🏢 Filial holati")
async def filial_holati(message: types.Message):
    if message.from_user.id != BOSH_RAHBAR_ID:
        return

    matn = f"🏢 *Filiallar holati*\n\n"
    for filial_key, filial_nom in FILIALLAR.items():
        xodimlar_soni = sum(1 for x in xodimlar.values() if x["filial"] == filial_key)
        aktiv = sum(
            1 for uid, x in xodimlar.items()
            if x["filial"] == filial_key and smenalar.get(uid, {}).get("holat") == "ochiq"
        )
        matn += f"🏢 *{filial_nom}*\n"
        matn += f"   👥 Jami xodim: {xodimlar_soni}\n"
        matn += f"   ✅ Aktiv smena: {aktiv}\n\n"

    await message.answer(matn, parse_mode="Markdown")

# ─── ADMIN — BAJARMAGANLAR ────────────────────────────────────────────────────
@dp.message(F.text == "⚠️ Bajarmaganlar")
async def bajarmaganlar(message: types.Message):
    if message.from_user.id != BOSH_RAHBAR_ID:
        return

    matn = f"⚠️ *Smena ochmaganlar — {datetime.now().strftime('%d.%m.%Y')}*\n\n"
    topildi = False

    for uid, x in xodimlar.items():
        if uid not in smenalar or smenalar[uid].get("holat") != "ochiq":
            matn += f"❌ {x['ism']} — {FILIALLAR[x['filial']]} ({LAVOZIMLAR[x['lavozim']]})\n"
            topildi = True

    if not topildi:
        matn += "✅ Hamma smena ochgan!"

    await message.answer(matn, parse_mode="Markdown")

# ─── ISHGA TUSHIRISH ──────────────────────────────────────────────────────────
async def main():
    print("✅ OilCity Hodimlar Boti ishga tushdi!")
    await bot.send_message(
        BOSH_RAHBAR_ID,
        "🚀 *OilCity Hodimlar Boti ishga tushdi!*\n\n"
        "Barcha xodimlar botga /start orqali kirishlari mumkin.",
        parse_mode="Markdown"
    )
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
