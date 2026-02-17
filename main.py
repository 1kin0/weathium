import os
import io
import time
import discord
import traceback
import asyncio
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

async def send_unified_log(log_type: str, color: discord.Color, content: str, interaction: discord.Interaction = None):
    guild = bot.get_guild(LOG_GUILD_ID)
    if not guild: return
    channel = guild.get_channel(LOG_CHANNEL_ID)
    if not channel: return

    # Header section
    timestamp = int(time.time())
    header = f"**TYPE : {log_type.upper()}**\n"
    header += f"**TIME : <t:{timestamp}:F>**\n"

    # Location section
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

@bot.event
async def on_ready():
    await bot.tree.sync()
    await send_unified_log("startup", discord.Color.green(), f"Bot is online. Latency: {round(bot.latency * 1000)}ms")

@bot.tree.command(name="ping", description="Check latency")
async def slash_ping(interaction: discord.Interaction):
    await interaction.response.send_message(f"`{round(bot.latency * 1000)}ms`", ephemeral=True)

@bot.tree.command(name="render", description="Render widget.html")
async def slash_render(interaction: discord.Interaction):
    await interaction.response.defer()
    
    # Check file existence first
    path = os.path.abspath("widget.html")
    if not os.path.exists(path):
        err_text = f"File not found: `{path}`"
        await send_unified_log("render_error", discord.Color.red(), err_text, interaction)
        await interaction.followup.send("`System error: missing source file`. Incident reported.")
        return

    try:
        browser = await get_browser()
        context = await browser.new_context(viewport={"width": 1200, "height": 1000})
        page = await context.new_page()
        
        try:
            await page.goto(f'file://{path}', wait_until="domcontentloaded", timeout=15000)
            await asyncio.sleep(0.5)
            buffer = await page.screenshot(type="png", omit_background=True)
            
            file = discord.File(io.BytesIO(buffer), "render.png")
            await interaction.followup.send(file=file)
            
        finally:
            await page.close()
            await context.close()
            
    except Exception:
        tb = traceback.format_exc()
        await send_unified_log("render_error", discord.Color.red(), f"```py\n{tb}```", interaction)
        await interaction.followup.send("`Rendering error`. The report has been sent to the developer.")

bot.run(TOKEN)