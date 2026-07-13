TOKEN = "MTUyNjE2OTU2NjA1OTgyMzE2NQ.GROlvN.aM_DC6e_i-4gH8XkJnH_hofQbbo0Lh7egHcHV8"
CHANNEL_ID = 1526169748499468379

import asyncio
import logging
import discord
from games import GAMES

GAME_INTERVAL = 15 * 60

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("squad-bot")

intents = discord.Intents.default()
intents.message_content = False
bot = discord.Client(intents=intents)

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
            log.error(f"Greška: {e}")
    current_view = None
    current_message = None
    current_game_cls = None

async def start_next_game(channel):
    global current_view, current_message, current_game_cls, game_index
    await stop_current_game()
    game_cls = GAMES[game_index % len(GAMES)]
    game_index += 1
    log.info(f"Pokrećem: {game_cls.emoji} {game_cls.name}")
    await channel.send(f"{game_cls.emoji} **Sljedeća igra za 5 sekundi: {game_cls.name}!** Budite spremni!")
    await asyncio.sleep(5)
    view, msg = await game_cls.start(channel)
    current_view = view
    current_message = msg
    current_game_cls = game_cls

async def game_loop(channel):
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
        log.error(f"❌ Kanal {CHANNEL_ID} nije pronađen!")
        return
    await channel.send("🤖 **SQUAD Bot je online!**\nIgre počinju svakih **15 minuta**! 🎮")
    log.info(f"🎮 Game loop pokrenut u #{channel.name}")
    bot.loop.create_task(game_loop(channel))

bot.run(TOKEN, log_handler=None)
