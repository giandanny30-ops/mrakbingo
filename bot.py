# ============================================================
#  SQUAD Discord Bot — sve u jednom fajlu
# ============================================================

TOKEN = "MTUyNjE2OTU2NjA1OTgyMzE2NQ.Ga33Tz.6wN5msjMoPjJymrpLastbzbzIiduKfiUEepCOg"
CHANNEL_ID = 1526169748499468379

# ============================================================

import asyncio
import logging
import random
import discord

GAME_INTERVAL = 15 * 60

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("squad-bot")

# ============================================================
# IGRA 1: TOPLO-HLADNO
# ============================================================

def _th_build_embed(secret, attempts, signal, winner=None, stopped=False):
    if winner:
        color = discord.Color.green()
        desc = f"🏆 <@{winner}> je pogodio/la tajni broj **{secret}**!"
    elif stopped:
        color = discord.Color.red()
        desc = f"🛑 Igra završena! Tajni broj je bio **{secret}**"
    else:
        color = discord.Color.orange()
        desc = "🔥 Pogodi tajni broj — toplije ili hladnije!"
    embed = discord.Embed(title="☀️ Toplo-Hladno", description=desc, color=color)
    embed.add_field(name="🎯 Raspon", value="`1 — 100`", inline=True)
    embed.add_field(name="📊 Pokušaji", value=f"`{attempts}`", inline=True)
    sig_text = signal if signal else "🎮 Igra počinje! Pogodi broj!"
    if winner:
        sig_text = f"🏆 Pogođeno za {attempts} pokušaj/a!"
    embed.add_field(name="📡 Signal", value=sig_text, inline=False)
    embed.set_footer(text="SQUAD Bot • Klikni i pogodi broj!")
    return embed

class _THGuessModal(discord.ui.Modal, title="Pogodi broj (1-100)"):
    number = discord.ui.TextInput(label="Unesi broj od 1 do 100", placeholder="npr. 42", min_length=1, max_length=3)
    def __init__(self, view):
        super().__init__()
        self.game_view = view
    async def on_submit(self, interaction: discord.Interaction):
        try:
            guess = int(self.number.value.strip())
            if guess < 1 or guess > 100:
                raise ValueError
        except ValueError:
            await interaction.response.send_message("❌ Unesi validan broj između 1 i 100!", ephemeral=True)
            return
        v = self.game_view
        v.attempts += 1
        diff = abs(guess - v.secret)
        if diff == 0:
            v.winner = interaction.user.id
            v.active = False
            v.disable_all()
            await interaction.response.edit_message(embed=_th_build_embed(v.secret, v.attempts, "", winner=interaction.user.id), view=v)
            return
        if diff <= 5:   signal = f"🔥 Prevrelo! (tvoj broj: `{guess}`)"
        elif diff <= 15: signal = f"♨️ Toplije! (tvoj broj: `{guess}`)"
        elif diff <= 30: signal = f"🌤️ Hladnije... (tvoj broj: `{guess}`)"
        else:            signal = f"🧊 Hladno! (tvoj broj: `{guess}`)"
        v.signal = f"<@{interaction.user.id}> — {signal}"
        await interaction.response.edit_message(embed=_th_build_embed(v.secret, v.attempts, v.signal), view=v)

class _THView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.secret = random.randint(1, 100)
        self.attempts = 0
        self.signal = ""
        self.winner = None
        self.active = True
    def disable_all(self):
        for item in self.children: item.disabled = True
    @discord.ui.button(label="🌡️ Pogodi broj", style=discord.ButtonStyle.primary)
    async def guess_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.active:
            await interaction.response.send_message("❌ Igra je gotova!", ephemeral=True); return
        await interaction.response.send_modal(_THGuessModal(self))
    @discord.ui.button(label="🎯 Završi igru", style=discord.ButtonStyle.danger)
    async def stop_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.active:
            await interaction.response.send_message("❌ Igra je već gotova!", ephemeral=True); return
        self.active = False
        self.disable_all()
        await interaction.response.edit_message(embed=_th_build_embed(self.secret, self.attempts, "", stopped=True), view=self)

class ToploHladnoGame:
    name = "Toplo-Hladno"; emoji = "☀️"
    @staticmethod
    async def start(channel):
        view = _THView()
        msg = await channel.send(embed=_th_build_embed(view.secret, 0, ""), view=view)
        return view, msg
    @staticmethod
    async def stop(view, message):
        if not view.active: return
        view.active = False; view.disable_all()
        await message.edit(embed=_th_build_embed(view.secret, view.attempts, "", stopped=True), view=view)

# ============================================================
# IGRA 2: BINGO
# ============================================================

_BINGO_TOTAL = 30
_BINGO_INTERVAL = 20

def _bingo_generate_card():
    pool = list(range(1, _BINGO_TOTAL + 1)); random.shuffle(pool); return pool[:9]

def _bingo_render_card(card, called):
    rows = []
    for i in range(3):
        row = [f"~~`{card[i*3+j]:02d}`~~" if card[i*3+j] in called else f"`{card[i*3+j]:02d}`" for j in range(3)]
        rows.append(" ".join(row))
    return "\n".join(rows)

def _bingo_check(card, called):
    lines = [[0,1,2],[3,4,5],[6,7,8],[0,3,6],[1,4,7],[2,5,8],[0,4,8],[2,4,6]]
    return any(all(card[i] in called for i in line) for line in lines)

def _bingo_embed(called, players, winner=None, round_num=0):
    last_str = " ".join(f"`{n}`" for n in called[-5:]) if called else "Čekamo..."
    if winner:
        color = discord.Color.green(); desc = f"🏆 <@{winner}> je pobijedio/la! **BINGO!**"
    else:
        color = discord.Color.purple(); desc = "Skupi karticu i čekaj svoja polja! Kad budeš imao red — stisni BINGO!"
    embed = discord.Embed(title="🎱 Bingo!", description=desc, color=color)
    embed.add_field(name="🔢 Izvučeni brojevi", value=last_str, inline=False)
    embed.add_field(name="👥 Igrači", value=f"{len(players)} u igri" if players else "Nitko još", inline=True)
    embed.add_field(name="🔄 Runda", value=str(round_num), inline=True)
    embed.set_footer(text="SQUAD Bot • Uzmi karticu i igraj Bingo!")
    return embed

class _BingoView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.called = []; self.players = {}
        self.pool = list(range(1, _BINGO_TOTAL + 1)); random.shuffle(self.pool)
        self.winner = None; self.active = True; self.round = 0
        self.message = None; self._task = None
    def disable_all(self):
        for item in self.children: item.disabled = True
    async def call_loop(self):
        while self.active and self.pool:
            await asyncio.sleep(_BINGO_INTERVAL)
            if not self.active or not self.pool: break
            num = self.pool.pop(); self.called.append(num); self.round += 1
            if self.message:
                try: await self.message.edit(embed=_bingo_embed(self.called, self.players, round_num=self.round), view=self)
                except Exception: pass
    @discord.ui.button(label="🎟️ Uzmi karticu", style=discord.ButtonStyle.success)
    async def join_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.active:
            await interaction.response.send_message("❌ Igra je gotova!", ephemeral=True); return
        uid = interaction.user.id
        if uid in self.players:
            await interaction.response.send_message("✅ Već imaš karticu! Klikni **Moja kartica**.", ephemeral=True); return
        card = _bingo_generate_card(); self.players[uid] = card
        card_str = _bingo_render_card(card, set(self.called))
        await interaction.response.send_message(f"🎟️ Tvoja Bingo kartica:\n\n{card_str}\n\nPrati izvučene brojeve i stisni **BINGO!** kad popuniš red!", ephemeral=True)
        if self.message: await self.message.edit(embed=_bingo_embed(self.called, self.players, round_num=self.round), view=self)
    @discord.ui.button(label="📋 Moja kartica", style=discord.ButtonStyle.secondary)
    async def card_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        uid = interaction.user.id; card = self.players.get(uid)
        if not card:
            await interaction.response.send_message("❌ Nemaš karticu! Klikni **Uzmi karticu** prvo.", ephemeral=True); return
        card_str = _bingo_render_card(card, set(self.called))
        called_str = " ".join(f"`{n}`" for n in self.called) if self.called else "Nitko još nije pozvan"
        await interaction.response.send_message(f"📋 Tvoja kartica:\n\n{card_str}\n\n🔢 Izvučeni: {called_str}", ephemeral=True)
    @discord.ui.button(label="🎉 BINGO!", style=discord.ButtonStyle.primary)
    async def bingo_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.active:
            await interaction.response.send_message("❌ Igra je gotova!", ephemeral=True); return
        uid = interaction.user.id; card = self.players.get(uid)
        if not card:
            await interaction.response.send_message("❌ Nemaš karticu! Klikni **Uzmi karticu** prvo.", ephemeral=True); return
        if _bingo_check(card, set(self.called)):
            self.winner = uid; self.active = False; self.disable_all()
            if self._task: self._task.cancel()
            await interaction.response.edit_message(embed=_bingo_embed(self.called, self.players, winner=uid, round_num=self.round), view=self)
        else:
            await interaction.response.send_message("❌ Još nemaš Bingo! Nastavi čekati brojeve.", ephemeral=True)

class BingoGame:
    name = "Bingo"; emoji = "🎱"
    @staticmethod
    async def start(channel):
        view = _BingoView()
        msg = await channel.send(embed=_bingo_embed([], {}, round_num=0), view=view)
        view.message = msg; view._task = asyncio.create_task(view.call_loop())
        return view, msg
    @staticmethod
    async def stop(view, message):
        view.active = False
        if view._task: view._task.cancel()
        view.disable_all()
        await message.edit(embed=_bingo_embed(view.called, view.players, round_num=view.round), view=view)

# ============================================================
# IGRA 3: POGODI RIJEČ
# ============================================================

_WORDS = [
    "jabuka","banana","kruska","maslina","naranca","zemlja","voda","vjetar","sunce","mjesec",
    "krevet","stolica","prozor","vrata","lampa","macka","pseto","konj","ptica","riba",
    "planina","rijeka","suma","more","jezero","ljubav","sreca","nada","vjera","mir",
    "skola","knjiga","olovka","papir","tabla","gitara","bubanj","violina","truba","klavir",
    "cokolada","sladoled","kolac","pizza","burger","avion","brod","vlak","bicikl","auto",
]
_MAX_WRONG = 6
_HANGMAN = ["😶","😕","😟","😦","😧","😨","💀"]

def _rij_mask(word, guessed):
    return " ".join(f"**{c.upper()}**" if c in guessed else r"\\_" for c in word)

def _rij_embed(word, guessed, wrong, winner=None, failed=False):
    stage = _HANGMAN[min(len(set(wrong)), _MAX_WRONG)]
    if winner:
        color = discord.Color.green(); title = "📝 Pogodi Riječ — Pobjeda!"; desc = f"🏆 <@{winner}> je pogodio/la riječ **{word.upper()}**!"
    elif failed:
        color = discord.Color.red(); title = "📝 Pogodi Riječ — Kraj!"; desc = f"💀 Niko nije pogodio! Riječ je bila **{word.upper()}**"
    else:
        color = discord.Color.blue(); title = "📝 Pogodi Riječ"; desc = "Pogodi skrivenu riječ slovo po slovo!"
    embed = discord.Embed(title=title, description=desc, color=color)
    embed.add_field(name="🔤 Riječ", value=_rij_mask(word, set(guessed)) or r"\\_", inline=False)
    embed.add_field(name="❌ Pogrešna slova", value=" ".join(f"`{l.upper()}`" for l in wrong) if wrong else "Nema još", inline=True)
    embed.add_field(name=f"{stage} Pokušaji", value=f"{len(set(wrong))} / {_MAX_WRONG}", inline=True)
    embed.set_footer(text="SQUAD Bot • Klikni i pogodi slovo!")
    return embed

class _LetterModal(discord.ui.Modal, title="Pogodi slovo"):
    letter = discord.ui.TextInput(label="Unesi jedno slovo", placeholder="npr. A", min_length=1, max_length=1)
    def __init__(self, view):
        super().__init__(); self.game_view = view
    async def on_submit(self, interaction: discord.Interaction):
        v = self.game_view; l = self.letter.value.strip().lower()
        if l in v.guessed or l in v.wrong:
            await interaction.response.send_message(f"⚠️ Slovo `{l.upper()}` je već pogađano!", ephemeral=True); return
        if l in v.word: v.guessed.append(l)
        else: v.wrong.append(l)
        is_won = all(c in set(v.guessed) for c in v.word)
        is_failed = len(v.wrong) >= _MAX_WRONG
        if is_won: v.winner = interaction.user.id; v.active = False; v.disable_all()
        elif is_failed: v.failed = True; v.active = False; v.disable_all()
        await interaction.response.edit_message(embed=_rij_embed(v.word, v.guessed, v.wrong, winner=v.winner, failed=v.failed), view=v)

class _WordModal(discord.ui.Modal, title="Pogodi cijelu riječ"):
    word_input = discord.ui.TextInput(label="Unesi cijelu riječ", placeholder="npr. jabuka", min_length=2, max_length=20)
    def __init__(self, view):
        super().__init__(); self.game_view = view
    async def on_submit(self, interaction: discord.Interaction):
        v = self.game_view; guess = self.word_input.value.strip().lower()
        if guess == v.word:
            v.winner = interaction.user.id; v.guessed = list(v.word); v.active = False; v.disable_all()
            await interaction.response.edit_message(embed=_rij_embed(v.word, v.guessed, v.wrong, winner=v.winner), view=v)
        else:
            v.wrong.extend(["?","!"])
            if len(v.wrong) >= _MAX_WRONG: v.failed = True; v.active = False; v.disable_all()
            await interaction.response.send_message(f"❌ Nije **{guess}**! Izgubio/la si 2 pokušaja.", ephemeral=True)
            if v.message: await v.message.edit(embed=_rij_embed(v.word, v.guessed, v.wrong, failed=v.failed), view=v)

class _RijView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.word = random.choice(_WORDS); self.guessed = []; self.wrong = []
        self.winner = None; self.failed = False; self.active = True; self.message = None
    def disable_all(self):
        for item in self.children: item.disabled = True
    @discord.ui.button(label="🔡 Pogodi slovo", style=discord.ButtonStyle.primary)
    async def letter_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.active:
            await interaction.response.send_message("❌ Igra je gotova!", ephemeral=True); return
        await interaction.response.send_modal(_LetterModal(self))
    @discord.ui.button(label="💡 Pogodi cijelu riječ", style=discord.ButtonStyle.success)
    async def word_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.active:
            await interaction.response.send_message("❌ Igra je gotova!", ephemeral=True); return
        await interaction.response.send_modal(_WordModal(self))

class PogodiRijec:
    name = "Pogodi Riječ"; emoji = "📝"
    @staticmethod
    async def start(channel):
        view = _RijView()
        msg = await channel.send(embed=_rij_embed(view.word, [], []), view=view)
        view.message = msg; return view, msg
    @staticmethod
    async def stop(view, message):
        if not view.active: return
        view.active = False; view.failed = True; view.disable_all()
        await message.edit(embed=_rij_embed(view.word, view.guessed, view.wrong, failed=True), view=view)

# ============================================================
# IGRA 4: POGODI OBJEKAT
# ============================================================

_OBJECTS = [
    {"answer":"telefon","emoji":"📱","clues":["Imam ekran koji možeš dodirivati.","Nosim ga u džepu svaki dan.","Možeš me koristiti za pozivanje.","Imam kameru i mikrofon.","Mogu slati poruke i e-mailove."]},
    {"answer":"auto","emoji":"🚗","clues":["Imam četiri kotača.","Koristim gorivo ili struju.","Vozač me upravlja volanom.","Mogu prevesti nekoliko putnika.","Imam svjetla sprijeda i straga."]},
    {"answer":"knjiga","emoji":"📚","clues":["Napravljen/a sam od papira.","Imam korice i stranice.","Čuvam znanje i priče.","Možeš me naći u biblioteci.","Pisci me stvaraju godinama."]},
    {"answer":"gitara","emoji":"🎸","clues":["Imam žice koje se drmaju.","Glazbalo sam.","Koristim se u rock i pop muzici.","Imam vrat i tijelo.","Možeš svirati akorde na meni."]},
    {"answer":"pizza","emoji":"🍕","clues":["Jelo sam talijanskog porijekla.","Imam okrugao oblik.","Napravljen/a sam od tijesta.","Na meni može biti sir i paradajz.","Pečem se u pećnici."]},
    {"answer":"sunce","emoji":"☀️","clues":["Zvijezda sam u centru našeg sistema.","Dajem toplinu i svjetlost.","Bez mene ne bi bilo života na Zemlji.","Vidljiv/a sam danju ali ne i noću.","Izlazim na istoku i zalazim na zapadu."]},
    {"answer":"pas","emoji":"🐕","clues":["Životinja sam s četiri noge.","Znam se čuti lajanjem.","Čest sam kućni ljubimac.","Imam rep koji maham kad sam sretan.","Zovem se 'čovjekov najbolji prijatelj'."]},
    {"answer":"frizider","emoji":"🧊","clues":["Električni uređaj sam.","Hladim hranu i piće.","Nalazi me se u kuhinji.","Imam vrata i police iznutra.","Čuvam hranu svježom duže."]},
]

def _obj_embed(puzzle, clues_shown, attempts, winner=None, gave_up=False):
    clues = puzzle["clues"][:clues_shown]
    clues_text = "\n".join(f"**{i+1}.** {c}" for i, c in enumerate(clues)) if clues else "Klikni Pogodi ili traži trag!"
    if winner:
        color = discord.Color.green(); title = "🔍 Pogodi Objekat — Pogođeno!"; desc = f"🏆 <@{winner}> je pogodio/la! Odgovor je bio **{puzzle['answer'].upper()}** {puzzle['emoji']}"
    elif gave_up:
        color = discord.Color.red(); title = "🔍 Pogodi Objekat — Kraj!"; desc = f"❌ Niko nije pogodio! Odgovor je bio **{puzzle['answer'].upper()}** {puzzle['emoji']}"
    else:
        color = discord.Color.teal(); title = f"🔍 Pogodi Objekat {puzzle['emoji']}"; desc = "Pažljivo čitaj tragove i pogodi o čemu se radi!"
    embed = discord.Embed(title=title, description=desc, color=color)
    embed.add_field(name=f"💡 Tragovi ({clues_shown}/{len(puzzle['clues'])})", value=clues_text, inline=False)
    embed.add_field(name="🎯 Pokušaji", value=f"`{attempts}`", inline=True)
    embed.set_footer(text="SQUAD Bot • Klikni i pogodi objekat!")
    return embed

class _ObjModal(discord.ui.Modal, title="Pogodi objekat!"):
    answer = discord.ui.TextInput(label="Šta je ovaj objekat?", placeholder="Unesi odgovor...", min_length=1, max_length=30)
    def __init__(self, view):
        super().__init__(); self.game_view = view
    async def on_submit(self, interaction: discord.Interaction):
        v = self.game_view; guess = self.answer.value.strip().lower(); correct = v.puzzle["answer"].lower(); v.attempts += 1
        if guess == correct or correct in guess or guess in correct:
            v.winner = interaction.user.id; v.active = False; v.disable_all()
            await interaction.response.edit_message(embed=_obj_embed(v.puzzle, v.clues_shown, v.attempts, winner=v.winner), view=v)
        else:
            if v.clues_shown < len(v.puzzle["clues"]): v.clues_shown += 1
            await interaction.response.send_message(f"❌ Nije **{guess}**! Otkrio/la sam ti novi trag.", ephemeral=True)
            if v.message: await v.message.edit(embed=_obj_embed(v.puzzle, v.clues_shown, v.attempts), view=v)

class _ObjView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.puzzle = random.choice(_OBJECTS); self.clues_shown = 1
        self.attempts = 0; self.winner = None; self.gave_up = False; self.active = True; self.message = None
    def disable_all(self):
        for item in self.children: item.disabled = True
    @discord.ui.button(label="🔍 Pogodi", style=discord.ButtonStyle.primary)
    async def guess_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.active:
            await interaction.response.send_message("❌ Igra je gotova!", ephemeral=True); return
        await interaction.response.send_modal(_ObjModal(self))
    @discord.ui.button(label="💡 Još jedan trag", style=discord.ButtonStyle.secondary)
    async def hint_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.active:
            await interaction.response.send_message("❌ Igra je gotova!", ephemeral=True); return
        if self.clues_shown < len(self.puzzle["clues"]): self.clues_shown += 1
        await interaction.response.edit_message(embed=_obj_embed(self.puzzle, self.clues_shown, self.attempts), view=self)

class PogodiObjekat:
    name = "Pogodi Objekat"; emoji = "🔍"
    @staticmethod
    async def start(channel):
        view = _ObjView()
        msg = await channel.send(embed=_obj_embed(view.puzzle, view.clues_shown, 0), view=view)
        view.message = msg; return view, msg
    @staticmethod
    async def stop(view, message):
        if not view.active: return
        view.active = False; view.gave_up = True; view.disable_all()
        await message.edit(embed=_obj_embed(view.puzzle, view.clues_shown, view.attempts, gave_up=True), view=view)

# ============================================================
# IGRA 5: GREBALICA
# ============================================================

_SYMBOLS = ["💎","🍒","⭐","🍋","🔔","🍀","🎰","💰","🌈"]

def _scratch():
    roll = random.random()
    if roll < 0.05:
        s = random.choice(_SYMBOLS); symbols = [s]*9; prize = "🎉 JACKPOT! Tri iste posvuda!"; emoji = "🏆"
    elif roll < 0.25:
        s = random.choice(_SYMBOLS); pool = [x for x in _SYMBOLS if x != s]
        row = [s,s,s]; rest = random.sample(pool, 6); symbols = row + rest; random.shuffle(symbols)
        prize = "🎊 Mala pobjeda! Jedan red!"; emoji = "✨"
    elif roll < 0.45:
        s = random.choice(_SYMBOLS); pool = [x for x in _SYMBOLS if x != s]
        symbols = [s,s] + random.sample(pool, 7); random.shuffle(symbols)
        prize = "😅 Skoro! Samo još jedan..."; emoji = "😬"
    else:
        symbols = random.sample(_SYMBOLS, 9); prize = "💨 Nema sreće ovaj put!"; emoji = "😢"
    return symbols, prize, emoji

def _greb_embed(total_plays, recent):
    recent_text = "\n".join(f"<@{uid}>: {res['prize_emoji']} {res['prize']}" for uid, res in list(recent.items())[-5:]) if recent else "Nitko još nije igrao!"
    embed = discord.Embed(title="🎰 Grebalica", description="Klikni **Grebi!** da otkriješ svoju tablicu! Poklopi tri iste i osvoji nagradu!", color=discord.Color.gold())
    embed.add_field(name="🎟️ Ukupno odigranih", value=f"`{total_plays}`", inline=True)
    embed.add_field(name="📊 Nedavni rezultati", value=recent_text, inline=False)
    embed.set_footer(text="SQUAD Bot • Sretno na Grebalici!")
    return embed

class _GrebView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.total_plays = 0; self.recent = {}; self.active = True; self.message = None
    def disable_all(self):
        for item in self.children: item.disabled = True
    @discord.ui.button(label="🎰 Grebi!", style=discord.ButtonStyle.primary)
    async def scratch_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.active:
            await interaction.response.send_message("❌ Igra je gotova!", ephemeral=True); return
        symbols, prize, prize_emoji = _scratch()
        self.total_plays += 1; self.recent[interaction.user.id] = {"prize": prize, "prize_emoji": prize_emoji}
        grid = "\n".join(" ".join(symbols[i*3:(i+1)*3]) for i in range(3))
        await interaction.response.send_message(f"🎰 **Tvoja Grebalica:**\n\n{grid}\n\n{prize_emoji} {prize}", ephemeral=True)
        if self.message: await self.message.edit(embed=_greb_embed(self.total_plays, self.recent), view=self)

class Grebalica:
    name = "Grebalica"; emoji = "🎰"
    @staticmethod
    async def start(channel):
        view = _GrebView()
        msg = await channel.send(embed=_greb_embed(0, {}), view=view)
        view.message = msg; return view, msg
    @staticmethod
    async def stop(view, message):
        view.active = False; view.disable_all()
        await message.edit(embed=_greb_embed(view.total_plays, view.recent), view=view)

# ============================================================
# GAME MANAGER
# ============================================================

GAMES = [ToploHladnoGame, BingoGame, PogodiRijec, PogodiObjekat, Grebalica]

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
        try: await current_game_cls.stop(current_view, current_message)
        except Exception as e: log.error(f"Greška pri zaustavljanju igre: {e}")
    current_view = None; current_message = None; current_game_cls = None

async def start_next_game(channel):
    global current_view, current_message, current_game_cls, game_index
    await stop_current_game()
    game_cls = GAMES[game_index % len(GAMES)]; game_index += 1
    log.info(f"Pokrećem igru: {game_cls.emoji} {game_cls.name}")
    await channel.send(f"{game_cls.emoji} **Sljedeća igra za 5 sekundi: {game_cls.name}!** Budite spremni!")
    await asyncio.sleep(5)
    view, msg = await game_cls.start(channel)
    current_view = view; current_message = msg; current_game_cls = game_cls

async def game_loop(channel):
    while True:
        try: await start_next_game(channel)
        except Exception as e: log.error(f"Greška pri pokretanju igre: {e}")
        await asyncio.sleep(GAME_INTERVAL)

@bot.event
async def on_ready():
    log.info(f"✅ Bot je online: {bot.user}")
    channel = bot.get_channel(CHANNEL_ID)
    if channel is None:
        try: channel = await bot.fetch_channel(CHANNEL_ID)
        except Exception: channel = None
    if not isinstance(channel, discord.TextChannel):
        log.error(f"❌ Kanal {CHANNEL_ID} nije pronađen ili nije tekstualni!"); return
    await channel.send("🤖 **SQUAD Bot je online!**\nIgre počinju svakih **15 minuta**! 🎮")
    log.info(f"🎮 Game loop pokrenut u #{channel.name}")
    bot.loop.create_task(game_loop(channel))

bot.run(TOKEN, log_handler=None)
