import discord
from discord.ext import commands
from discord import app_commands

from playwright.async_api import async_playwright
from dotenv import load_dotenv

import os
import io

load_dotenv()

TOKEN = os.getenv('DISCORD_TOKEN')

intents = discord.Intents.default()
intents.message_content = True

# для slash-команд используем commands.Bot c tree (app_commands)
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

    # синхронизируем slash-команды с Discord
    try:
        synced = await bot.tree.sync()
        print(f'Synced {len(synced)} slash commands')
    except Exception as e:
        print(f'Failed to sync commands: {e}')


# Обычная префиксная команда: !render
@bot.command(name='render')
async def render(ctx: commands.Context):
    # безопасно пробуем удалить сообщение (чтобы не падать без прав)
    try:
        await ctx.message.delete()
    except discord.Forbidden:
        pass
    except discord.NotFound:
        pass

    buffer = await render_html()
    file = discord.File(io.BytesIO(buffer), 'render.png')
    await ctx.send(file=file)


# Обычная префиксная команда: !ping
@bot.command(name='ping')
async def ping(ctx: commands.Context):
    latency_ms = round(bot.latency * 1000)
    await ctx.send(f'Pong! `{latency_ms} ms`')


# Slash-команда: /ping
@bot.tree.command(name="ping", description="Проверить задержку бота")
async def slash_ping(interaction: discord.Interaction):
    latency_ms = round(bot.latency * 1000)
    await interaction.response.send_message(f'Pong! `{latency_ms} ms`')


# Slash-команда: /render
@bot.tree.command(name="render", description="Отрендерить страницу и отправить скриншот")
async def slash_render(interaction: discord.Interaction):
    await interaction.response.defer()  # чтобы был «thinking...»

    buffer = await render_html()
    file = discord.File(io.BytesIO(buffer), 'render.png')
    await interaction.followup.send(file=file)


bot.run(TOKEN)