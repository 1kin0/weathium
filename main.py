import os
import io
import time
import discord
import traceback
import asyncio
import aiohttp
from discord import app_commands
from discord.ext import commands
from playwright.async_api import async_playwright
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")
WEATHER_API_KEY = os.getenv("WEATHER_API_KEY") 
LOG_GUILD_ID = 1473082652452978991
LOG_CHANNEL_ID = 1473409327514648597
WIDGET_PATH = "/app/web/widget.html"

_browser = None
_playwright = None
_lock = asyncio.Lock()

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="/", intents=intents)

async def send_unified_log(log_type: str, color: discord.Color, content: str, interaction: discord.Interaction = None):
    try:
        guild = bot.get_guild(LOG_GUILD_ID)
        if not guild: return
        channel = guild.get_channel(LOG_CHANNEL_ID)
        if not channel: return

        timestamp = int(time.time())
        header = f"**TYPE : {log_type.upper()}**\n**TIME : <t:{timestamp}:F>**\n"

        mention = "<@&1474514062909112566> " if "error" in log_type.lower() else ""

        if interaction:
            location = f"**LOCATION :** `{interaction.guild.name if interaction.guild else 'DM'}`\n**USER :** `{interaction.user}`"
        else:
            location = "**LOCATION :** `Internal System`"

        embed = discord.Embed(title=header, description=f"{location}\n\n ```{content[:1000]}``` ", color=color)
        
        await channel.send(content=mention, embed=embed)
    except:
        pass

async def get_browser():
    global _browser, _playwright
    async with _lock:
        if _browser and not _browser.is_connected():
            _browser = None
        if _browser is None:
            if _playwright is None:
                _playwright = await async_playwright().start()
            _browser = await _playwright.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"]
            )
    return _browser

async def fetch_weather(city: str):
    url = f"http://api.openweathermap.org/data/2.5/weather?q={city}&appid={WEATHER_API_KEY}&units=metric&lang=ru"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            if resp.status == 200:
                return await resp.json()
            return None

@bot.event
async def on_ready():
    await bot.tree.sync()
    await send_unified_log("startup", discord.Color.green(), "Bot online")
    asyncio.create_task(get_browser())

@bot.tree.command(name="render", description="Render widget test")
async def slash_render(interaction: discord.Interaction):
    await interaction.response.defer()
    try:
        # Исправление ошибки ERR_FILE: читаем файл через Python
        with open(WIDGET_PATH, "r", encoding="utf-8") as f:
            html = f.read()
            
        browser = await get_browser()
        context = await browser.new_context(viewport={"width": 1300, "height": 1000})
        page = await context.new_page()
        try:
            # Используем set_content вместо goto(file://)
            await page.set_content(html, wait_until="domcontentloaded")
            await asyncio.sleep(0.3)
            buffer = await page.screenshot(type="png", omit_background=True)
            await interaction.followup.send(file=discord.File(io.BytesIO(buffer), "render.png"))
        finally:
            await page.close()
            await context.close()
    except Exception:
        await send_unified_log("render_error", discord.Color.red(), traceback.format_exc(), interaction)
        await interaction.followup.send("Ошибка рендеринга.")

@bot.tree.command(name="weather", description="Check the weather in the city")
@app_commands.describe(city="Enter the name of the city")
async def weather(interaction: discord.Interaction, city: str):
    await interaction.response.defer()
    data = await fetch_weather(city)
    if not data:
        await interaction.followup.send(f"Город `{city}` не найден.")
        return

    try:
        with open(WIDGET_PATH, "r", encoding="utf-8") as f:
            html = f.read()

        # --- Логика стилизации в зависимости от погоды ---
        condition_main = data['weather'][0]['main']
        
        # Mapping: (Эмодзи, HEX-цвет, RGB-цвет для градиента)
        # В HTML Blurple это #5865F2 и rgba(88, 101, 242, ...)
        weather_styles = {
            "Clear": ("☀️", "#00A8FC", "0, 168, 252"),       # Свежий голубой
            "Clouds": ("☁️", "#72767D", "114, 118, 125"),    # Серый (Discord)
            "Rain": ("🌧️", "#5865F2", "88, 101, 242"),        # Blurple
            "Drizzle": ("🌦️", "#5865F2", "88, 101, 242"),
            "Thunderstorm": ("⛈️", "#FEE75C", "254, 231, 92"), # Желтый
            "Snow": ("❄️", "#FFFFFF", "255, 255, 255"),       # Белый
            "Mist": ("🌫️", "#B9BBBE", "185, 187, 190"),       # Туман
            "Fog": ("🌫️", "#B9BBBE", "185, 187, 190"),
        }
        
        icon, accent_hex, accent_rgb = weather_styles.get(condition_main, ("☀️", "#5865F2", "88, 101, 242"))

        # Подготовка данных
        temp = round(data['main']['temp'])
        feels_like = round(data['main']['feels_like'])
        description = data['weather'][0]['description'].capitalize()
        pressure_mm = round(data['main']['pressure'] * 0.750062)

        replacements = {
            "Москва": data['name'],
            "Ясно": description,
            "-12°": f"{temp}°",
            "-18°": f"{feels_like}°",
            "84%": f"{data['main']['humidity']}%",
            "4.2": str(data['wind']['speed']),
            "754": str(pressure_mm),
            "☀️": icon, # Замена иконки
            "#5865F2": accent_hex, # Замена цвета иконок и границ
            "88, 101, 242": accent_rgb # Замена цвета градиента фона
        }

        for placeholder, value in replacements.items():
            html = html.replace(placeholder, value)

        browser = await get_browser()
        context = await browser.new_context(viewport={"width": 1300, "height": 1000})
        page = await context.new_page()
        try:
            await page.set_content(html, wait_until="domcontentloaded")
            await asyncio.sleep(0.4)
            buffer = await page.screenshot(type="png", omit_background=True)
            await interaction.followup.send(file=discord.File(io.BytesIO(buffer), "widget.png"))
        finally:
            await page.close()
            await context.close()
    except Exception:
        await send_unified_log("weather_error", discord.Color.red(), traceback.format_exc(), interaction)
        await interaction.followup.send("Weather generation error.")

bot.run(TOKEN)