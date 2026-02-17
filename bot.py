import os
import io
import time
import logging
import discord
from discord.ext import commands
from playwright.async_api import async_playwright
from dotenv import load_dotenv

load_dotenv()

# Configuration
TOKEN = os.getenv("DISCORD_TOKEN")
LOG_GUILD_ID = 1473082652452978991
LOG_CHANNEL_ID = 1473409327514648597
os.environ["PLAYWRIGHT_BROWSERS_PATH"] = "/app/pw-browsers"

_browser = None
_playwright = None

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="/", intents=intents)

async def send_log(message: str):
    guild = bot.get_guild(LOG_GUILD_ID)
    if guild:
        channel = guild.get_channel(LOG_CHANNEL_ID)
        if channel:
            timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
            await channel.send(f"[`{timestamp}`] {message}")

async def get_browser():
    global _browser, _playwright
    if _browser is None:
        try:
            _playwright = await async_playwright().start()
            _browser = await _playwright.chromium.launch(
                headless=True,
                args=[
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-gpu",
                    "--no-zygote",
                    "--single-process"
                ]
            )
            await send_log("Browser instance started successfully")
        except Exception as e:
            await send_log(f"Critical error starting browser: `{str(e)}` ")
            raise e
    return _browser

async def render_html():
    browser = await get_browser()
    context = await browser.new_context(viewport={"width": 1200, "height": 800})
    page = await context.new_page()
    
    try:
        await page.goto(f'file://{os.path.abspath("index.html")}', wait_until="domcontentloaded", timeout=30000)
        buffer = await page.screenshot(type="png")
        return buffer
    except Exception as e:
        await send_log(f"Render process failed: `{str(e)}` ")
        raise e
    finally:
        await page.close()
        await context.close()

@bot.event
async def on_ready():
    print(f"{bot.user} connected")
    await bot.tree.sync()
    await send_log(f"Bot status: `Online`. Latency: `{round(bot.latency * 1000)}ms`")

@bot.tree.command(name="ping", description="Check bot latency")
async def slash_ping(interaction: discord.Interaction):
    start = time.perf_counter()
    await interaction.response.send_message('Pong!')
    duration = round((time.perf_counter() - start) * 1000)
    await interaction.edit_original_response(content=f'Pong! `{duration}ms`')

@bot.tree.command(name="render", description="Render page and send screenshot")
async def slash_render(interaction: discord.Interaction):
    start_total = time.perf_counter()
    await interaction.response.defer()

    try:
        start_render = time.perf_counter()
        buffer = await render_html()
        render_ms = (time.perf_counter() - start_render) * 1000
        total_ms = (time.perf_counter() - start_total) * 1000

        file = discord.File(io.BytesIO(buffer), "render.png")
        embed = discord.Embed(title="Render Result", color=0x3498db)
        embed.add_field(name="Render Time", value=f"`{render_ms:.1f} ms`", inline=True)
        embed.add_field(name="Total Time", value=f"`{total_ms:.1f} ms`", inline=True)
        embed.set_footer(text=f"Requested by {interaction.user}", icon_url=interaction.user.display_avatar.url)

        await interaction.followup.send(file=file, embed=embed)
    except Exception as e:
        error_msg = f"Failed to render: `{str(e)}`"
        await interaction.followup.send(content=error_msg)
        await send_log(f"User {interaction.user} triggered error: `{str(e)}`")

bot.run(TOKEN)