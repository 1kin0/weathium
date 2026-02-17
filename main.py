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
WEATHER_API_KEY = os.getenv("WEATHER_API_KEY") # Нужно добавить в .env
LOG_GUILD_ID = 1473082652452978991
LOG_CHANNEL_ID = 1473409327514648597

# Глобальные переменные для переиспользования браузера
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
    header = f"**TYPE : {log_type.upper()}**\n"
    header += f"**TIME : <t:{timestamp}:F>**\n"

    if interaction:
        location = f"**LOCATION :** `{interaction.guild.name if interaction.guild else 'DM'}` (`{interaction.guild_id}`)\n"
        location += f"**USER :** `{interaction.user}` (`{interaction.user.id}`)"
    else:
        location = "**LOCATION :** `Internal System`"

    embed = discord.Embed(
        title=header,
        description=f"{location}\n\n ```{content[:1000]}``` ",
        color=color
    )
    await channel.send(embed=embed)

async def get_browser():
    global _browser, _playwright
    async with _lock:
        if _browser and not _browser.is_connected():
            _browser = None
        if _browser is None:
            try:
                if _playwright is None:
                    _playwright = await async_playwright().start()
                _browser = await _playwright.chromium.launch(
                    headless=True,
                    args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage", "--disable-gpu"]
                )
                await send_unified_log("launch", discord.Color.blue(), "Chromium engine initialized")
            except Exception:
                await send_unified_log("critical_error", discord.Color.red(), f"```py\n{traceback.format_exc()}```")
                raise
    return _browser

async def fetch_weather(city: str):
    """Получение данных из OpenWeatherMap"""
    url = f"http://api.openweathermap.org/data/2.5/weather?q={city}&appid={WEATHER_API_KEY}&units=metric&lang=ru"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            if resp.status == 200:
                return await resp.json()
            return None

@bot.event
async def on_ready():
    await bot.tree.sync()
    await send_unified_log("startup", discord.Color.green(), f"Bot online. Latency: {round(bot.latency * 1000)}ms")
    asyncio.create_task(get_browser())

@bot.tree.command(name="weather", description="Показать погоду в городе")
@app_commands.describe(city="Название города")
async def weather(interaction: discord.Interaction, city: str):
    await interaction.response.defer()
    
    # 1. Запрос данных
    data = await fetch_weather(city)
    if not data:
        await interaction.followup.send(f"Город `{city}` не найден или сервис недоступен.")
        return

    # 2. Подготовка данных для HTML
    try:
        with open("widget.html", "r", encoding="utf-8") as f:
            html_template = f.read()

        # Маппинг данных в шаблон
        replacements = {
            "Москва": data['name'].capitalize(),
            "Ясно": data['weather'][0]['description'].capitalize(),
            "-12°": f"{round(data['main']['temp'])}°",
            "84%": f"{data['main']['humidity']}%",
            "-18°": f"{round(data['main']['feels_like'])}°",
            "754": str(data['main']['pressure']),
            "0": str(data.get('clouds', {}).get('all', 0)) # Используем облачность вместо УФ, если API базовый
        }

        for placeholder, value in replacements.items():
            html_template = html_template.replace(placeholder, value)

        # 3. Рендеринг
        browser = await get_browser()
        context = await browser.new_context(viewport={"width": 1300, "height": 1000})
        page = await context.new_page()
        
        try:
            # Устанавливаем модифицированный HTML напрямую
            await page.set_content(html_template, wait_until="domcontentloaded")
            await asyncio.sleep(0.3) 
            buffer = await page.screenshot(type="png", omit_background=True)
            
            file = discord.File(io.BytesIO(buffer), "weather.png")
            await interaction.followup.send(file=file)
        finally:
            await page.close()
            await context.close()

    except Exception:
        tb = traceback.format_exc()
        await send_unified_log("weather_error", discord.Color.red(), f"```py\n{tb}```", interaction)
        await interaction.followup.send("Произошла ошибка при генерации виджета.")

@bot.tree.command(name="ping", description="Check latency")
async def slash_ping(interaction: discord.Interaction):
    await interaction.response.send_message(f"`{round(bot.latency * 1000)}ms`", ephemeral=True)

bot.run(TOKEN)