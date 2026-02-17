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
os.environ["PLAYWRIGHT_BROWSERS_PATH"] = "/app/pw-browsers"

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
            # Prevent 400 Bad Request by truncating long error messages
            safe_desc = (description[:3500] + '...') if len(description) > 3500 else description
            embed = discord.Embed(
                title=title,
                description=safe_desc,
                color=color,
                timestamp=discord.utils.utcnow()
            )
            await channel.send(embed=embed)

async def get_browser():
    global _browser, _playwright
    if _browser is None:
        try:
            _playwright = await async_playwright().start()
            _browser = await _playwright.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage", "--disable-gpu", "--no-zygote", "--single-process"]
            )
            await send_log_embed("Browser Status", "Instance started successfully", discord.Color.green())
        except Exception as e:
            await send_log_embed("Browser Critical Error", f"Failed to launch: `{str(e)}`", discord.Color.red())
            raise e
    return _browser

async def render_html():
    browser = await get_browser()
    context = await browser.new_context(viewport={"width": 1200, "height": 800})
    page = await context.new_page()
    try:
        await page.goto(f'file://{os.path.abspath("index.html")}', wait_until="domcontentloaded", timeout=20000)
        return await page.screenshot(type="png")
    except Exception as e:
        await send_log_embed("Render Error", f"Execution failed: `{str(e)}`", discord.Color.red())
        raise e
    finally:
        await page.close()
        await context.close()

@bot.event
async def on_ready():
    await bot.tree.sync()
    await send_log_embed("Bot Online", f"Sync complete. Latency: `{round(bot.latency * 1000)}ms`", discord.Color.blue())

@bot.tree.command(name="render", description="Render page")
async def slash_render(interaction: discord.Interaction):
    start_total = time.perf_counter()
    await interaction.response.defer()
    try:
        buffer = await render_html()
        total_ms = (time.perf_counter() - start_total) * 1000
        file = discord.File(io.BytesIO(buffer), "render.png")
        embed = discord.Embed(title="Render Result", color=discord.Color.blue())
        embed.set_footer(text=f"Time: {total_ms:.1f}ms | User: {interaction.user}")
        await interaction.followup.send(file=file, embed=embed)
    except Exception as e:
        raw_err = str(e)
        short_err = (raw_err[:1500] + '...') if len(raw_err) > 1500 else raw_err
        await interaction.followup.send(content=f"Error: `{short_err}`")
        await send_log_embed("User Command Error", f"User: `{interaction.user}`\nError: `{short_err}`", discord.Color.red())

bot.run(TOKEN)