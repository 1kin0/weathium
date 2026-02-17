import os
import io
import time
import discord
from discord.ext import commands
from playwright.async_api import async_playwright
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")
LOG_GUILD_ID = 1473082652452978991
LOG_CHANNEL_ID = 1473409327514648597

_browser = None
_playwright = None

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="/", intents=intents)

async def send_log_embed(title: str, description: str, color: discord.Color):
    guild = bot.get_guild(LOG_GUILD_ID)
    if guild:
        channel = guild.get_channel(LOG_CHANNEL_ID)
        if channel:
            safe_desc = (description[:3500] + '...') if len(description) > 3500 else description
            embed = discord.Embed(title=title, description=safe_desc, color=color, timestamp=discord.utils.utcnow())
            await channel.send(embed=embed)

async def get_browser():
    global _browser, _playwright
    # Проверка: если браузер закрыт или упал, сбрасываем состояние
    if _browser and not _browser.is_connected():
        _browser = None

    if _browser is None:
        try:
            if _playwright is None:
                _playwright = await async_playwright().start()
            _browser = await _playwright.chromium.launch(
                headless=True,
                args=[
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-gpu"
                ]
            )
            await send_log_embed("Browser Status", "New instance started", discord.Color.green())
        except Exception as e:
            await send_log_embed("Browser Critical Error", f"Launch failed: `{str(e)[:1000]}`", discord.Color.red())
            raise e
    return _browser

async def render_html():
    browser = await get_browser()
    context = await browser.new_context(viewport={"width": 1200, "height": 800})
    page = await context.new_page()
    try:
        # Убедитесь, что index.html находится в корне проекта
        path = os.path.abspath("index.html")
        await page.goto(f'file://{path}', wait_until="domcontentloaded", timeout=20000)
        return await page.screenshot(type="png")
    except Exception as e:
        await send_log_embed("Render Error", f"Failed: `{str(e)[:1000]}`", discord.Color.red())
        raise e
    finally:
        await page.close()
        await context.close()

@bot.event
async def on_ready():
    await bot.tree.sync()
    await send_log_embed("Bot Online", f"Ready. Latency: `{round(bot.latency * 1000)}ms`", discord.Color.blue())

@bot.tree.command(name="ping", description="Check latency")
async def slash_ping(interaction: discord.Interaction):
    await interaction.response.send_message(f'Pong! `{round(bot.latency * 1000)}ms`')

@bot.tree.command(name="render", description="Render page")
async def slash_render(interaction: discord.Interaction):
    await interaction.response.defer()
    try:
        buffer = await render_html()
        file = discord.File(io.BytesIO(buffer), "render.png")
        await interaction.followup.send(file=file)
    except Exception as e:
        err_msg = str(e)[:1500]
        await interaction.followup.send(content=f"Error: `{err_msg}`")

bot.run(TOKEN)