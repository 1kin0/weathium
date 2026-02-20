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
    try:
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
            else:
                await send_unified_log("api_warning", discord.Color.orange(), f"Error {resp.status}: {city}")
                return None

@bot.event
async def on_ready():
    await bot.tree.sync()
    await send_unified_log("startup", discord.Color.green(), "Bot online")
    asyncio.create_task(get_browser())

@bot.tree.command(name="ping", description="Check latency")
async def slash_ping(interaction: discord.Interaction):
    await interaction.response.send_message(f"`{round(bot.latency * 1000)}ms`", ephemeral=True)

@bot.tree.command(name="render", description="Render widget")
async def slash_render(interaction: discord.Interaction):
    await interaction.response.defer()
    path = os.path.abspath("/web/widget.html")
    
    try:
        browser = await get_browser()
        context = await browser.new_context(viewport={"width": 1300, "height": 1000})
        page = await context.new_page()
        try:
            await page.goto(f'file://{path}', wait_until="domcontentloaded")
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
        with open("/web/widget.html", "r", encoding="utf-8") as f:
            html = f.read()

        # Подготавливаем данные из OpenWeather API
        temp = round(data['main']['temp'])
        feels_like = round(data['main']['feels_like'])
        humidity = data['main']['humidity']
        pressure_hpa = data['main']['pressure']
        # Конвертируем гПа в мм рт. ст.
        pressure_mm = round(pressure_hpa * 0.750062)
        # Скорость ветра
        wind_speed = data['wind']['speed']
        # Описание погоды
        description = data['weather'][0]['description'].capitalize()

        replacements = {
            "Москва": data['name'],
            "Ясно": description,
            "-12°": f"{temp}°",
            "-18°": f"{feels_like}°",
            "84%": f"{humidity}%",
            "4.2": f"{wind_speed}", # Заменяем значение ветра
            "754": str(pressure_mm),
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