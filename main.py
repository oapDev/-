import discord
from discord.ext import commands
from discord.ui import Button, View
import requests
import asyncio
import json
import os
import base64
import time
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service

# ================= CONFIGURATION =================
TOKEN = 'MTQ1NjYyMzAzODIyNDE0MjQxOA.GJcReh.PY4MH6yH0FkevFOhdm8To1AYUYi-c9zzbryEKk'
USERNAME = "pcu06112"
PASSWORD = "newKub!122" 
ALLOWED_CHANNEL_ID = 1456639584879247520
COOKIE_FILE = "system.config"
FB_ADMIN_URL = "https://www.facebook.com/share/14QurBkLrid/"
API_URL = "https://authenservice.nhso.go.th/authencode/api/nch-personal-fund/search-by-pid"
URL_LOGIN = "https://authenservice.nhso.go.th/authencode/claimcode/search/history"

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

# ================= CORE FUNCTIONS =================

def sync_get_new_cookies():
    """ระบบ Login อัตโนมัติที่ดึงความเสถียรมาจาก av1.py"""
    chrome_options = Options()
    chrome_options.add_argument("--headless=new") 
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation", "enable-logging"])
    # ใช้ User-Agent ที่เลียนแบบเบราว์เซอร์จริงตาม av1.py
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36")
    
    service = Service()
    if os.name == 'nt': 
        service.creation_flags = 0x08000000 
    
    driver = None
    try:
        driver = webdriver.Chrome(options=chrome_options, service=service)
        driver.get(URL_LOGIN)
        wait = WebDriverWait(driver, 30)
        
        # ค้นหาช่องกรอก Username และ Password ตามโครงสร้างเว็บ สปสช.
        user_field = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "input[name='username'], input#username")))
        user_field.send_keys(USERNAME)
        pass_field = driver.find_element(By.CSS_SELECTOR, "input[name='password'], input#password")
        pass_field.send_keys(PASSWORD + Keys.ENTER)
        
        # รอให้ระบบสร้าง Session (ใช้ time.sleep เพราะทำงานใน Thread แยก)
        time.sleep(12) 
        
        cookies = driver.get_cookies()
        if cookies:
            data = base64.b64encode(json.dumps(cookies).encode()).decode()[::-1]
            with open(COOKIE_FILE, "w", encoding="utf-8") as f: 
                f.write(data)
            print("✅ [System] Renewed Session with NHSO successfully.")
            return True
        return False
    except Exception as e:
        print(f"❌ [Login Error] {e}")
        return False
    finally:
        if driver: 
            driver.quit()

async def get_session():
    """จัดการ Session แบบ Async เพื่อไม่ให้บอทค้าง"""
    if not os.path.exists(COOKIE_FILE):
        await asyncio.to_thread(sync_get_new_cookies)

    session = requests.Session()
    try:
        with open(COOKIE_FILE, "r", encoding="utf-8") as f:
            raw = base64.b64decode(f.read()[::-1]).decode()
            cookies = json.loads(raw)
            for c in cookies: 
                session.cookies.set(c["name"], c["value"])
        
        session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Referer": "https://authenservice.nhso.go.th/"
        })
        return session
    except:
        if os.path.exists(COOKIE_FILE): os.remove(COOKIE_FILE)
        await asyncio.to_thread(sync_get_new_cookies)
        return await get_session()

# ================= UI COMPONENTS =================

class AdminView(View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(Button(label="ติดต่อ ADMIN", url=FB_ADMIN_URL, style=discord.ButtonStyle.link, emoji="👤"))

# ================= BOT COMMANDS =================

@bot.event
async def on_ready():
    print(f'🚀 บอทออนไลน์: {bot.user.name} | ระบบดึงข้อมูลพร้อมใช้งาน')

@bot.command()
async def pid(ctx, pid: str):
    if ctx.channel.id != ALLOWED_CHANNEL_ID: return

    if len(pid) != 13 or not pid.isdigit():
        return await ctx.send("❌ **กรุณาระบุเลขบัตรประชาชน 13 หลักให้ถูกต้อง**")

    loading_embed = discord.Embed(
        description="⏳ **กำลังดึงข้อมูลความสัมพันธ์ครอบครัวจาก สปสช...**", 
        color=0x3498db
    )
    status_msg = await ctx.send(embed=loading_embed)
    
    try:
        session = await get_session()
        
        # ฟังก์ชันดึงข้อมูล API แบบ Thread-safe
        def fetch():
            return session.get(API_URL, params={"pid": pid}, timeout=15)

        r = await asyncio.to_thread(fetch)
        
        # กรณี Session หมดอายุ (401/403)
        if r.status_code in [401, 403]:
            if os.path.exists(COOKIE_FILE): os.remove(COOKIE_FILE)
            session = await get_session()
            r = await asyncio.to_thread(fetch)

        if r.status_code == 200:
            res = r.json()
            p = res.get('personData', {})
            if not p: 
                return await status_msg.edit(content="❌ **ไม่พบข้อมูลเลขบัตรนี้ในฐานข้อมูล**", embed=None)

            embed = discord.Embed(title="✨ ผลการตรวจสอบข้อมูล สปสช. ขั้นสูง ✨", color=0x2ecc71)
            
            # I. ข้อมูลส่วนตัว
            embed.add_field(name="👤 I. ข้อมูลบุคคล", value=f"```css\n"
                f"ชื่อ-นามสกุล: {p.get('fullName', '-')}\n"
                f"เลขบัตรประชาชน: {p.get('pid', pid)}\n"
                f"วันเกิด: {p.get('displayBirthDate', '-')} ({p.get('age', {}).get('years', '-')} ปี)\n"
                f"เพศ: {p.get('sexDesc', '-')}\n```", inline=False)

            # II. ข้อมูลครอบครัว (ดึงจาก personData ตามไฟล์ต้นฉบับ)
            embed.add_field(name="👥 II. ข้อมูลความสัมพันธ์ (ครอบครัว)", value=f"```css\n"
                f"เลขบัตรประชาชนมารดา: {p.get('motherId', 'ไม่พบข้อมูล')}\n"
                f"เลขบัตรประชาชนบิดา: {p.get('fatherId', 'ไม่พบข้อมูล')}\n"
                f"เลขบัตรเจ้าของสิทธิ: {res.get('ownerPid', '-')}\n```", inline=False)

            # III. ข้อมูลสิทธิ
            embed.add_field(name="🏥 III. สิทธิการรักษา", value=f"```css\n"
                f"สิทธิหลัก: {res.get('mainInscl', {}).get('rightName', '-')}\n"
                f"สถานพยาบาลหลัก: {res.get('hospMain', {}).get('hname', '-')}\n```", inline=False)

            # IV. ข้อมูลที่อยู่
            addr = p.get('addressCatm', {})
            embed.add_field(name="🏘️ IV. รายละเอียดที่อยู่", value=f"```css\n"
                f"บ้านเลขที่: {p.get('homeAddress', {}).get('adressNo', '-')} หมู่ {addr.get('moo', '-')}\n"
                f"ตำบล: {addr.get('tumbonName', '-')} อำเภอ: {addr.get('amphurName', '-')} จังหวัด: {addr.get('changwatName', '-')}\n```", inline=False)

            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            embed.set_footer(text=f"ค้นหาโดย: {ctx.author.name} | {now}")

            await status_msg.delete()
            await ctx.send(embed=embed, view=AdminView())
        else:
            await status_msg.edit(content=f"❌ **Error:** เซิร์ฟเวอร์ตอบสนองผิดพลาด `{r.status_code}`", embed=None)

    except Exception as e:
        await status_msg.edit(content=f"❌ **System Error:** `{str(e)}`", embed=None)


bot.run(TOKEN)

