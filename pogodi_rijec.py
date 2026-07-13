import random
import discord

WORDS = [
    "jabuka", "banana", "kruska", "maslina", "naranca",
    "zemlja", "voda", "vjetar", "sunce", "mjesec",
    "krevet", "stolica", "prozor", "vrata", "lampa",
    "macka", "pseto", "konj", "ptica", "riba",
    "planina", "rijeka", "suma", "more", "jezero",
    "ljubav", "sreca", "nada", "vjera", "mir",
    "skola", "knjiga", "olovka", "papir", "tabla",
    "gitara", "bubanj", "violina", "truba", "klavir",
    "cokolada", "sladoled", "kolac", "pizza", "burger",
    "avion", "brod", "vlak", "bicikl", "auto",
]

MAX_WRONG = 6
HANGMAN = ["😶", "😕", "😟", "😦", "😧", "😨", "💀"]


def mask_word(word, guessed):
    return " ".join(f"**{c.upper()}**" if c in guessed else r"\\_" for c in word)


def build_embed(word, guessed, wrong, winner=None, failed=False):
    guessed_set = set(guessed)
    wrong_set = set(wrong)
    masked = mask_word(word, guessed_set)
    stage = HANGMAN[min(len(wrong_set), MAX_WRONG)]

    if winner:
        color = discord.Color.green()
        title = "📝 Pogodi Riječ — Pobjeda!"
        desc = f"🏆 <@{winner}> je pogodio/la riječ **{word.upper()}**!"
    elif failed:
        color = discord.Color.red()
        title = "📝 Pogodi Riječ — Kraj!"
        desc = f"💀 Niko nije pogodio! Riječ je bila **{word.upper()}**"
    else:
        color = discord.Color.blue()
        title = "📝 Pogodi Riječ"
        desc = "Pogodi skrivenu riječ slovo po slovo!"

    embed = discord.Embed(title=title, description=desc, color=color)
    embed.add_field(name="🔤 Riječ", value=masked or r"\\_", inline=False)
    wrong_disp = " ".join(f"`{l.upper()}`" for l in wrong) if wrong else "Nema još"
    embed.add_field(name="❌ Pogrešna slova", value=wrong_disp, inline=True)
    embed.add_field(name=f"{stage} Pokušaji", value=f"{len(wrong_set)} / {MAX_WRONG}", inline=True)
    embed.set_footer(text="SQUAD Bot • Klikni i pogodi slovo!")
    return embed


class LetterModal(discord.ui.Modal, title="Pogodi slovo"):
    letter = discord.ui.TextInput(
        label="Unesi jedno slovo",
        placeholder="npr. A",
        min_length=1,
        max_length=1,
    )

    def __init__(self, view):
        super().__init__()
        self.game_view = view

    async def on_submit(self, interaction: discord.Interaction):
        v = self.game_view
        l = self.letter.value.strip().lower()

        if l in v.guessed or l in v.wrong:
            await interaction.response.send_message(
                f"⚠️ Slovo `{l.upper()}` je već pogađano!", ephemeral=True
            )
            return

        if l in v.word:
            v.guessed.append(l)
        else:
            v.wrong.append(l)

        is_won = all(c in set(v.guessed) for c in v.word)
        is_failed = len(v.wrong) >= MAX_WRONG

        if is_won:
            v.winner = interaction.user.id
            v.active = False
            v.disable_all()
        elif is_failed:
            v.failed = True
            v.active = False
            v.disable_all()

        embed = build_embed(v.word, v.guessed, v.wrong, winner=v.winner, failed=v.failed)
        await interaction.response.edit_message(embed=embed, view=v)


class WordModal(discord.ui.Modal, title="Pogodi cijelu riječ"):
    word_input = discord.ui.TextInput(
        label="Unesi cijelu riječ",
        placeholder="npr. jabuka",
        min_length=2,
        max_length=20,
    )

    def __init__(self, view):
        super().__init__()
        self.game_view = view

    async def on_submit(self, interaction: discord.Interaction):
        v = self.game_view
        guess = self.word_input.value.strip().lower()

        if guess == v.word:
            v.winner = interaction.user.id
            v.guessed = list(v.word)
            v.active = False
            v.disable_all()
            embed = build_embed(v.word, v.guessed, v.wrong, winner=v.winner)
            await interaction.response.edit_message(embed=embed, view=v)
        else:
            v.wrong.extend(["?", "!"])
            if len(v.wrong) >= MAX_WRONG:
                v.failed = True
                v.active = False
                v.disable_all()
            await interaction.response.send_message(
                f"❌ Nije **{guess}**! Izgubio/la si 2 pokušaja.", ephemeral=True
            )
            embed = build_embed(v.word, v.guessed, v.wrong, failed=v.failed)
            if v.message:
                await v.message.edit(embed=embed, view=v)


class Rijec_View(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.word = random.choice(WORDS)
        self.guessed = []
        self.wrong = []
        self.winner = None
        self.failed = False
        self.active = True
        self.message = None

    def disable_all(self):
        for item in self.children:
            item.disabled = True

    @discord.ui.button(label="🔡 Pogodi slovo", style=discord.ButtonStyle.primary)
    async def letter_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.active:
            await interaction.response.send_message("❌ Igra je gotova!", ephemeral=True)
            return
        await interaction.response.send_modal(LetterModal(self))

    @discord.ui.button(label="💡 Pogodi cijelu riječ", style=discord.ButtonStyle.success)
    async def word_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.active:
            await interaction.response.send_message("❌ Igra je gotova!", ephemeral=True)
            return
        await interaction.response.send_modal(WordModal(self))


class PogodiRijec:
    name = "Pogodi Riječ"
    emoji = "📝"

    @staticmethod
    async def start(channel: discord.TextChannel):
        view = Rijec_View()
        embed = build_embed(view.word, [], [])
        msg = await channel.send(embed=embed, view=view)
        view.message = msg
        return view, msg

    @staticmethod
    async def stop(view, message):
        if not view.active:
            return
        view.active = False
        view.failed = True
        view.disable_all()
        embed = build_embed(view.word, view.guessed, view.wrong, failed=True)
        await message.edit(embed=embed, view=view)
