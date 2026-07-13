"""
SQUAD Discord Bot — Python verzija
Igre: Toplo-Hladno, Bingo, Pogodi Riječ, Pogodi Objekat, Grebalica
Svaka igra se rotira automatski svakih 15 minuta.

Potrebne env varijable:
  DISCORD_BOT_TOKEN  - token bota iz Discord Developer Portala
  DISCORD_CHANNEL_ID - ID kanala gdje se igraju igre
"""

import asyncio
import os
import logging

import discord
from dotenv import load_dotenv

from games import GAMES

load_dotenv()

TOKEN = os.getenv("DISCORD_BOT_TOKEN")
CHANNEL_ID = int(os.getenv("DISCORD_CHANNEL_ID", "0"))
GAME_INTERVAL = 15 * 60  # 15 minuta u sekundama

if not TOKEN:
    raise RuntimeError("❌ DISCORD_BOT_TOKEN nije postavljen!")
if not CHANNEL_ID:
    raise RuntimeError("❌ DISCORD_CHANNEL_ID nije postavljen!")

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("squad-bot")

intents = discord.Intents.default()
intents.message_content = False  # Nije potrebno za button/modal igre

bot = discord.Client(intents=intents)

# Trenutno stanje igre
current_view = None
current_message = None
current_game_cls = None
game_index = 0


async def stop_current_game():
    global current_view, current_message, current_game_cls
    if current_game_cls and current_view and current_message:
        try:
            await current_game_cls.stop(current_view, current_message)
        except Exception as e:
            log.error(f"Greška pri zaustavljanju igre: {e}")
    current_view = None
    current_message = None
    current_game_cls = None


async def start_next_game(channel: discord.TextChannel):
    global current_view, current_message, current_game_cls, game_index

    await stop_current_game()

    game_cls = GAMES[game_index % len(GAMES)]
    game_index += 1

    log.info(f"Pokrećem igru: {game_cls.emoji} {game_cls.name}")

    await channel.send(
        f"{game_cls.emoji} **Sljedeća igra za 5 sekundi: {game_cls.name}!** Budite spremni!"
    )
    await asyncio.sleep(5)

    view, msg = await game_cls.start(channel)
    current_view = view
    current_message = msg
    current_game_cls = game_cls


async def game_loop(channel: discord.TextChannel):
    """Beskonačna petlja koja rotira igre svakih 15 minuta."""
    while True:
        try:
            await start_next_game(channel)
        except Exception as e:
            log.error(f"Greška pri pokretanju igre: {e}")

        await asyncio.sleep(GAME_INTERVAL)


@bot.event
async def on_ready():
    log.info(f"✅ Bot je online: {bot.user}")

    channel = bot.get_channel(CHANNEL_ID)
    if channel is None:
        try:
            channel = await bot.fetch_channel(CHANNEL_ID)
        except Exception:
            channel = None

    if not isinstance(channel, discord.TextChannel):
        log.error(f"❌ Kanal {CHANNEL_ID} nije pronađen ili nije tekstualni!")
        return

    await channel.send(
        "🤖 **SQUAD Bot je online!**\nIgre počinju svakih **15 minuta**. Budite spremni! 🎮"
    )

    log.info(f"🎮 Game loop pokrenut u kanalu #{channel.name}")
    bot.loop.create_task(game_loop(channel))


bot.run(TOKEN, log_handler=None)
