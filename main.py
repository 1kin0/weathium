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

_browser = None
_playwright = None
_lock = asyncio.Lock()

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="/", intents=intents)

async def send_unified_log(log_type: str, color: discord.Color, content: str, interaction: discord.Interaction = None):
    guild = bot.get_guild(LOG_GUILD_ID)
    if not guild: return
    channel = guild.get_channel(LOG_CHANNEL_ID)
    if not channel: return

    timestamp = int(time.time())
    header = f"**TYPE : {log_type.upper()}**\n**TIME : <t:{timestamp}:F>**\n"

    if interaction:
        location = f"**LOCATION :** `{interaction.guild.name if interaction.guild else 'DM'}`\n**USER :** `{interaction.user}`"
    else:
        location = "**LOCATION :** `Internal System`"

    embed = discord.Embed(title=header, description=f"{location}\n\n ```{content[:1000]}``` ", color=color)
    await channel.send(embed=embed)

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
    # Используем API OpenWeatherMap
    url = f"http://api.openweathermap.org/data/2.5/weather?q={city}&appid={WEATHER_API_KEY}&units=metric&lang=ru"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            if resp.status == 200:
                return await resp.json()
            else:
                err_msg = f"API Error {resp.status} for city: {city}"
                await send_unified_log("api_warning", discord.Color.orange(), err_msg)
                return None

@bot.event
async def on_ready():
    await bot.tree.sync()
    await send_unified_log("startup", discord.Color.green(), "Bot online and ready")
    asyncio.create_task(get_browser())

@bot.tree.command(name="weather", description="Узнать погоду")
@app_commands.describe(city="Введите название города")
async def weather(interaction: discord.Interaction, city: str):
    await interaction.response.defer()
    
    data = await fetch_weather(city)
    if not data:
        await interaction.followup.send(f"Город `{city}` не найден. Проверьте правильность написания или ключ API.")
        return

    try:
        # Читаем шаблон из вашего widget.html
        with open("widget.html", "r", encoding="utf-8") as f:
            html_content = f.read()

        # Заменяем данные в HTML на реальные из API
        replacements = {
            "Москва": data['name'],
            "Ясно": data['weather'][0]['description'].capitalize(),
            "-12°": f"{round(data['main']['temp'])}°",
            "84%": f"{data['main']['humidity']}%",
            "-18°": f"{round(data['main']['feels_like'])}°",
            "754": str(round(data['main']['pressure'] * 0.750062)), # Перевод hPa в мм рт. ст.
            "0": str(data.get('clouds', {}).get('all', 0))
        }

        for placeholder, value in replacements.items():
            html_content = html_content.replace(placeholder, value)

        browser = await get_browser()
        context = await browser.new_context(viewport={"width": 1300, "height": 1000})
        page = await context.new_page()
        
        try:
            # Рендерим измененный HTML
            await page.set_content(html_content, wait_until="domcontentloaded")
            await asyncio.sleep(0.5) 
            buffer = await page.screenshot(type="png", omit_background=True)
            
            file = discord.File(io.BytesIO(buffer), "weather.png")
            await interaction.followup.send(file=file)
        finally:
            await page.close()
            await context.close()

    except Exception:
        tb = traceback.format_exc()
        await send_unified_log("render_error", discord.Color.red(), tb, interaction)
        await interaction.followup.send("Ошибка рендеринга виджета.")

bot.run(TOKEN)