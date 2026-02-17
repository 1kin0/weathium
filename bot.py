import discord
from discord.ext import commands
from playwright.async_api import async_playwright
from dotenv import load_dotenv
import os
import io

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix='!', intents=intents)

async def render_html():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.set_viewport_size({"width": 1200, "height": 800})
        await page.goto(f'file://{os.path.abspath("index.html")}')
        buffer = await page.screenshot(full_page=False, type='png')
        await browser.close()
        return buffer

@bot.event
async def on_ready():
    print(f'{bot.user} connected')

@bot.command(name='render')
async def render(ctx):
    await ctx.message.delete()
    buffer = await render_html()
    file = discord.File(io.BytesIO(buffer), 'render.png')
    await ctx.send(file=file)

bot.run(TOKEN)