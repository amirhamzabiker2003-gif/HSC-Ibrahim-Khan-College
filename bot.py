import requests
import asyncio
from bs4 import BeautifulSoup
from flask import Flask
from threading import Thread
import os

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
    CallbackQueryHandler
)

# ----------- 1. KEEP ALIVE SERVER -----------
app = Flask('')

@app.route('/')
def home():
    return "HSC Bot is Online!"

def run():
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))

def keep_alive():
    t = Thread(target=run)
    t.start()

# ----------- 2. CONFIGURATION -----------
BOT_TOKEN = "8687725670:AAGL7ul92ppIqLgnx5vei9s1FtbFKOI8Fg0" # আপনার টোকেন অটোমেটিক বসিয়ে দেওয়া হয়েছে

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
}

# ----------- 3. SMART DATA SCRAPER (Separate Fields) -----------
def get_data(tid):
    url = f"https://billpay.sonalibank.com.bd/HSCFee/Home/Voucher/{tid}"
    try:
        r = requests.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(r.text, "html.parser")
        
        data = {
            "Transaction ID": tid, "College": "", "Group": "", 
            "SSC Roll": "N/A", "Class Roll": "N/A", "Reg. No": "N/A",
            "Name": "", "Mobile": "", "Year": "",
            "Session": "", "Amount(BDT)": "", "Date": "Not Found"
        }
        
        rows = soup.find_all("tr")
        for row in rows:
            cols = row.find_all("td")
            if len(cols) >= 2:
                key = cols[0].text.strip().replace(":", "")
                val = cols[1].text.strip()
                
                if "College" in key: data["College"] = val
                elif "Group" in key: data["Group"] = val
                elif "SSC Roll" in key: data["SSC Roll"] = val
                elif "Class Roll" in key: data["Class Roll"] = val
                elif "Reg. No" in key: data["Reg. No"] = val
                elif "Name" in key: data["Name"] = val
                elif "Mobile" in key: data["Mobile"] = val
                elif "Year" in key: data["Year"] = val
                elif "Session" in key: data["Session"] = val
                elif "Amount" in key: data["Amount(BDT)"] = val
                elif "Date" in key: data["Date"] = val

        if data["Date"] == "Not Found":
            date_tag = soup.find(string=lambda x: x and "Date" in x)
            if date_tag:
                data["Date"] = date_tag.parent.get_text().replace("Date", "").replace(":", "").strip()

        return data
    except:
        return None

# ----------- 4. RESULT SENDER FORMAT -----------
async def process_roll(update_or_query, data_list):
    final_text = ""
    unique_phones = []
    
    for i, data in enumerate(data_list, 1):
        phone = data["Mobile"]
        wa_phone = "880" + phone[1:] if phone.startswith("0") else phone
        
        # এখানে তিনটি রোল/রেজিস্ট্রেশন আলাদা লাইনে দেখানো হয়েছে
        final_text += (
            f"📄 Result {i}\n"
            f"<pre>\n"
            f"Transaction ID: {data['Transaction ID']}\n"
            f"College       : {data['College']}\n"
            f"Group         : {data['Group']}\n"
            f"SSC Roll      : {data['SSC Roll']}\n"
            f"Class Roll    : {data['Class Roll']}\n"
            f"Reg. No       : {data['Reg. No']}\n"
            f"Name          : {data['Name']}\n"
            f"Mobile        : {data['Mobile']}\n"
            f"Year          : {data['Year']}\n"
            f"Session       : {data['Session']}\n"
            f"Amount(BDT)   : {data['Amount(BDT)']}\n"
            f"Date          : {data['Date']}\n"
            f"</pre>\n\n"
        )
        
        if wa_phone not in unique_phones:
            unique_phones.append(wa_phone)

    keyboard = []
    for ph in unique_phones:
        keyboard.append([
            InlineKeyboardButton("📱 WhatsApp", url=f"https://wa.me/{ph}"),
            InlineKeyboardButton("📢 Telegram", url=f"https://t.me/{ph}")
        ])
    
    msg_source = update_or_query.message if hasattr(update_or_query, 'message') else update_or_query
    await msg_source.reply_text(final_text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard))

# ----------- 5. CORE SEARCH ENGINE -----------
async def run_search(update_or_query, context, start_r, end_r):
    rolls = list(range(start_r, end_r + 1))
    context.user_data["current_end"] = end_r
    
    msg_source = update_or_query.message if hasattr(update_or_query, 'message') else update_or_query
    status_msg = await msg_source.reply_text("⏳ Processing...")
    
    total_found = 0
    for i, roll in enumerate(rolls, 1):
        try:
            url = f"https://billpay.sonalibank.com.bd/HSCFee/Home/Search?searchStr={roll}"
            r = requests.get(url, headers=headers, timeout=10)
            
            if "Details" in r.text:
                soup = BeautifulSoup(r.text, "html.parser")
                links = soup.select("a[href*='Voucher']")
                data_list = []
                for link in links:
                    tid = link['href'].split("/")[-1]
                    d = get_data(tid)
                    if d and d["Name"]: data_list.append(d)
                
                if data_list:
                    total_found += 1
                    await process_roll(update_or_query, data_list)

            await status_msg.edit_text(
                f"⏳ Processing...\n"
                f"🔢 Roll: {roll}\n"
                f"📊 Found: {total_found}\n"
                f"✅ Progress: {i}/{len(rolls)}"
            )
        except: continue

    next_kb = [[InlineKeyboardButton("👉 Next 500?", callback_data="next_500")]]
    await msg_source.reply_text(
        f"✅ Done!\n📊 Total: {total_found}",
        reply_markup=InlineKeyboardMarkup(next_kb)
    )

# ----------- 6. HANDLERS -----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = [[InlineKeyboardButton("Start", callback_data="btn_ready")]]
    await update.message.reply_text("HSC ফি চেক বট শুরু করতে 'Start' বাটনে ক্লিক করুন:", reply_markup=InlineKeyboardMarkup(kb))

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    try:
        if "-" in text:
            s, e = map(int, text.split("-"))
            await run_search(update, context, s, e)
        else:
            r = int(text)
            await run_search(update, context, r, r)
    except: pass

async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "btn_ready":
        await query.message.reply_text("🚀 Ready!")
    elif query.data == "next_500":
        last_end = context.user_data.get("current_end", 0)
        if last_end > 0:
            await run_search(query, context, last_end + 1, last_end + 500)

# ----------- 7. RUN BOT -----------
if __name__ == "__main__":
    keep_alive()
    application = ApplicationBuilder().token(BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(callback_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    application.run_polling()
