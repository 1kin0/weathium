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

# Глобальные переменные для переиспользования браузера
_browser = None
_playwright = None
_lock = asyncio.Lock() # Для безопасной инициализации

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
    
    async with _lock: # Защита от одновременного запуска нескольких браузеров 
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
                await send_unified_log("launch", discord.Color.blue(), "Chromium engine initialized and ready")
            except Exception:
                await send_unified_log("critical_error", discord.Color.red(), f"```py\n{traceback.format_exc()}```")
                raise
    return _browser

async def fetch_weather(city: str):
    """Вспомогательная функция для получения данных погоды"""
    url = f"http://api.openweathermap.org/data/2.5/weather?q={city}&appid={WEATHER_API_KEY}&units=metric&lang=ru"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            if resp.status == 200:
                return await resp.json()
            else:
                err_text = f"Weather API error: {resp.status} for city {city}"
                await send_unified_log("api_error", discord.Color.orange(), err_text)
                return None

@bot.event
async def on_ready():
    # 1. Синхронизируем команды 
    await bot.tree.sync()
    
    # 2. Логируем старт 
    status_msg = f"Bot is online. Latency: {round(bot.latency * 1000)}ms"
    await send_unified_log("startup", discord.Color.green(), status_msg)
    
    # 3. ПРЕДВАРИТЕЛЬНЫЙ ЗАПУСК БРАУЗЕРА 
    asyncio.create_task(get_browser())

# --- ОРИГИНАЛЬНЫЕ КОМАНДЫ ---

@bot.tree.command(name="ping", description="Check latency")
async def slash_ping(interaction: discord.Interaction):
    await interaction.response.send_message(f"`{round(bot.latency * 1000)}ms`", ephemeral=True) [cite: 2]

@bot.tree.command(name="render", description="Render widget.html")
async def slash_render(interaction: discord.Interaction):
    await interaction.response.defer()
    
    path = os.path.abspath("widget.html")
    if not os.path.exists(path):
        err_text = f"File not found: `{path}`"
        await send_unified_log("render_error", discord.Color.red(), err_text, interaction)
        await interaction.followup.send("`System error: missing source file`.")
        return

    try:
        browser = await get_browser()
        context = await browser.new_context(viewport={"width": 1300, "height": 1000})
        page = await context.new_page()
        
        try:
            await page.goto(f'file://{path}', wait_until="domcontentloaded", timeout=15000)
            await asyncio.sleep(0.2) 
            buffer = await page.screenshot(type="png", omit_background=True)
            
            file = discord.File(io.BytesIO(buffer), "render.png")
            await interaction.followup.send(file=file)
            
        finally:
            await page.close()
            await context.close()
            
    except Exception:
        tb = traceback.format_exc()
        await send_unified_log("render_error", discord.Color.red(), f"```py\n{tb}```", interaction)
        await interaction.followup.send("`Rendering error`. Check logs.")

# --- НОВАЯ КОМАНДА WEATHER ---

@bot.tree.command(name="weather", description="Показать погоду в конкретном городе")
@app_commands.describe(city="Название города")
async def weather(interaction: discord.Interaction, city: str):
    await interaction.response.defer()
    
    data = await fetch_weather(city)
    if not data:
        await interaction.followup.send(f"Город `{city}` не найден или API недоступно.")
        return

    try:
        with open("widget.html", "r", encoding="utf-8") as f:
            html_template = f.read()

        # Динамическая замена данных в HTML
        replacements = {
            "Москва": data['name'], # Подставляем город из ответа API (с правильной капитализацией)
            "Ясно": data['weather'][0]['description'].capitalize(),
            "-12°": f"{round(data['main']['temp'])}°",
            "84%": f"{data['main']['humidity']}%",
            "-18°": f"{round(data['main']['feels_like'])}°",
            "754": str(round(data['main']['pressure'] * 0.750062)), # hPa в мм рт. ст.
            "0": str(data.get('clouds', {}).get('all', 0))
        }

        for placeholder, value in replacements.items():
            html_template = html_template.replace(placeholder, value)

        browser = await get_browser()
        context = await browser.new_context(viewport={"width": 1300, "height": 1000})
        page = await context.new_page()
        
        try:
            # Рендерим модифицированный контент 
            await page.set_content(html_template, wait_until="domcontentloaded")
            await asyncio.sleep(0.4) 
            buffer = await page.screenshot(type="png", omit_background=True)
            
            file = discord.File(io.BytesIO(buffer), "weather.png")
            await interaction.followup.send(file=file)
        finally:
            await page.close()
            await context.close()

    except Exception:
        tb = traceback.format_exc()
        await send_unified_log("weather_render_error", discord.Color.red(), f"```py\n{tb}```", interaction)
        await interaction.followup.send("Ошибка генерации погоды.")

bot.run(TOKEN)