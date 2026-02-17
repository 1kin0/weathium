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

async def send_status_log(title: str, description: str, color: discord.Color, fields: dict = None, is_error: bool = False):
    guild = bot.get_guild(LOG_GUILD_ID)
    if not guild: return
    channel = guild.get_channel(LOG_CHANNEL_ID)
    if not channel: return

    # Крупное время и заголовок для моментального опознания
    current_time = int(time.time())
    main_header = f"# 🕒 TIME: <t:{current_time}:T>\n# ❌ ERROR: {title}" if is_error else f"# ✅ {title}"

    embed = discord.Embed(
        title=main_header,
        description=f"**DETAILS:**\n{description[:1800]}",
        color=color
    )
    
    if fields:
        for name, value in fields.items():
            embed.add_field(name=f"**{name.upper()}**", value=value, inline=True)
    
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
            await send_status_log("Browser Engine", "Started successfully", discord.Color.blue())
        except Exception as e:
            await send_status_log("Launch Failed", f"```\n{str(e)}```", discord.Color.red(), is_error=True)
            raise e
    return _browser

@bot.event
async def on_ready():
    await bot.tree.sync()
    await send_status_log("Bot Online", "Ready to work", discord.Color.green())

@bot.tree.command(name="ping", description="Latency check")
async def slash_ping(interaction: discord.Interaction):
    await interaction.response.send_message(f"`{round(bot.latency * 1000)}ms`", ephemeral=True)

@bot.tree.command(name="render", description="Render page")
async def slash_render(interaction: discord.Interaction):
    await interaction.response.defer()
    
    try:
        browser = await get_browser()
        context = await browser.new_context(viewport={"width": 1200, "height": 800})
        page = await context.new_page()
        
        try:
            path = os.path.abspath("index.html")
            await page.goto(f'file://{path}', wait_until="domcontentloaded", timeout=15000)
            await asyncio.sleep(0.5)
            buffer = await page.screenshot(type="png")
            
            file = discord.File(io.BytesIO(buffer), "render.png")
            await interaction.followup.send(file=file)
            
        finally:
            await page.close()
            await context.close()
            
    except Exception as e:
        tb = traceback.format_exc()
        # ЛОГ ДЛЯ ТЕБЯ (ПОДРОБНО И КРУПНО)
        await send_status_log(
            title=f"Render {type(e).__name__}",
            description=f"```py\n{tb[:1500]}```",
            color=discord.Color.red(),
            fields={
                "User": f"`{interaction.user}`",
                "Guild": f"`{interaction.guild.name if interaction.guild else 'DM'}`",
                "ID": f"`{interaction.user.id}`"
            },
            is_error=True
        )
        # ОТВЕТ ПОЛЬЗОВАТЕЛЮ (КРАТКО)
        await interaction.followup.send(content="`Browser error`. Try again later.")

bot.run(TOKEN)