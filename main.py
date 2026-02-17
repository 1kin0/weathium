import os
import io
import time
import discord
import traceback
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

async def send_status_log(title: str, description: str, color: discord.Color, fields: dict = None):
    guild = bot.get_guild(LOG_GUILD_ID)
    if not guild: return
    channel = guild.get_channel(LOG_CHANNEL_ID)
    if not channel: return

    embed = discord.Embed(
        title=f"**{title.upper()}**",
        description=description[:2000],
        color=color,
        timestamp=discord.utils.utcnow()
    )
    
    if fields:
        for name, value in fields.items():
            embed.add_field(name=name, value=value, inline=True)
    
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
            await send_status_log("Browser System", "Chromium instance initialized", discord.Color.blue())
        except Exception as e:
            await send_status_log("Critical Launch Error", f"```py\n{str(e)}```", discord.Color.red())
            raise e
    return _browser

async def render_html():
    browser = await get_browser()
    context = await browser.new_context(viewport={"width": 1200, "height": 800})
    page = await context.new_page()
    try:
        path = os.path.abspath("index.html")
        await page.goto(f'file://{path}', wait_until="domcontentloaded", timeout=20000)
        return await page.screenshot(type="png")
    finally:
        await page.close()
        await context.close()

@bot.event
async def on_ready():
    await bot.tree.sync()
    await send_status_log(
        "Bot Startup", 
        "System is now online and commands are synced.", 
        discord.Color.green(),
        {"Latency": f"`{round(bot.latency * 1000)}ms`", "Status": "`Active`"}
    )

@bot.tree.command(name="ping", description="Check latency")
async def slash_ping(interaction: discord.Interaction):
    await interaction.response.send_message(f'Pong! `{round(bot.latency * 1000)}ms`')

@bot.tree.command(name="render", description="Render page")
async def slash_render(interaction: discord.Interaction):
    await interaction.response.defer()
    start_time = time.perf_counter()
    
    try:
        buffer = await render_html()
        total_ms = (time.perf_counter() - start_time) * 1000
        file = discord.File(io.BytesIO(buffer), "render.png")
        await interaction.followup.send(file=file)
    
    except Exception as e:
        error_type = type(e).__name__
        error_details = str(e)[:1000]
        
        # Информативный лог для канала
        await send_status_log(
            "Render Command Failed",
            f"**Error Type:** `{error_type}`\n**Summary:** {error_details}",
            discord.Color.red(),
            {
                "User": f"`{interaction.user}`",
                "Guild": f"`{interaction.guild.name if interaction.guild else 'DM'}`",
                "User ID": f"`{interaction.user.id}`"
            }
        )
        
        # Ответ пользователю
        await interaction.followup.send(content=f"Execution error: `{error_type}`. Details sent to logs.")

bot.run(TOKEN)