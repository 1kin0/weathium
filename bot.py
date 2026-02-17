import os
import io
import time

import discord
from discord.ext import commands
from discord import app_commands

from playwright.async_api import async_playwright
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="/", intents=intents)


async def render_html():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.set_viewport_size({"width": 1200, "height": 800})
        await page.goto(f'file://{os.path.abspath("index.html")}')
        buffer = await page.screenshot(full_page=False, type="png")
        await browser.close()
        return buffer


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
    latency_ms = round(bot.latency * 1000)
    await interaction.response.send_message(f'Pong! `{latency_ms}ms`')


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