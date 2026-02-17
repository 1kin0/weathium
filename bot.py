import os
import io
import time

import discord
from discord.ext import commands
from discord import app_commands

os.environ["PLAYWRIGHT_BROWSERS_PATH"] = "/app/pw-browsers"

from playwright.async_api import async_playwright
from dotenv import load_dotenv

_browser = None
_playwright = None

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="/", intents=intents)


async def get_browser():
    global _browser, _playwright
    if _browser is None:
        _playwright = await async_playwright().start()
        _browser = await _playwright.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage", # КРИТИЧНО для Railway
                "--disable-gpu",           # Экономит RAM
                "--no-zygote",
                "--single-process"         # Максимальная экономия памяти
            ]
        )
    return _browser

async def render_html():
    browser = await get_browser()
    # Используем контекст, чтобы куки/кеш не забивали память со временем
    context = await browser.new_context(
        viewport={"width": 1200, "height": 800} # Указываем размер сразу
    )
    page = await context.new_page()
    
    try:
        # Быстрая загрузка локального файла
        await page.goto(f'file://{os.path.abspath("index.html")}', wait_until="domcontentloaded")
        
        # Скриншот только нужной области (если есть конкретный id/class)
        # Например: buffer = await page.locator(".card").screenshot()
        buffer = await page.screenshot(type="png")
        
        return buffer
    finally:
        # Закрываем только вкладку и контекст, но ОСТАВЛЯЕМ браузер запущенным
        await page.close()
        await context.close()

async def close_browser():
    if _browser:
        await _browser.close()
    if _playwright:
        await _playwright.stop()


@bot.event
async def on_ready():
    print(f"{bot.user} connected")
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} slash commands")
    except Exception as e:
        print(f"Failed to sync commands: {e}")


@bot.tree.command(name="ping", description="Check bot latency")
async def slash_ping(interaction: discord.Interaction):
    start = time.perf_counter()
    await interaction.response.send_message('Pong!')
    end = time.perf_counter()
    duration = round((end - start) * 1000)
    await interaction.edit_original_response(content=f'Pong! `{duration}ms`')


@bot.tree.command(name="render", description="Render page and send screenshot")
async def slash_render(interaction: discord.Interaction):
    start_total = time.perf_counter()
    await interaction.response.defer()

    start_render = time.perf_counter()
    buffer = await render_html()
    end_render = time.perf_counter()

    render_ms = (end_render - start_render) * 1000
    total_ms = (end_render - start_total) * 1000

    file = discord.File(io.BytesIO(buffer), "render.png")

    embed = discord.Embed(
        title="Render result",
        color=discord.Color.blue(),
    )
    embed.add_field(
        name="Render time",
        value=f"{render_ms:.1f} ms",
        inline=True,
    )
    embed.add_field(
        name="Total time",
        value=f"{total_ms:.1f} ms",
        inline=True,
    )
    embed.set_footer(
        text=f"Requested by {interaction.user}",
        icon_url=interaction.user.display_avatar.url,
    )

    await interaction.followup.send(file=file, embed=embed)


bot.run(TOKEN)