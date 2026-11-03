# Sonnet bot

## Serverda ishga tushirish
```bash
git clone <repo-url> bot && cd bot
python3 -m venv venv && venv/bin/pip install -r requirements.txt
export BOT_TOKEN="123456:ABC..."     # @BotFather
export ADMIN_ID="123456789"          # sizning Telegram ID
export LOG_CHAT_ID="-1001234567890"  # log kanal (ixtiyoriy)
nohup venv/bin/python sonnet_final.py >> bot.log 2>&1 &
```
Token va parollarni **hech qachon** GitHub'ga yozmang — faqat muhit o'zgaruvchisida saqlang.

## Shablonlar
`templates/` va `templates_tgs/` JSON fayllari bitta siqilgan arxivda: `templates_pack.zip`.
Yangi shablon qo'shsangiz, papkaga `.json` tashlab: `python assets.py pack`.
