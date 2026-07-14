"""
🎰 Squad Lutrija Bot — Python Edition
discord.py 2.x | SQLite | Slash + Prefix komande
"""

import discord
from discord.ext import commands, tasks
from discord import app_commands
import sqlite3
import random
import asyncio
import os
import time
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

# ── CONFIG ─────────────────────────────────────────────────────────────────────
TOKEN              = os.getenv("DISCORD_TOKEN", "")
GUILD_ID           = int(os.getenv("DISCORD_GUILD_ID", "0") or 0)
GAME_CHANNEL_ID    = int(os.getenv("DISCORD_CHANNEL_ID", "0") or 0)
BAN_CHANNEL_ID     = int(os.getenv("DISCORD_BAN_CHANNEL_ID", "0") or 0)
ANTI_BAN_ROLE_ID   = int(os.getenv("DISCORD_ANTI_BAN_ROLE_ID", "0") or 0)
OWNER_ID           = int(os.getenv("DISCORD_OWNER_ID", "0") or 0)
PREFIX             = "."
BOT_NAME           = "Squad Lutrija"
BOT_VERSION        = "v5.0"
ANTI_BAN_THRESHOLD = 5
DAILY_AMOUNT       = 200
STREAK_BONUS_STEP  = 20   # + po danu niza, do maksimuma ispod
STREAK_BONUS_CAP   = 10   # maksimalno dana koja se računaju u bonus
START_NOVAC        = 500
GAME_INTERVAL      = 5    # minuta — igre idu redom, jedna po jedna

# ── BOJE (rosa akcent na svim standardnim embedima) ─────────────────────────────
COLOR_DEFAULT = 0xFF4FA3   # rosa — glavna boja svih "neutralnih" embeda
COLOR_WIN     = 0x57F287   # zeleno — ostaje jasan signal za pobjedu
COLOR_LOSE    = 0xED4245   # crveno — ostaje jasan signal za gubitak
COLOR_BAN     = 0xFF2D6F   # rosa-crvena — ban obavijesti
COLOR_WARN    = 0xFF8C00

# ── DATABASE ───────────────────────────────────────────────────────────────────
DB_PATH = "squad_lutrija.db"

def db_connect():
    return sqlite3.connect(DB_PATH)

def db_init():
    conn = db_connect()
    c = conn.cursor()
    c.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            discord_id TEXT PRIMARY KEY,
            username   TEXT NOT NULL,
            novac      INTEGER DEFAULT 500,
            total_games INTEGER DEFAULT 0,
            total_wins  INTEGER DEFAULT 0,
            last_daily  INTEGER DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS bans (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id       TEXT NOT NULL,
            username      TEXT NOT NULL,
            moderator_id  TEXT NOT NULL,
            moderator_name TEXT NOT NULL,
            reason        TEXT DEFAULT 'Nije naveden razlog',
            active        INTEGER DEFAULT 1,
            guild_id      TEXT NOT NULL,
            created_at    INTEGER NOT NULL,
            removed_at    INTEGER,
            removed_by_id TEXT
        );
        CREATE TABLE IF NOT EXISTS games_log (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            discord_id TEXT NOT NULL,
            username   TEXT NOT NULL,
            game_name  TEXT NOT NULL,
            result     TEXT NOT NULL,
            amount     INTEGER DEFAULT 0,
            created_at INTEGER NOT NULL
        );
        CREATE TABLE IF NOT EXISTS bot_state (
            key   TEXT PRIMARY KEY,
            value TEXT
        );
    """)
    # Migracija: dodaj "streak" kolonu ako baza postoji od prije
    c.execute("PRAGMA table_info(users)")
    cols = [r[1] for r in c.fetchall()]
    if "streak" not in cols:
        c.execute("ALTER TABLE users ADD COLUMN streak INTEGER DEFAULT 0")
    conn.commit()
    conn.close()

def get_user(discord_id: str, username: str) -> dict:
    conn = db_connect()
    c = conn.cursor()
    c.execute("SELECT discord_id,username,novac,total_games,total_wins,last_daily,streak FROM users WHERE discord_id=?", (discord_id,))
    row = c.fetchone()
    if not row:
        c.execute(
            "INSERT INTO users (discord_id, username, novac) VALUES (?,?,?)",
            (discord_id, username, START_NOVAC),
        )
        conn.commit()
        c.execute("SELECT discord_id,username,novac,total_games,total_wins,last_daily,streak FROM users WHERE discord_id=?", (discord_id,))
        row = c.fetchone()
    else:
        c.execute("UPDATE users SET username=? WHERE discord_id=?", (username, discord_id))
        conn.commit()
    conn.close()
    return {"discord_id": row[0], "username": row[1], "novac": row[2],
            "total_games": row[3], "total_wins": row[4], "last_daily": row[5],
            "streak": row[6] or 0}

def add_novac(discord_id: str, amount: int) -> int:
    conn = db_connect()
    c = conn.cursor()
    c.execute(
        "UPDATE users SET novac = MAX(0, novac + ?) WHERE discord_id=?",
        (amount, discord_id),
    )
    conn.commit()
    c.execute("SELECT novac FROM users WHERE discord_id=?", (discord_id,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else 0

def record_game(discord_id: str, username: str, game: str, result: str, amount: int):
    conn = db_connect()
    c = conn.cursor()
    win_inc = 1 if result == "win" else 0
    c.execute(
        "UPDATE users SET total_games=total_games+1, total_wins=total_wins+? WHERE discord_id=?",
        (win_inc, discord_id),
    )
    c.execute(
        "INSERT INTO games_log (discord_id,username,game_name,result,amount,created_at) VALUES (?,?,?,?,?,?)",
        (discord_id, username, game, result, amount, int(time.time())),
    )
    conn.commit()
    conn.close()

def get_top_users(limit=10):
    conn = db_connect()
    c = conn.cursor()
    c.execute("SELECT username, novac, total_wins FROM users ORDER BY novac DESC LIMIT ?", (limit,))
    rows = c.fetchall()
    conn.close()
    return rows

def add_ban(user_id, username, mod_id, mod_name, reason, guild_id) -> int:
    conn = db_connect()
    c = conn.cursor()
    c.execute(
        "INSERT INTO bans (user_id,username,moderator_id,moderator_name,reason,guild_id,created_at) VALUES (?,?,?,?,?,?,?)",
        (user_id, username, mod_id, mod_name, reason, guild_id, int(time.time())),
    )
    conn.commit()
    c.execute("SELECT COUNT(*) FROM bans WHERE user_id=?", (user_id,))
    count = c.fetchone()[0]
    conn.close()
    return count

def remove_ban(user_id, mod_id) -> bool:
    conn = db_connect()
    c = conn.cursor()
    c.execute("SELECT id FROM bans WHERE user_id=? AND active=1 LIMIT 1", (user_id,))
    row = c.fetchone()
    if not row:
        conn.close()
        return False
    c.execute(
        "UPDATE bans SET active=0, removed_at=?, removed_by_id=? WHERE id=?",
        (int(time.time()), mod_id, row[0]),
    )
    conn.commit()
    conn.close()
    return True

def get_active_bans():
    conn = db_connect()
    c = conn.cursor()
    c.execute("SELECT user_id,username,moderator_name,reason,created_at FROM bans WHERE active=1 ORDER BY created_at DESC")
    rows = c.fetchall()
    conn.close()
    return rows

def get_user_bans(user_id):
    conn = db_connect()
    c = conn.cursor()
    c.execute("SELECT reason,active,created_at FROM bans WHERE user_id=? ORDER BY created_at DESC", (user_id,))
    rows = c.fetchall()
    conn.close()
    return rows

def get_next_game_index() -> int:
    """Igre idu redom (1 po 1), redoslijed se pamti u bazi pa preživi i restart bota."""
    conn = db_connect()
    c = conn.cursor()
    c.execute("SELECT value FROM bot_state WHERE key='game_index'")
    row = c.fetchone()
    idx = (int(row[0]) if row else 0) % len(GAMES)
    next_idx = (idx + 1) % len(GAMES)
    c.execute(
        "INSERT INTO bot_state (key,value) VALUES ('game_index',?) "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (str(next_idx),),
    )
    conn.commit()
    conn.close()
    return idx

# ── HELPERI ────────────────────────────────────────────────────────────────────

def fmt(n) -> str:
    """Formatira novac sa tačkom kao razdjelnikom hiljada (1.234.500)."""
    return f"{int(n):,}".replace(",", ".")

def rank_title(novac: int) -> str:
    if novac >= 20000: return "👑 Legenda"
    if novac >= 10000: return "💎 Majstor"
    if novac >= 5000:  return "🥇 Profesionalac"
    if novac >= 2000:  return "🥈 Napredni Igrač"
    if novac >= 500:   return "🥉 Igrač"
    return "🌱 Početnik"

def bingo_letter(n: int) -> str:
    if n <= 15: return "B"
    if n <= 30: return "I"
    if n <= 45: return "N"
    if n <= 60: return "G"
    return "O"

def uname(user) -> str:
    return getattr(user, "display_name", None) or user.name

def quote(lines) -> str:
    """Prefiksira svaku liniju sa '> ' da Discord nacrta vertikalnu crtu (blockquote) pored teksta.
    Linije koje su već heading markdown (#, -#) se ne diraju da ne pokvare veliki naslov."""
    if isinstance(lines, str):
        lines = lines.split("\n")
    out = []
    for l in lines:
        if not l or l.startswith("#") or l.startswith("-#") or l.startswith("> "):
            # već quotovano (ili heading/prazna linija) — ne duplira prefiks
            out.append(l)
        else:
            out.append(f"> {l}")
    return "\n".join(out)

# ── UNIFIED EMBED TEMPLATE (isti "look" za bukvalno sve embede u botu) ─────────
# Struktura kopira dogovoreni format:
#   Title:  "{emoji} Pokrenuo/la: {korisnik}"
#   Desc:   veliki naslov (# 🎯 💎 I M E   I G R E 💎 🎯) + bullet lista info (sa vertikalnom crtom)
#   Fields: dodatne info / nagradna lista (i one sa vertikalnom crtom)
#   Footer: "{emoji} x Squad Lutrija {Igra} • Ulog: X novca • danas u HH:MM"

def big_heading(emoji: str, name: str) -> str:
    # Samo JEDAN emoji u naslovu (bez dupliranja na oba kraja, bez 💎💎),
    # plus dekorativni "゛" prefiks ispred imena igre.
    return f"{emoji} ゛{name}"

def make_embed(user, emoji: str, name: str, bullets, fields=None, color=COLOR_DEFAULT,
                bet=None, footer_hint=None, heading=True):
    now = datetime.now().strftime("%H:%M")
    started_by = uname(user) if user is not None else None
    title = f"{emoji} Pokrenuo/la: {started_by}" if started_by else f"{emoji} {name}"
    embed = discord.Embed(title=title, color=color)
    parts = []
    if heading:
        parts.append(f"### {big_heading(emoji, name)}")
    # Bullet linije idu sa "> " ispred — Discord to renderuje kao vertikalnu crtu pored teksta
    parts.append(quote(bullets or []))
    embed.description = "\n".join(parts)
    for f in (fields or []):
        # quote() je idempotentan — automatski dodaje istu vertikalnu crtu i na
        # fields kao i na description, bez obzira da li je vrijednost već quotovana
        embed.add_field(name=f["name"], value=quote(f["value"]), inline=f.get("inline", True))
    footer_parts = [f"{emoji} x {BOT_NAME} {name}"]
    if bet is not None:
        footer_parts.append(f"Ulog: {fmt(bet)} novca")
    if footer_hint:
        footer_parts.append(footer_hint)
    footer_parts.append(f"danas u {now}")
    embed.set_footer(text=" • ".join(footer_parts))
    return embed

# ── GAME VIEWS ─────────────────────────────────────────────────────────────────

# ── 1. GREBALICE ───────────────────────────────────────────────────────────────
SYMBOLS = ["🍒","🍋","🍊","⭐","💎","7️⃣","🔔","🍀","❓"]

class GrebaliceView(discord.ui.View):
    EMOJI = "🎰"; NAME = "Grebalice"

    def __init__(self, user: discord.User, bet: int):
        super().__init__(timeout=120)
        self.user  = user
        self.bet   = bet
        self.grid  = random.sample(SYMBOLS, 9)
        self.revealed = [False] * 9
        self.picks = 0
        self._add_buttons()

    def _grid_str(self):
        return "".join((self.grid[i] if self.revealed[i] else "🟫") + (" " if (i+1) % 3 else "\n") for i in range(9))

    def initial_embed(self):
        return make_embed(self.user, self.EMOJI, self.NAME,
            ["🎯 Klikni polje i grebi 3 od 9!",
             "🪙 Uloženo je već skinuto sa računa.",
             "🏆 3 iste = veliki dobitak, 2 iste = mali dobitak."],
            fields=[{"name":"🎯 Preostalo","value":"**3** polja","inline":True},
                    {"name":"🃏 Tabla","value":self._grid_str(),"inline":False}],
            bet=self.bet, footer_hint="Grebi 3 polja!")

    def _add_buttons(self):
        self.clear_items()
        for i in range(9):
            btn = discord.ui.Button(
                label="\u200b",
                emoji=self.grid[i] if self.revealed[i] else "🟫",
                style=discord.ButtonStyle.secondary if self.revealed[i] else discord.ButtonStyle.primary,
                custom_id=f"g_{i}",
                row=i // 3,
                disabled=self.revealed[i],
            )
            btn.callback = self._make_cb(i)
            self.add_item(btn)
        cancel = discord.ui.Button(label="Odustani", emoji="❌",
                                   style=discord.ButtonStyle.danger, custom_id="cancel", row=3)
        cancel.callback = self._cancel
        self.add_item(cancel)

    def _make_cb(self, idx):
        async def callback(interaction: discord.Interaction):
            if interaction.user.id != self.user.id:
                return await interaction.response.send_message("❌ Ovo nije tvoja igra!", ephemeral=True)
            self.revealed[idx] = True
            self.picks += 1
            done = self.picks >= 3
            color = COLOR_DEFAULT
            bullets = [f"🎯 Otkriveno polje {idx+1} → {self.grid[idx]}"]
            if done:
                counts = {}
                for i, r in enumerate(self.revealed):
                    if r:
                        counts[self.grid[i]] = counts.get(self.grid[i], 0) + 1
                max_c = max(counts.values())
                top_s = [s for s,v in counts.items() if v == max_c][0]
                if max_c >= 3:
                    mult = {"💎":10,"7️⃣":7,"⭐":5,"🍀":4}.get(top_s, 3)
                    earned = int(self.bet * mult)
                    net = earned - self.bet
                    add_novac(str(self.user.id), net)
                    record_game(str(self.user.id), self.user.name, "Grebalice", "win", net)
                    bullets.append(f"🏆 WIN {top_s}{top_s}{top_s}! +**{fmt(net)}** novca!")
                    color = COLOR_WIN
                elif max_c == 2:
                    earned = int(self.bet * 1.5)
                    net = earned - self.bet
                    add_novac(str(self.user.id), net)
                    record_game(str(self.user.id), self.user.name, "Grebalice", "win", net)
                    bullets.append(f"🎉 Mali win! +**{fmt(net)}** novca!")
                    color = COLOR_WIN
                else:
                    record_game(str(self.user.id), self.user.name, "Grebalice", "lose", -self.bet)
                    bullets.append(f"😔 Nema sreće. Gubitak **{fmt(self.bet)}** novca.")
                    color = COLOR_LOSE
                for item in self.children:
                    item.disabled = True
                self.stop()
            self._add_buttons()
            embed = make_embed(self.user, self.EMOJI, self.NAME, bullets,
                fields=[{"name":"🎯 Preostalo","value":f"**{3-self.picks}** polja","inline":True},
                        {"name":"🃏 Tabla","value":self._grid_str(),"inline":False}],
                color=color, bet=self.bet, footer_hint="Grebi 3 polja!")
            await interaction.response.edit_message(embed=embed, view=self if not done else None)
        return callback

    async def _cancel(self, interaction: discord.Interaction):
        if interaction.user.id != self.user.id:
            return await interaction.response.send_message("❌ Nije tvoja igra!", ephemeral=True)
        for item in self.children: item.disabled = True
        self.stop()
        embed = make_embed(self.user, self.EMOJI, self.NAME, ["❌ Igra otkazana."], color=COLOR_LOSE, bet=self.bet)
        await interaction.response.edit_message(embed=embed, view=None)

# ── 2. KOLO SREĆE (stvarno se vrti prije nego što otkrije rezultat) ────────────
WHEEL = [
    ("💀 BANKROT", 0, 8),("×0.5 Mali Gubitak", 0.5, 12),("×1 Vratilo Se", 1, 20),
    ("×1.5 Sitni Dobitak", 1.5, 20),("×2 Duplo", 2, 18),("×3 Trostruko", 3, 12),
    ("×5 SUPER WIN", 5, 7),("×10 JACKPOT", 10, 3),
]
WHEEL_ICONS = ["💀","📉","🔁","🎈","✨","🔥","💰","👑"]

def spin_wheel():
    total = sum(w[2] for w in WHEEL)
    r = random.randint(1, total)
    for seg in WHEEL:
        r -= seg[2]
        if r <= 0:
            return seg
    return WHEEL[2]

class KoloView(discord.ui.View):
    EMOJI = "🎡"; NAME = "Kolo Srece"

    def __init__(self, user, bet):
        super().__init__(timeout=60)
        self.user = user
        self.bet  = bet

    def initial_embed(self):
        seg_list = quote(f"{WHEEL_ICONS[i]} {s[0]}" for i, s in enumerate(WHEEL))
        return make_embed(self.user, self.EMOJI, self.NAME,
            ["🎯 Klikni **Zavrti Kolo** i kolo se stvarno vrti!",
             "🪙 Ulog je već skinut sa računa.",
             "⏳ Sačekaj da se kolo zaustavi na svom polju."],
            fields=[{"name":"🎡 Segmenti","value":seg_list,"inline":False}],
            bet=self.bet, footer_hint="Zavrti kolo!")

    @discord.ui.button(label="Zavrti Kolo", emoji="🎡", style=discord.ButtonStyle.success)
    async def spin(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user.id:
            return await interaction.response.send_message("❌ Nije tvoja igra!", ephemeral=True)
        button.disabled = True
        seg = spin_wheel()
        label, mult, _ = seg

        # ── Animacija vrtnje: kolo prolazi kroz par nasumičnih polja pa se zaustavi ──
        spin_frames = [random.choice(WHEEL) for _ in range(4)] + [seg]
        for i, frame in enumerate(spin_frames):
            f_label = frame[0]
            f_icon  = WHEEL_ICONS[WHEEL.index(frame)]
            slowing = "🌀" if i < len(spin_frames) - 1 else "🛑"
            embed = make_embed(self.user, self.EMOJI, self.NAME,
                [f"{slowing} Kolo se vrti...", f"{f_icon} *{f_label}*"],
                fields=[{"name":"🎡 Status","value":"Vrti se..." if i < len(spin_frames)-1 else "Zaustavljeno!","inline":True}],
                bet=self.bet, footer_hint="Vrti se!")
            if i == 0:
                await interaction.response.edit_message(embed=embed, view=self)
            else:
                await asyncio.sleep(0.7)
                await interaction.edit_original_response(embed=embed, view=self)
        await asyncio.sleep(0.5)

        earned = int(self.bet * mult)
        net = earned - self.bet
        color = COLOR_WIN if net > 0 else COLOR_LOSE if net < 0 else COLOR_DEFAULT
        if net != 0:
            add_novac(str(self.user.id), net)
        result = "win" if net > 0 else "lose" if net < 0 else "draw"
        record_game(str(self.user.id), self.user.name, "Kolo Sreće", result, net)
        msg = f"💰 +**{fmt(net)}** novca!" if net > 0 else (f"💸 -**{fmt(abs(net))}** novca." if net < 0 else "🤝 Vraćen ulog.")
        self.stop()
        embed = make_embed(self.user, self.EMOJI, self.NAME,
            [f"🎡 Kolo se zaustavilo na: **{label}**", msg],
            bet=self.bet, color=color, footer_hint="Zavrtjeno!")
        await interaction.edit_original_response(embed=embed, view=None)

# ── 3. PITANJE ─────────────────────────────────────────────────────────────────
QUESTIONS = [
    ("Koji grad je glavni grad Bosne i Hercegovine?",["Sarajevo","Banja Luka","Mostar","Tuzla"],0),
    ("Koliko ima planeta u Sunčevom sistemu?",["7","8","9","10"],1),
    ("Ko je napisao 'Romeo i Julija'?",["Goethe","Molière","Shakespeare","Dante"],2),
    ("Koja je najduža rijeka na svijetu?",["Amazon","Nil","Yangtze","Mississippi"],1),
    ("Koja država ima najveću površinu?",["Kina","SAD","Rusija","Kanada"],2),
    ("Hemijska oznaka za zlato?",["Zl","Go","Au","Ag"],2),
    ("Koliko minuta ima u 3 sata?",["150","180","200","120"],1),
    ("Koja životinja ima 8 srca?",["Hobotnica","Lignja","Morski konjić","Meduza"],0),
    ("Koji element ima atomski broj 1?",["Helij","Kisik","Vodik","Ugljik"],2),
    ("Kada je počeo Drugi svjetski rat?",["1937","1939","1941","1935"],1),
    ("Koja je najveća planeta Sunčevog sistema?",["Saturn","Neptun","Jupiter","Uran"],2),
    ("Ko je izumio telefon?",["Edison","Tesla","Bell","Marconi"],2),
    ("Koji sport se igra na Wimbledonu?",["Golf","Kriket","Tenis","Fudbal"],2),
    ("Koliko kontinenata ima na Zemlji?",["5","6","7","8"],2),
    ("Koja je najbrža kopnena životinja?",["Gepard","Lav","Antilopa","Konj"],0),
]

class PitanjeView(discord.ui.View):
    EMOJI = "❓"; NAME = "Pitanje"

    def __init__(self, user, bet):
        super().__init__(timeout=60)
        self.user = user
        self.bet  = bet
        q = random.choice(QUESTIONS)
        self.question, opts, correct_idx = q
        indexed = list(enumerate(opts))
        random.shuffle(indexed)
        self.options = [o for _, o in indexed]
        self.correct = next(i for i, (old_i, _) in enumerate(indexed) if old_i == correct_idx)
        labels = ["A","B","C","D"]
        for i, opt in enumerate(self.options):
            btn = discord.ui.Button(label=f"{labels[i]}: {opt[:40]}", style=discord.ButtonStyle.primary, row=0)
            btn.callback = self._make_cb(i)
            self.add_item(btn)

    def initial_embed(self):
        return make_embed(self.user, self.EMOJI, self.NAME,
            [f"🤔 **{self.question}**", "🎯 Klikni tačan odgovor ispod!"],
            bet=self.bet, footer_hint="Odgovori tačno!")

    def _make_cb(self, idx):
        async def callback(interaction: discord.Interaction):
            if interaction.user.id != self.user.id:
                return await interaction.response.send_message("❌ Nije tvoja igra!", ephemeral=True)
            correct = idx == self.correct
            net = self.bet if correct else -self.bet
            add_novac(str(self.user.id), net)
            record_game(str(self.user.id), self.user.name, "Pitanje", "win" if correct else "lose", net)
            for item in self.children: item.disabled = True
            self.stop()
            bullets = [
                f"🤔 **{self.question}**",
                f"🎯 Odabrano: **{self.options[idx]}**",
                f"✅ TAČNO! +**{fmt(self.bet)}** novca! 🎉" if correct else f"❌ Netačno! Tačan: **{self.options[self.correct]}**",
            ]
            embed = make_embed(self.user, self.EMOJI, self.NAME, bullets,
                bet=self.bet, color=COLOR_WIN if correct else COLOR_LOSE)
            await interaction.response.edit_message(embed=embed, view=None)
        return callback

# ── 4. NASTAVI PJESMU (tekst pjesme se vidi odmah, ogromno, i mora se pogoditi nastavak) ─
SONGS = [
    ("Dino Merlin","Ima jedna tajna...","u srcu mom",["što te voli","da ti kažem","moja ljubavi"]),
    ("Halid Bešlić","Jedina...","ti si mi jedina",["u mom životu","ljubavi moja","zvijezdo moja"]),
    ("Zdravko Čolić","Pusti me, pusti me...","da živim slobodno",["da odem od tebe","da pjevam za tebe","jer ja sam tvoj"]),
    ("Indexi","Plavi, plavi...","Jadran moj",["talasi","horizonti","vjetriću"]),
    ("Bijelo Dugme","Hop, hop, hop...","idi kući pop",["igraj se","pjevaj nam","skoči sad"]),
    ("Kemal Monteno","Sarajevo, ljubavi moja...","ko te prežali može",["ti si moj grad","ostani uz mene","nikad te ne zaboravim"]),
    ("Ceca","Kukavica...","sam ja bila",["ne plači","za tobom","moj živote"]),
    ("Massimo","Cijeli grad...","o nama priča",["zna za nas","čuje nas","vidi nas"]),
]

class NastaviView(discord.ui.View):
    EMOJI = "🎵"; NAME = "Nastavi Pjesmu"

    def __init__(self, user, bet):
        super().__init__(timeout=60)
        self.user = user
        self.bet  = bet
        song = random.choice(SONGS)
        self.artist, self.line, self.missing, wrongs = song
        options = [self.missing] + wrongs[:3]
        random.shuffle(options)
        self.options  = options
        self.correct_idx = options.index(self.missing)
        for i, opt in enumerate(options):
            btn = discord.ui.Button(label=opt[:40], style=discord.ButtonStyle.primary, row=0)
            btn.callback = self._make_cb(i)
            self.add_item(btn)

    def _lyric_block(self, reveal=False):
        line = f"„{self.line} {self.missing if reveal else '____'}“"
        return [f"### 🎵 {line}", f"-# 🎤 {self.artist}"]

    def initial_embed(self):
        return make_embed(self.user, self.EMOJI, self.NAME,
            self._lyric_block(reveal=False) + ["🎯 Pogodi kojim se riječima nastavlja pjesma!"],
            bet=self.bet, footer_hint="Pogodi nastavak!", heading=False)

    def _make_cb(self, idx):
        async def callback(interaction: discord.Interaction):
            if interaction.user.id != self.user.id:
                return await interaction.response.send_message("❌ Nije tvoja igra!", ephemeral=True)
            correct = idx == self.correct_idx
            net = self.bet if correct else -self.bet
            add_novac(str(self.user.id), net)
            record_game(str(self.user.id), self.user.name, "Nastavi Pjesmu", "win" if correct else "lose", net)
            for item in self.children: item.disabled = True
            self.stop()
            bullets = self._lyric_block(reveal=True) + [
                f"🎯 Odabrano: **\"{self.options[idx]}\"**",
                f"✅ TAČNO! +**{fmt(self.bet)}** novca! 🎉" if correct else f"❌ Netačno! Tačan nastavak: **\"{self.missing}\"**"]
            embed = make_embed(self.user, self.EMOJI, self.NAME, bullets,
                bet=self.bet, color=COLOR_WIN if correct else COLOR_LOSE, heading=False)
            await interaction.response.edit_message(embed=embed, view=None)
        return callback

# ── 5. POGODI OBLIK ────────────────────────────────────────────────────────────
SHAPES = [
    ("Ima 4 jednake stranice i 4 prava ugla.","Kvadrat","🟦",[("Pravougaonik","🟥"),("Romb","🔷"),("Trapez","🔺")]),
    ("Sve tačke jednako udaljene od centra. Nema stranica.","Krug","⭕",[("Elipsa","🫧"),("Oval","🥚"),("Polukrug","🌙")]),
    ("Ima 3 stranice i 3 ugla. Suma uglova je 180°.","Trougao","🔺",[("Kvadrat","🟦"),("Pentagon","⭐"),("Šestougao","⬡")]),
    ("Ima 8 jednakih stranica. Viđa se na saobraćajnim znacima.","Oktogon","🛑",[("Šestougao","⬡"),("Pentagon","⭐"),("Kvadrat","🟦")]),
    ("Ima 5 stranica i 5 uglova.","Pentagon","⭐",[("Šestougao","⬡"),("Oktogon","🛑"),("Heptagon","🔷")]),
    ("Trodimenzionalni oblik sa kružnom bazom i jednom tačkom na vrhu.","Konus","🔺",[("Piramida","🏛️"),("Cilindar","🥫"),("Sfera","🌐")]),
]

class OblikView(discord.ui.View):
    EMOJI = "🔷"; NAME = "Pogodi Oblik"

    def __init__(self, user, bet):
        super().__init__(timeout=60)
        self.user = user
        self.bet  = bet
        shape = random.choice(SHAPES)
        self.desc, self.answer, self.emoji, wrongs = shape
        opts = [(self.answer, self.emoji)] + wrongs[:3]
        random.shuffle(opts)
        self.opts = opts
        self.correct_idx = next(i for i,(n,_) in enumerate(opts) if n == self.answer)
        for i, (name, em) in enumerate(opts):
            btn = discord.ui.Button(label=name, emoji=em, style=discord.ButtonStyle.primary, row=0)
            btn.callback = self._make_cb(i)
            self.add_item(btn)

    def initial_embed(self):
        return make_embed(self.user, self.EMOJI, self.NAME,
            [f"🔍 *{self.desc}*", "🎯 Prepoznaj oblik i klikni odgovor!"],
            bet=self.bet, footer_hint="Pogodi oblik!")

    def _make_cb(self, idx):
        async def callback(interaction: discord.Interaction):
            if interaction.user.id != self.user.id:
                return await interaction.response.send_message("❌ Nije tvoja igra!", ephemeral=True)
            correct = idx == self.correct_idx
            net = self.bet if correct else -self.bet
            add_novac(str(self.user.id), net)
            record_game(str(self.user.id), self.user.name, "Pogodi Oblik", "win" if correct else "lose", net)
            for item in self.children: item.disabled = True
            self.stop()
            n, em = self.opts[idx]
            bullets = [f"🔍 *{self.desc}*",
                       f"🎯 Odabrano: **{em} {n}**",
                       f"✅ TAČNO! +**{fmt(self.bet)}** novca!" if correct else f"❌ Netačno! Tačan: **{self.emoji} {self.answer}**"]
            embed = make_embed(self.user, self.EMOJI, self.NAME, bullets,
                bet=self.bet, color=COLOR_WIN if correct else COLOR_LOSE)
            await interaction.response.edit_message(embed=embed, view=None)
        return callback

# ── 6. MINSKO POLJE ────────────────────────────────────────────────────────────
MINE_MULTIPLIERS = [1.1,1.3,1.5,1.8,2.2,2.7,3.3,4.0,5.0,6.5,8.0,10.0]

class MinskoView(discord.ui.View):
    EMOJI = "💣"; NAME = "Minsko Polje"

    def __init__(self, user, bet):
        super().__init__(timeout=180)
        self.user  = user
        self.bet   = bet
        self.mines = set(random.sample(range(16), 4))
        self.revealed = set()
        self.safe_picked = 0
        self._build()

    def _mult(self): return MINE_MULTIPLIERS[min(self.safe_picked, len(MINE_MULTIPLIERS)-1)]

    def initial_embed(self):
        return make_embed(self.user, self.EMOJI, self.NAME,
            ["🎯 Otkrivaj polja — izbjegavaj mine!", "📈 Svako sigurno polje diže multiplikator."],
            fields=[{"name":"✅ Sigurnih","value":"**0**","inline":True},
                    {"name":"📈 Trenutno","value":f"×{self._mult()} = **{fmt(self.bet)}** novca","inline":True}],
            bet=self.bet, footer_hint="Otkrivaj oprezno!")

    def _build(self):
        self.clear_items()
        for i in range(16):
            em = "✅" if i in self.revealed else ("💥" if (i in self.mines and self.safe_picked < 0) else "⬛")
            btn = discord.ui.Button(emoji=em, label="\u200b", style=discord.ButtonStyle.secondary,
                                    custom_id=f"m_{i}", row=i//4, disabled=i in self.revealed)
            btn.callback = self._make_cb(i)
            self.add_item(btn)
        mult = self._mult()
        cur = int(self.bet * mult)
        cashout = discord.ui.Button(label=f"💰 Uzmi {fmt(cur)} novca (×{mult})",
                                    style=discord.ButtonStyle.success, row=4,
                                    disabled=self.safe_picked == 0)
        cashout.callback = self._cashout
        self.add_item(cashout)

    def _make_cb(self, idx):
        async def callback(interaction: discord.Interaction):
            if interaction.user.id != self.user.id:
                return await interaction.response.send_message("❌ Nije tvoja igra!", ephemeral=True)
            if idx in self.mines:
                record_game(str(self.user.id), self.user.name, "Minsko Polje", "lose", -self.bet)
                for item in self.children: item.disabled = True
                self.stop()
                embed = make_embed(self.user, self.EMOJI, self.NAME,
                    ["💥 EKSPLOZIJA!", f"Gubitak **{fmt(self.bet)}** novca."],
                    color=COLOR_LOSE, bet=self.bet, footer_hint="BOOM! 💥")
                return await interaction.response.edit_message(embed=embed, view=None)
            self.revealed.add(idx)
            self.safe_picked += 1
            mult = self._mult()
            cur  = int(self.bet * mult)
            if self.safe_picked >= 12:
                net = cur - self.bet
                add_novac(str(self.user.id), net)
                record_game(str(self.user.id), self.user.name, "Minsko Polje", "win", net)
                self.stop()
                embed = make_embed(self.user, self.EMOJI, self.NAME,
                    ["🏆 MAXWIN! Očistio/la si cijelo polje!", f"+**{fmt(net)}** novca! LEGENDA!"],
                    color=COLOR_WIN, bet=self.bet)
                return await interaction.response.edit_message(embed=embed, view=None)
            self._build()
            embed = make_embed(self.user, self.EMOJI, self.NAME,
                ["🎯 Otkrivaj polja — izbjegavaj mine!", f"✅ Sigurno polje! Trenutno: **{fmt(cur)}** novca (×{mult})"],
                fields=[{"name":"✅ Sigurnih","value":f"**{self.safe_picked}**","inline":True},
                        {"name":"📈 Trenutno","value":f"×{mult} = **{fmt(cur)}** novca","inline":True}],
                bet=self.bet)
            await interaction.response.edit_message(embed=embed, view=self)
        return callback

    async def _cashout(self, interaction: discord.Interaction):
        if interaction.user.id != self.user.id:
            return await interaction.response.send_message("❌ Nije tvoja igra!", ephemeral=True)
        mult = self._mult()
        earned = int(self.bet * mult)
        net = earned - self.bet
        add_novac(str(self.user.id), net)
        record_game(str(self.user.id), self.user.name, "Minsko Polje", "win", net)
        for item in self.children: item.disabled = True
        self.stop()
        embed = make_embed(self.user, self.EMOJI, self.NAME,
            [f"💰 Uzeto **{fmt(earned)}** novca!", f"Profit: +**{fmt(net)}**"],
            color=COLOR_WIN, bet=self.bet)
        await interaction.response.edit_message(embed=embed, view=None)

# ── 7. BLACKJACK ───────────────────────────────────────────────────────────────
SUITS = ["♠️","♥️","♦️","♣️"]
RANKS = ["2","3","4","5","6","7","8","9","10","J","Q","K","A"]

def make_deck():
    d = [f"{r}{s}" for s in SUITS for r in RANKS]
    random.shuffle(d)
    return d

def card_val(rank):
    if rank in ["J","Q","K"]: return 10
    if rank == "A": return 11
    return int(rank)

def hand_val(hand):
    total = sum(card_val(c[:-2] if len(c)>2 else c[:-1]) for c in hand)
    aces  = sum(1 for c in hand if c.startswith("A"))
    while total > 21 and aces:
        total -= 10; aces -= 1
    return total

def hand_str(hand, hide_first=False):
    if hide_first: return f"🂠 {' '.join(hand[1:])}"
    return " ".join(f"**{c}**" for c in hand)

class BlackjackView(discord.ui.View):
    EMOJI = "🃏"; NAME = "Blackjack"

    def __init__(self, user, bet):
        super().__init__(timeout=120)
        self.user   = user
        self.bet    = bet
        self.deck   = make_deck()
        self.player = [self.deck.pop(), self.deck.pop()]
        self.dealer = [self.deck.pop(), self.deck.pop()]

    def initial_embed(self):
        return self._embed()

    def _embed(self, hide=True, bullets=None, color=COLOR_DEFAULT):
        pv = hand_val(self.player)
        dv = hand_val(self.dealer)
        return make_embed(self.user, self.EMOJI, self.NAME,
            bullets or ["🎯 Stigni što bliže 21 bez prelaska!", "🃏 Hit = uzmi kartu, Stand = ostani!"],
            fields=[{"name":"🎴 Tvoje Karte","value":f"{hand_str(self.player)}\nVrijednost: **{pv}**"},
                    {"name":"🤵 Dealer","value":f"{hand_str(self.dealer, hide)}\nVrijednost: **{'?' if hide else dv}**"}],
            color=color, bet=self.bet, footer_hint="Hit ili Stand!")

    async def _end(self, interaction, reason):
        while hand_val(self.dealer) < 17:
            self.dealer.append(self.deck.pop())
        pv, dv = hand_val(self.player), hand_val(self.dealer)
        if pv > 21:
            result, net, msg = "lose", -self.bet, f"💥 Bust! Gubitak **{fmt(self.bet)}** novca."
        elif dv > 21 or pv > dv:
            result, net, msg = "win", self.bet, f"🏆 Pobjeda! +**{fmt(self.bet)}** novca!"
        elif pv < dv:
            result, net, msg = "lose", -self.bet, f"😔 Dealer pobijedio. Gubitak **{fmt(self.bet)}** novca."
        else:
            result, net, msg = "draw", 0, "🤝 Nerješeno! Ulog vraćen."
        add_novac(str(self.user.id), net)
        record_game(str(self.user.id), self.user.name, "Blackjack", result, net)
        color = COLOR_WIN if net > 0 else COLOR_LOSE if net < 0 else COLOR_DEFAULT
        for item in self.children: item.disabled = True
        self.stop()
        embed = self._embed(hide=False, bullets=[f"📋 {reason}", msg], color=color)
        await interaction.response.edit_message(embed=embed, view=None)

    @discord.ui.button(label="Hit", emoji="🃏", style=discord.ButtonStyle.primary)
    async def hit(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user.id:
            return await interaction.response.send_message("❌ Nije tvoja igra!", ephemeral=True)
        self.player.append(self.deck.pop())
        if hand_val(self.player) > 21:
            return await self._end(interaction, "Bust!")
        embed = self._embed(bullets=[f"🃏 Uzeta karta!", f"Vrijednost: **{hand_val(self.player)}**"])
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="Stand", emoji="✋", style=discord.ButtonStyle.secondary)
    async def stand(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user.id:
            return await interaction.response.send_message("❌ Nije tvoja igra!", ephemeral=True)
        await self._end(interaction, "Stand — dealer odigrao")

    @discord.ui.button(label="Double", emoji="💰", style=discord.ButtonStyle.success)
    async def double(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user.id:
            return await interaction.response.send_message("❌ Nije tvoja igra!", ephemeral=True)
        self.bet *= 2
        self.player.append(self.deck.pop())
        await self._end(interaction, "Double down!")

# ── 8. ZMAJ ILI VITEZ ─────────────────────────────────────────────────────────
DRAGON_ATK = ["Zmaj puhao vatru!","Zmaj mahao krilima!","Zmaj udario repom!","Kritičan vatren udarac!"]
KNIGHT_ATK = ["Vitez probio oklop!","Vitez napao s leđa!","Koplje — direktan pogodak!","Sveta energija!"]
DRAW_TXT   = ["Obojica iscrpljeni!","Savršena ravnoteža sila!","Bitka trajala satima!"]

class ZmajView(discord.ui.View):
    EMOJI = "🐉"; NAME = "Zmaj ili Vitez"

    def __init__(self, user, bet):
        super().__init__(timeout=60)
        self.user = user; self.bet = bet

    def initial_embed(self):
        return make_embed(self.user, self.EMOJI, self.NAME,
            ["🎯 Odaberi svog borca i bori se!"], bet=self.bet, footer_hint="Odaberi borca!")

    @discord.ui.button(label="Zmaj", emoji="🐉", style=discord.ButtonStyle.danger)
    async def zmaj(self, i, b): await self._fight(i, "zmaj")

    @discord.ui.button(label="Vitez", emoji="⚔️", style=discord.ButtonStyle.primary)
    async def vitez(self, i, b): await self._fight(i, "vitez")

    async def _fight(self, interaction: discord.Interaction, choice: str):
        if interaction.user.id != self.user.id:
            return await interaction.response.send_message("❌ Nije tvoja igra!", ephemeral=True)
        roll = random.randint(1, 100)
        if roll <= 45:
            result, net = "win", int(self.bet * 1.2)
            story = random.choice(DRAGON_ATK if choice=="zmaj" else KNIGHT_ATK)
            msg = f"🏆 **{'Zmaj' if choice=='zmaj' else 'Vitez'}** pobijedio! +**{fmt(net)}** novca!"
        elif roll <= 90:
            result, net = "lose", -self.bet
            story = random.choice(KNIGHT_ATK if choice=="zmaj" else DRAGON_ATK)
            msg = f"😔 **{'Vitez' if choice=='zmaj' else 'Zmaj'}** pobijedio. Gubitak **{fmt(self.bet)}** novca."
        else:
            result, net = "draw", 0
            story = random.choice(DRAW_TXT)
            msg = "🤝 Nerješeno! Ulog vraćen."
        add_novac(str(self.user.id), net)
        record_game(str(self.user.id), self.user.name, "Zmaj ili Vitez", result, net)
        color = COLOR_WIN if net > 0 else COLOR_LOSE if net < 0 else COLOR_DEFAULT
        for item in self.children: item.disabled = True
        self.stop()
        embed = make_embed(self.user, self.EMOJI, self.NAME,
            [f"⚔️ *{story}*", msg],
            fields=[{"name":"🎭 Izbor","value":f"{'🐉 Zmaj' if choice=='zmaj' else '⚔️ Vitez'}","inline":True}],
            color=color, bet=self.bet)
        await interaction.response.edit_message(embed=embed, view=None)

# ── 9. POGODAK ─────────────────────────────────────────────────────────────────
PROX_MULTS = [5, 3, 2, 1.5, 1]

class PogodakView(discord.ui.View):
    EMOJI = "🎯"; NAME = "Pogodak"

    def __init__(self, user, bet):
        super().__init__(timeout=120)
        self.user   = user
        self.bet    = bet
        self.target = random.randint(0, 8)
        self.shots  = 0
        self.missed = set()
        self._build()

    def initial_embed(self):
        return make_embed(self.user, self.EMOJI, self.NAME,
            ["🎯 Traži skrivenu metu — imaš 5 hitaca!"],
            fields=[{"name":"🔫 Preostalo","value":"**5** hitaca","inline":True},
                    {"name":"📊 Sljedeći bonus","value":f"×{PROX_MULTS[0]}","inline":True}],
            bet=self.bet, footer_hint="Nađi metu!")

    def _prox(self, idx):
        gr, gc = idx//3, idx%3
        tr, tc = self.target//3, self.target%3
        d = abs(gr-tr) + abs(gc-tc)
        return ["🎯 POGODAK!","🔥 Jako vruće!","♨️ Vruće!","❄️ Hladno!"][min(d,3)]

    def _build(self):
        self.clear_items()
        for i in range(9):
            em = "💨" if i in self.missed else "🟦"
            btn = discord.ui.Button(emoji=em, label="\u200b", style=discord.ButtonStyle.primary,
                                    row=i//3, disabled=i in self.missed)
            btn.callback = self._make_cb(i)
            self.add_item(btn)

    def _make_cb(self, idx):
        async def callback(interaction: discord.Interaction):
            if interaction.user.id != self.user.id:
                return await interaction.response.send_message("❌ Nije tvoja igra!", ephemeral=True)
            self.shots += 1
            if idx == self.target:
                mult = PROX_MULTS[min(self.shots-1, len(PROX_MULTS)-1)]
                earned = int(self.bet * mult)
                net = earned - self.bet
                add_novac(str(self.user.id), net)
                record_game(str(self.user.id), self.user.name, "Pogodak", "win", net)
                for item in self.children: item.disabled = True
                self.stop()
                embed = make_embed(self.user, self.EMOJI, self.NAME,
                    [f"🎯 Pogodak na **{self.shots}. hitac**!", f"+**{fmt(net)}** novca (×{mult})!"],
                    color=COLOR_WIN, bet=self.bet)
                return await interaction.response.edit_message(embed=embed, view=None)
            self.missed.add(idx)
            prox = self._prox(idx)
            if self.shots >= 5:
                record_game(str(self.user.id), self.user.name, "Pogodak", "lose", -self.bet)
                for item in self.children: item.disabled = True
                self.stop()
                embed = make_embed(self.user, self.EMOJI, self.NAME,
                    ["💨 Potrošeni svi pokušaji!", f"Gubitak **{fmt(self.bet)}** novca."],
                    color=COLOR_LOSE, bet=self.bet)
                return await interaction.response.edit_message(embed=embed, view=None)
            self._build()
            next_mult = PROX_MULTS[min(self.shots, len(PROX_MULTS)-1)]
            embed = make_embed(self.user, self.EMOJI, self.NAME,
                [f"💨 Promašeno! {prox}", f"Hitac {self.shots}/5"],
                fields=[{"name":"🔫 Preostalo","value":f"**{5-self.shots}** hitaca","inline":True},
                        {"name":"📊 Sljedeći bonus","value":f"×{next_mult}","inline":True}],
                bet=self.bet)
            await interaction.response.edit_message(embed=embed, view=self)
        return callback

# ── 10. MATEMATIKA ─────────────────────────────────────────────────────────────
def gen_math():
    t = random.randint(1,4)
    if t == 1:
        a,b = random.randint(10,99), random.randint(10,99)
        if random.randint(0,1): return f"{a} + {b} = ?", a+b, 1.5
        a,b = max(a,b), min(a,b)
        return f"{a} - {b} = ?", a-b, 1.5
    elif t == 2:
        a,b = random.randint(2,12), random.randint(2,12)
        return f"{a} × {b} = ?", a*b, 2
    elif t == 3:
        b = random.randint(2,9); ans = random.randint(2,12)
        return f"{b*ans} ÷ {b} = ?", ans, 2
    else:
        a,b,c = random.randint(5,20), random.randint(2,9), random.randint(1,10)
        return f"({a} × {b}) + {c} = ?", a*b+c, 3

class MatikaView(discord.ui.View):
    EMOJI = "🔢"; NAME = "Matematika"

    def __init__(self, user, bet):
        super().__init__(timeout=60)
        self.user = user; self.bet = bet
        self.question, self.answer, self.mult = gen_math()
        self.start_time = time.time()
        wrongs = set()
        while len(wrongs) < 3:
            w = self.answer + random.choice([-5,-3,-2,-1,1,2,3,5,7,10])
            if w > 0 and w != self.answer: wrongs.add(w)
        opts = [self.answer] + list(wrongs)
        random.shuffle(opts)
        self.opts = opts
        self.correct_idx = opts.index(self.answer)
        for i, opt in enumerate(opts):
            btn = discord.ui.Button(label=str(opt), style=discord.ButtonStyle.primary, row=0)
            btn.callback = self._make_cb(i)
            self.add_item(btn)

    def initial_embed(self):
        return make_embed(self.user, self.EMOJI, self.NAME,
            [f"🧮 **{self.question}**", "⚡ Brzina rješavanja = veći bonus!"],
            fields=[{"name":"📊 Multiplikator","value":f"×{self.mult}","inline":True}],
            bet=self.bet, footer_hint="Brzina = bonus!")

    def _make_cb(self, idx):
        async def callback(interaction: discord.Interaction):
            if interaction.user.id != self.user.id:
                return await interaction.response.send_message("❌ Nije tvoja igra!", ephemeral=True)
            elapsed = time.time() - self.start_time
            correct = idx == self.correct_idx
            speed = 1.5 if elapsed < 5 else 1.2 if elapsed < 10 else 1
            earned = int(self.bet * self.mult * speed) if correct else 0
            net = earned - self.bet
            add_novac(str(self.user.id), net)
            record_game(str(self.user.id), self.user.name, "Matematika", "win" if correct else "lose", net)
            for item in self.children: item.disabled = True
            self.stop()
            bullets = [f"🧮 **{self.question}**", f"🎯 Odabrano: **{self.opts[idx]}**"]
            if correct:
                bonus = f" + brzinski bonus ×{speed:.1f}" if speed > 1 else ""
                bullets.append(f"✅ TAČNO za {elapsed:.1f}s! +**{fmt(net)}** novca{bonus}! 🎉")
            else:
                bullets.append(f"❌ Netačno! Tačan: **{self.answer}**. Gubitak **{fmt(self.bet)}** novca.")
            embed = make_embed(self.user, self.EMOJI, self.NAME, bullets,
                fields=[{"name":"⏱️ Vrijeme","value":f"{elapsed:.1f}s","inline":True},
                        {"name":"📊 Multiplikator","value":f"×{self.mult * speed:.2f}","inline":True}],
                bet=self.bet, color=COLOR_WIN if correct else COLOR_LOSE)
            await interaction.response.edit_message(embed=embed, view=None)
        return callback

# ── 11. BINGO (tiket model — identičan izgled kao dogovoreni referentni izgled) ─
BINGO_DRAW_COUNT = 20   # koliko se brojeva izvlači iz 75 pri obračunu tiketa
BINGO_PRIZES = {2: 10_000, 3: 30_000, 4: 75_000, 5: 250_000}
BINGO_PAYTABLE = quote([
    f"🥉 2 pogotka — **{fmt(BINGO_PRIZES[2])}** novca",
    f"🥈 3 pogotka — **{fmt(BINGO_PRIZES[3])}** novca",
    f"🥇 4 pogotka — **{fmt(BINGO_PRIZES[4])}** novca",
    f"👑 5 pogodaka — **{fmt(BINGO_PRIZES[5])}** novca 🎉 JACKPOT!",
])

class BingoTicketModal(discord.ui.Modal, title="🎯 Bingo Tiket"):
    brojevi = discord.ui.TextInput(
        label="5 brojeva (1-75), razdvojenih zarezom",
        placeholder="npr. 3, 17, 28, 44, 61",
        max_length=40,
    )

    def __init__(self, view: "BingoView"):
        super().__init__()
        self.view_ref = view

    async def on_submit(self, interaction: discord.Interaction):
        try:
            nums = [int(x.strip()) for x in self.brojevi.value.split(",") if x.strip() != ""]
        except ValueError:
            return await interaction.response.send_message(
                "❌ Unesi samo brojeve razdvojene zarezom (npr. 3, 17, 28, 44, 61).", ephemeral=True)
        nums = list(dict.fromkeys(nums))  # ukloni eventualne duplikate
        if len(nums) != 5 or any(n < 1 or n > 75 for n in nums):
            return await interaction.response.send_message(
                "❌ Unesi tačno **5 različitih** brojeva između **1 i 75**.", ephemeral=True)
        await self.view_ref._resolve(interaction, nums)

class BingoView(discord.ui.View):
    EMOJI = "🎯"; NAME = "Bingo"

    def __init__(self, user, bet):
        super().__init__(timeout=120)
        self.user = user
        self.bet  = bet

    def initial_embed(self):
        return make_embed(self.user, self.EMOJI, self.NAME,
            ["🎯 Klikni dugme ispod i unesi 5 brojeva (1-75)!",
             f"🎫 Tiket košta **{fmt(self.bet)}** novca — već skinuto sa računa.",
             "⏰ Imaš **2 minute** da izabereš brojeve — budi brz! 🔥",
             "📢 Rezultati se objavljuju javno za sve! 🌍"],
            fields=[{"name":"🏆 Nagradna Lista","value":BINGO_PAYTABLE,"inline":False}],
            footer_hint=f"Cijena tiketa: {fmt(self.bet)} novca")

    @discord.ui.button(label="Uzmi Tiket", emoji="🎯", style=discord.ButtonStyle.success)
    async def take_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user.id:
            return await interaction.response.send_message("❌ Nije tvoja igra!", ephemeral=True)
        await interaction.response.send_modal(BingoTicketModal(self))

    async def _resolve(self, interaction: discord.Interaction, nums):
        drawn = random.sample(range(1, 76), BINGO_DRAW_COUNT)
        matches = sorted(n for n in nums if n in drawn)
        hit_count = len(matches)
        prize = BINGO_PRIZES.get(hit_count, 0)
        net = prize - self.bet
        if prize:
            add_novac(str(self.user.id), prize)
        record_game(str(self.user.id), self.user.name, "Bingo", "win" if prize else "lose", net)
        for item in self.children: item.disabled = True
        self.stop()

        drawn_str  = ", ".join(f"{bingo_letter(x)}-{x}" for x in sorted(drawn))
        tvoji_str  = ", ".join(str(n) for n in nums)
        pogoci_str = ", ".join(str(n) for n in matches) if matches else "—"

        if prize:
            bullets = [f"🎉 Pogodio/la si **{hit_count}** od 5 brojeva!", f"+**{fmt(net)}** novca!"]
            color = COLOR_WIN
        else:
            bullets = [f"😔 Pogodio/la si samo **{hit_count}** od 5 brojeva.",
                       f"Gubitak **{fmt(self.bet)}** novca."]
            color = COLOR_LOSE

        embed = make_embed(self.user, self.EMOJI, self.NAME, bullets,
            fields=[{"name":"🎫 Tvoji Brojevi","value":tvoji_str,"inline":True},
                    {"name":"🎯 Pogoci","value":pogoci_str,"inline":True},
                    {"name":"🎱 Izvučeno","value":drawn_str,"inline":False},
                    {"name":"🏆 Nagradna Lista","value":BINGO_PAYTABLE,"inline":False}],
            color=color, footer_hint=f"Cijena tiketa: {fmt(self.bet)} novca")
        await interaction.response.edit_message(embed=embed, view=None)

# ── GAME REGISTRY ──────────────────────────────────────────────────────────────
GAMES = [
    {"id":"grebalice",  "name":"Grebalice",       "emoji":"🎰", "desc":"Grebi 3 od 9 polja!",              "bet":50,  "view":GrebaliceView},
    {"id":"bingo",      "name":"Bingo",            "emoji":"🎯", "desc":"Unesi 5 brojeva i pogodi izvučene!", "bet":500, "view":BingoView},
    {"id":"kolo",       "name":"Kolo Srece",       "emoji":"🎡", "desc":"Zavrti i osvoji!",                 "bet":30,  "view":KoloView},
    {"id":"pitanje",    "name":"Pitanje",          "emoji":"❓", "desc":"Odgovori tačno i osvoji!",         "bet":25,  "view":PitanjeView},
    {"id":"nastavi",    "name":"Nastavi Pjesmu",   "emoji":"🎵", "desc":"Pogodi nastavak pjesme!",          "bet":30,  "view":NastaviView},
    {"id":"oblik",      "name":"Pogodi Oblik",     "emoji":"🔷", "desc":"Prepoznaj geometrijski oblik!",    "bet":25,  "view":OblikView},
    {"id":"minsko",     "name":"Minsko Polje",     "emoji":"💣", "desc":"Izbjegavaj mine i zarađuj!",       "bet":60,  "view":MinskoView},
    {"id":"blackjack",  "name":"Blackjack",        "emoji":"🃏", "desc":"Stigni što bliže 21!",             "bet":50,  "view":BlackjackView},
    {"id":"zmaj",       "name":"Zmaj ili Vitez",   "emoji":"🐉", "desc":"Odaberi borca i bori se!",         "bet":35,  "view":ZmajView},
    {"id":"pogodak",    "name":"Pogodak",          "emoji":"🎯", "desc":"Nađi skrivenu metu!",              "bet":40,  "view":PogodakView},
    {"id":"matematika", "name":"Matematika",       "emoji":"🔢", "desc":"Riješi zadatak — brzina = bonus!", "bet":20,  "view":MatikaView},
]

# ── INVITE VIEW ─────────────────────────────────────────────────────────────────
class GameInviteView(discord.ui.View):
    def __init__(self, game: dict):
        super().__init__(timeout=600)
        self.game = game
        btn = discord.ui.Button(label=f"Igraj! {game['name']}", emoji="🎮",
                                style=discord.ButtonStyle.success)
        btn.callback = self._play
        self.add_item(btn)

    async def _play(self, interaction: discord.Interaction):
        g = self.game
        user = interaction.user
        u = get_user(str(user.id), user.name)
        bet = g["bet"]
        if u["novac"] < bet:
            return await interaction.response.send_message(
                f"💸 Nemaš dovoljno novca! Imaš **{fmt(u['novac'])}** a treba **{fmt(bet)}**. Koristi `/bonus`!",
                ephemeral=True)
        add_novac(str(user.id), -bet)
        view = g["view"](user, bet)
        # Svaka igra odmah pokazuje svoje pravo stanje (pitanje, pjesmu, karte, tablu...)
        # umjesto generičke poruke — tako igrač odmah vidi šta treba pogoditi/uraditi.
        embed = view.initial_embed()
        await interaction.response.send_message(embed=embed, view=view)

# ── BOT SETUP ──────────────────────────────────────────────────────────────────
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix=PREFIX, intents=intents, help_command=None)
tree = bot.tree

# ── AUTO GAME TASK ──────────────────────────────────────────────────────────────
@tasks.loop(minutes=GAME_INTERVAL)
async def auto_game():
    if not GAME_CHANNEL_ID:
        return
    channel = bot.get_channel(GAME_CHANNEL_ID)
    if not channel:
        return
    idx = get_next_game_index()
    g = GAMES[idx]
    embed = make_embed(None, g["emoji"], g["name"],
        [f"🎯 Klikni **Igraj!** ispod i uđi u igru!",
         f"⏰ Rok za igru: **10 minuta**",
         f"🔁 Sljedeća igra za **{GAME_INTERVAL} minuta** (redom, jedna po jedna)"],
        fields=[{"name":"🎮 Igra","value":f"**{idx+1}/{len(GAMES)}** — {g['desc']}","inline":False}],
        bet=g["bet"], footer_hint="Klikni i igraj!")
    embed.title = f"{g['emoji']} Automatska Igra"
    await channel.send(embed=embed, view=GameInviteView(g))

@bot.event
async def on_ready():
    print(f"✅ {bot.user} je spreman! | {BOT_NAME} {BOT_VERSION}")
    try:
        if GUILD_ID:
            guild = discord.Object(id=GUILD_ID)
            tree.copy_global_to(guild=guild)
            synced = await tree.sync(guild=guild)
        else:
            synced = await tree.sync()
        print(f"🔄 Sinhronizirano {len(synced)} slash komandi.")
    except Exception as e:
        print(f"❌ Greška pri sinhronizaciji: {e}")
    await bot.change_presence(
        activity=discord.Activity(type=discord.ActivityType.playing, name="🎰 Squad Lutrija | /igre"))
    if not auto_game.is_running():
        auto_game.start()

# ── SLASH KOMANDE ──────────────────────────────────────────────────────────────

@tree.command(name="stanje", description="Provjeri svoje stanje novca i statistiku")
async def cmd_stanje(interaction: discord.Interaction):
    u = get_user(str(interaction.user.id), interaction.user.name)
    wr = f"{round(u['total_wins']/u['total_games']*100)}%" if u['total_games'] > 0 else "N/A"
    embed = make_embed(interaction.user, "💰", "Stanje Racuna",
        ["📊 Pregled tvog novca i statistike."],
        fields=[{"name":"💵 Novac","value":f"**{fmt(u['novac'])}** novca","inline":True},
                {"name":"🏅 Rang","value":rank_title(u['novac']),"inline":True},
                {"name":"🎮 Igara","value":f"**{u['total_games']}**","inline":True},
                {"name":"🏆 Pobjeda","value":f"**{u['total_wins']}**","inline":True},
                {"name":"📊 Win Rate","value":wr,"inline":True},
                {"name":"🔥 Niz Dana (bonus)","value":f"**{u['streak']}**","inline":True}],
        footer_hint="Igraj i zarađuj!")
    await interaction.response.send_message(embed=embed, ephemeral=True)

@tree.command(name="bonus", description="Uzmi dnevni bonus (raste sa uzastopnim danima)")
async def cmd_bonus(interaction: discord.Interaction):
    u = get_user(str(interaction.user.id), interaction.user.name)
    now = int(time.time())
    cooldown = 24 * 3600
    grace = 48 * 3600  # ako se uzme unutar 48h, niz se nastavlja; inače se resetuje
    if now - u["last_daily"] < cooldown:
        remaining = cooldown - (now - u["last_daily"])
        h = remaining // 3600; m = (remaining % 3600) // 60
        return await interaction.response.send_message(
            f"⏰ Već si uzeo/la bonus! Sljedeći za **{h}h {m}m**.", ephemeral=True)
    if u["last_daily"] != 0 and now - u["last_daily"] <= grace:
        new_streak = u["streak"] + 1
    else:
        new_streak = 1
    bonus = DAILY_AMOUNT + min(new_streak, STREAK_BONUS_CAP) * STREAK_BONUS_STEP
    conn = db_connect()
    conn.execute("UPDATE users SET last_daily=?, streak=? WHERE discord_id=?",
                 (now, new_streak, str(interaction.user.id)))
    conn.commit(); conn.close()
    new_bal = add_novac(str(interaction.user.id), bonus)
    embed = make_embed(interaction.user, "🎁", "Dnevni Bonus",
        ["🎯 Bonus dodijeljen! Vrati se sutra da nastaviš niz."],
        fields=[{"name":"🔥 Niz Dana","value":f"**{new_streak}**","inline":True},
                {"name":"🎁 Bonus","value":f"+**{fmt(bonus)}** novca","inline":True},
                {"name":"💵 Novo Stanje","value":f"**{fmt(new_bal)}** novca","inline":True}],
        color=COLOR_WIN, footer_hint="Uzeti svaka 24h!")
    await interaction.response.send_message(embed=embed, ephemeral=True)

@tree.command(name="igre", description="Pogledaj sve dostupne igre")
async def cmd_igre(interaction: discord.Interaction):
    lista = quote(f"{g['emoji']} **{g['name']}** — ulog: **{fmt(g['bet'])}** novca" for g in GAMES)
    embed = make_embed(interaction.user, "🎰", "Dostupne Igre",
        [f"🔁 Automatski se pokreću svakih **{GAME_INTERVAL} minuta**, redom jedna po jedna!"],
        fields=[{"name":"🎮 Igre","value":lista,"inline":False}],
        footer_hint=f"{len(GAMES)} igara dostupno!")
    await interaction.response.send_message(embed=embed)

@tree.command(name="top", description="Top 10 najbogatijih igrača")
async def cmd_top(interaction: discord.Interaction):
    rows = get_top_users(10)
    medals = ["🥇","🥈","🥉","4️⃣","5️⃣","6️⃣","7️⃣","8️⃣","9️⃣","🔟"]
    if rows:
        text = quote(f"{medals[i]} **{r[0]}** — {fmt(r[1])} novca" for i,r in enumerate(rows))
    else:
        text = quote(["Nema igrača još!"])
    embed = make_embed(interaction.user, "🏆", "Top 10 Igraca",
        ["📊 Najbogatiji igrači na serveru — ažurirano upravo sada."],
        fields=[{"name":"💰 Rang Lista","value":text,"inline":False}],
        footer_hint="Igraj i uđi na listu!")
    await interaction.response.send_message(embed=embed)

# ── BAN SLASH KOMANDE (javno vidljive svima u kanalu) ──────────────────────────

@tree.command(name="ban", description="Banuj korisnika")
@app_commands.describe(korisnik="Korisnik kojeg banuješ", razlog="Razlog bana")
@app_commands.checks.has_permissions(ban_members=True)
async def cmd_ban(interaction: discord.Interaction, korisnik: discord.Member, razlog: str = "Nije naveden razlog"):
    await interaction.response.defer(ephemeral=True)
    guild_id = str(interaction.guild_id)
    ban_count = add_ban(str(korisnik.id), korisnik.name,
                        str(interaction.user.id), interaction.user.name, razlog, guild_id)

    anti_triggered = False
    if ban_count >= ANTI_BAN_THRESHOLD and ANTI_BAN_ROLE_ID:
        role = interaction.guild.get_role(ANTI_BAN_ROLE_ID)
        if role and role in korisnik.roles:
            await korisnik.remove_roles(role, reason=f"Anti-ban: {ban_count} banova")
            anti_triggered = True

    embed = make_embed(interaction.user, "🔨", "Korisnik Je Banovan",
        [f"⛔ **@{korisnik.name}** je banovan sa servera!"],
        fields=[{"name":"👤 Korisnik","value":f"<@{korisnik.id}> (**{korisnik.name}**)","inline":True},
                {"name":"👮 Moderator","value":f"<@{interaction.user.id}>","inline":True},
                {"name":"📋 Razlog","value":f"```{razlog}```","inline":False},
                {"name":"🔢 Ukupno Banova","value":f"**{ban_count}**","inline":True},
                {"name":"⚠️ Status",
                 "value":"🔴 **ANTI-BAN AKTIVIRAN** — Uloga skinuta!" if anti_triggered
                         else f"🟡 {ANTI_BAN_THRESHOLD - ban_count} ban(a) do skidanja uloge",
                 "inline":True}],
        color=COLOR_BAN)

    # Ban obavijest ide javno u ban kanal (vidljivo svima), ne privatno
    if BAN_CHANNEL_ID:
        ban_ch = bot.get_channel(BAN_CHANNEL_ID)
        if ban_ch:
            view = discord.ui.View()
            unban_btn = discord.ui.Button(label="Odbanuj", emoji="✅", style=discord.ButtonStyle.success,
                                          custom_id=f"unban_{korisnik.id}")
            view.add_item(unban_btn)
            await ban_ch.send(embed=embed, view=view)

    # DM banovanom korisniku
    try:
        dm_embed = make_embed(korisnik, "⛔", "Banovan Si",
            [f"Banovan/a si na **{interaction.guild.name}**!", f"**Razlog:** {razlog}"],
            color=COLOR_BAN, footer_hint="Kontaktiraj moderatora za žalbu")
        await korisnik.send(embed=dm_embed)
    except: pass

    if anti_triggered:
        await interaction.followup.send(f"✅ **@{korisnik.name}** banovan. ⚡ Anti-ban aktiviran — uloga skinuta!", ephemeral=True)
    else:
        await interaction.followup.send(f"✅ **@{korisnik.name}** banovan. Razlog: {razlog}", ephemeral=True)

@tree.command(name="unban", description="Odbanuj korisnika po ID-u")
@app_commands.describe(user_id="Discord ID korisnika")
@app_commands.checks.has_permissions(ban_members=True)
async def cmd_unban(interaction: discord.Interaction, user_id: str):
    success = remove_ban(user_id, str(interaction.user.id))
    if not success:
        return await interaction.response.send_message("❌ Nema aktivnog bana za tog korisnika.", ephemeral=True)
    embed = make_embed(interaction.user, "✅", "Korisnik Je Odbanovan",
        [f"✅ Korisnik ID `{user_id}` je odbanovan."],
        fields=[{"name":"👮 Moderator","value":f"<@{interaction.user.id}>","inline":True}],
        color=COLOR_WIN)
    if BAN_CHANNEL_ID:
        ban_ch = bot.get_channel(BAN_CHANNEL_ID)
        if ban_ch: await ban_ch.send(embed=embed)
    await interaction.response.send_message(embed=embed, ephemeral=True)

@tree.command(name="banlista", description="Lista svih aktivnih banova (javno vidljivo)")
async def cmd_banlista(interaction: discord.Interaction):
    bans = get_active_bans()
    if not bans:
        text = quote(["✅ Nema aktivnih banova na serveru!"])
    else:
        text = quote(
            f"⛔ **{b[1]}** (ID: `{b[0]}`) — **Razlog:** {b[3]} — **Mod:** <@{b[2]}>"
            for b in bans[:10])
    embed = make_embed(interaction.user, "📋", "Ban Lista",
        [f"⛔ Ukupno **{len(bans)}** aktivnih banova na serveru."],
        fields=[{"name":"Banovi","value":text,"inline":False}],
        color=discord.Color.from_rgb(255, 45, 111).value)
    await interaction.response.send_message(embed=embed)

@tree.command(name="moj-ban", description="Provjeri vlastiti ban status (javno vidljivo)")
async def cmd_moj_ban(interaction: discord.Interaction):
    bans = get_user_bans(str(interaction.user.id))
    active = [b for b in bans if b[1] == 1]
    text = quote(f"• {b[0]} — *{'Aktivan' if b[1] else 'Uklonjen'}*" for b in bans[-5:]) if bans else quote(["Nema banova"])
    embed = make_embed(interaction.user, "⛔" if active else "✅",
        "Tvoj Ban Status" if active else "Nisi Banovan",
        [f"⛔ Trenutno si banovan/a! Kontaktiraj moderatora." if active else "✅ Nisi na ban listi! Uživaj!"],
        fields=[{"name":"🔢 Ukupno Banova","value":f"**{len(bans)}**","inline":True},
                {"name":"⛔ Aktivnih","value":f"**{len(active)}**","inline":True},
                {"name":"📋 Historija","value":text,"inline":False}],
        color=COLOR_LOSE if active else COLOR_WIN)
    # Javno vidljivo svima u kanalu (nije ephemeral) — banovi treba da se vide
    await interaction.response.send_message(embed=embed, ephemeral=False)

# ── OWNER PREFIX KOMANDE (.) ───────────────────────────────────────────────────

@bot.command(name="daijnovca")
async def owner_give(ctx: commands.Context, member: discord.Member = None, amount: int = 500):
    if ctx.author.id != OWNER_ID and OWNER_ID != 0: return
    if not member: return await ctx.reply("Upotreba: `.daijnovca @korisnik iznos`")
    bal = add_novac(str(member.id), amount)
    await ctx.reply(f"✅ Dao/la **{fmt(amount)}** novca za **@{member.name}**. Novo stanje: **{fmt(bal)}**")

@bot.command(name="uzminovca")
async def owner_take(ctx: commands.Context, member: discord.Member = None, amount: int = 0):
    if ctx.author.id != OWNER_ID and OWNER_ID != 0: return
    if not member: return await ctx.reply("Upotreba: `.uzminovca @korisnik iznos`")
    bal = add_novac(str(member.id), -amount)
    await ctx.reply(f"✅ Uzeto **{fmt(amount)}** novca od **@{member.name}**. Novo stanje: **{fmt(bal)}**")

@bot.command(name="resetaj")
async def owner_reset(ctx: commands.Context, member: discord.Member = None):
    if ctx.author.id != OWNER_ID and OWNER_ID != 0: return
    if not member: return await ctx.reply("Upotreba: `.resetaj @korisnik`")
    conn = db_connect()
    conn.execute("UPDATE users SET novac=500, total_games=0, total_wins=0, streak=0 WHERE discord_id=?", (str(member.id),))
    conn.commit(); conn.close()
    await ctx.reply(f"✅ Resetovano stanje za **@{member.name}** na 500 novca.")

@bot.command(name="pokreni")
async def owner_trigger(ctx: commands.Context):
    if ctx.author.id != OWNER_ID and OWNER_ID != 0: return
    idx = get_next_game_index()
    g = GAMES[idx]
    embed = make_embed(None, g["emoji"], g["name"],
        ["🎯 Ručno pokrenuto od vlasnika!", "Klikni **Igraj!** ispod!"],
        bet=g["bet"], footer_hint="Klikni i igraj!")
    embed.title = f"{g['emoji']} Ručno Pokrenuta Igra"
    await ctx.send(embed=embed, view=GameInviteView(g))
    await ctx.message.add_reaction("✅")

@bot.command(name="pomoc")
async def owner_help(ctx: commands.Context):
    if ctx.author.id != OWNER_ID and OWNER_ID != 0: return
    help_text = "\n".join([
        "`.daijnovca @korisnik iznos` — Daj novac korisniku",
        "`.uzminovca @korisnik iznos` — Uzmi novac od korisnika",
        "`.resetaj @korisnik` — Resetuj stanje korisnika",
        "`.pokreni` — Ručno pokreni sljedeću igru u redoslijedu",
        "`.pomoc` — Ova lista",
    ])
    await ctx.reply(f"**🔑 Owner Komande:**\n{help_text}")

# ── BUTTON INTERACTION HANDLER ─────────────────────────────────────────────────
@bot.event
async def on_interaction(interaction: discord.Interaction):
    if interaction.type == discord.InteractionType.component:
        cid = interaction.data.get("custom_id", "")
        if cid.startswith("unban_"):
            uid = cid.split("_")[1]
            if not interaction.user.guild_permissions.ban_members:
                return await interaction.response.send_message("❌ Nemaš dozvolu!", ephemeral=True)
            ok = remove_ban(uid, str(interaction.user.id))
            msg = "✅ Korisnik odbanovan!" if ok else "❌ Nema aktivnog bana."
            await interaction.response.send_message(msg, ephemeral=True)

# ── ERROR HANDLING ─────────────────────────────────────────────────────────────
@tree.error
async def on_app_command_error(interaction: discord.Interaction, error):
    if isinstance(error, app_commands.MissingPermissions):
        await interaction.response.send_message("❌ Nemaš dozvolu za ovu komandu!", ephemeral=True)
    else:
        await interaction.response.send_message(f"⚠️ Greška: {error}", ephemeral=True)

# ── MAIN ───────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    db_init()
    if not TOKEN:
        print("❌ DISCORD_TOKEN nije postavljen! Dodaj ga u .env fajl (ili Replit Secrets).")
    else:
        print(f"🎰 Pokrećem {BOT_NAME} {BOT_VERSION}...")
        bot.run(TOKEN)
