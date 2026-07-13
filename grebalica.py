import random
import discord

OBJECTS = [
    {
        "answer": "telefon",
        "emoji": "📱",
        "clues": [
            "Imam ekran koji možeš dodirivati.",
            "Nosim ga u džepu svaki dan.",
            "Možeš me koristiti za pozivanje.",
            "Imam kameru i mikrofon.",
            "Mogu slati poruke i e-mailove.",
        ],
    },
    {
        "answer": "auto",
        "emoji": "🚗",
        "clues": [
            "Imam četiri kotača.",
            "Koristim gorivo ili struju.",
            "Vozač me upravlja volanom.",
            "Mogu prevesti nekoliko putnika.",
            "Imam svjetla sprijeda i straga.",
        ],
    },
    {
        "answer": "knjiga",
        "emoji": "📚",
        "clues": [
            "Napravljen/a sam od papira.",
            "Imam korice i stranice.",
            "Čuvam znanje i priče.",
            "Možeš me naći u biblioteci.",
            "Pisci me stvaraju godinama.",
        ],
    },
    {
        "answer": "gitara",
        "emoji": "🎸",
        "clues": [
            "Imam žice koje se drmaju.",
            "Glazbalo sam.",
            "Koristim se u rock i pop muzici.",
            "Imam vrat i tijelo.",
            "Možeš svirati akorde na meni.",
        ],
    },
    {
        "answer": "pizza",
        "emoji": "🍕",
        "clues": [
            "Jelo sam talijanskog porijekla.",
            "Imam okrugao oblik.",
            "Napravljen/a sam od tijesta.",
            "Na meni može biti sir i paradajz.",
            "Pečem se u pećnici.",
        ],
    },
    {
        "answer": "sunce",
        "emoji": "☀️",
        "clues": [
            "Zvijezda sam u centru našeg sistema.",
            "Dajem toplinu i svjetlost.",
            "Bez mene ne bi bilo života na Zemlji.",
            "Vidljiv/a sam danju ali ne i noću.",
            "Izlazim na istoku i zalazim na zapadu.",
        ],
    },
    {
        "answer": "pas",
        "emoji": "🐕",
        "clues": [
            "Životinja sam s četiri noge.",
            "Znam se čuti lajanjem.",
            "Čest sam kućni ljubimac.",
            "Imam rep koji maham kad sam sretan.",
            "Zovem se 'čovjekov najbolji prijatelj'.",
        ],
    },
    {
        "answer": "frizider",
        "emoji": "🧊",
        "clues": [
            "Električni uređaj sam.",
            "Hladim hranu i piće.",
            "Nalazi me se u kuhinji.",
            "Imam vrata i police iznutra.",
            "Čuvam hranu svježom duže.",
        ],
    },
]


def build_embed(puzzle, clues_shown, attempts, winner=None, gave_up=False):
    clues = puzzle["clues"][:clues_shown]
    clues_text = "\n".join(f"**{i+1}.** {c}" for i, c in enumerate(clues)) if clues else "Klikni Pogodi ili traži trag!"

    if winner:
        color = discord.Color.green()
        title = "🔍 Pogodi Objekat — Pogođeno!"
        desc = f"🏆 <@{winner}> je pogodio/la! Odgovor je bio **{puzzle['answer'].upper()}** {puzzle['emoji']}"
    elif gave_up:
        color = discord.Color.red()
        title = "🔍 Pogodi Objekat — Kraj!"
        desc = f"❌ Niko nije pogodio! Odgovor je bio **{puzzle['answer'].upper()}** {puzzle['emoji']}"
    else:
        color = discord.Color.teal()
        title = f"🔍 Pogodi Objekat {puzzle['emoji']}"
        desc = "Pažljivo čitaj tragove i pogodi o čemu se radi!"

    embed = discord.Embed(title=title, description=desc, color=color)
    embed.add_field(name=f"💡 Tragovi ({clues_shown}/{len(puzzle['clues'])})", value=clues_text, inline=False)
    embed.add_field(name="🎯 Pokušaji", value=f"`{attempts}`", inline=True)
    embed.set_footer(text="SQUAD Bot • Klikni i pogodi objekat!")
    return embed


class GuessObjectModal(discord.ui.Modal, title="Pogodi objekat!"):
    answer = discord.ui.TextInput(
        label="Šta je ovaj objekat?",
        placeholder="Unesi odgovor...",
        min_length=1,
        max_length=30,
    )

    def __init__(self, view):
        super().__init__()
        self.game_view = view

    async def on_submit(self, interaction: discord.Interaction):
        v = self.game_view
        guess = self.answer.value.strip().lower()
        correct = v.puzzle["answer"].lower()
        v.attempts += 1

        if guess == correct or correct in guess or guess in correct:
            v.winner = interaction.user.id
            v.active = False
            v.disable_all()
            embed = build_embed(v.puzzle, v.clues_shown, v.attempts, winner=v.winner)
            await interaction.response.edit_message(embed=embed, view=v)
        else:
            if v.clues_shown < len(v.puzzle["clues"]):
                v.clues_shown += 1
            await interaction.response.send_message(
                f"❌ Nije **{guess}**! Otkrio/la sam ti novi trag.", ephemeral=True
            )
            embed = build_embed(v.puzzle, v.clues_shown, v.attempts)
            if v.message:
                await v.message.edit(embed=embed, view=v)


class ObjekatView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.puzzle = random.choice(OBJECTS)
        self.clues_shown = 1
        self.attempts = 0
        self.winner = None
        self.gave_up = False
        self.active = True
        self.message = None

    def disable_all(self):
        for item in self.children:
            item.disabled = True

    @discord.ui.button(label="🔍 Pogodi", style=discord.ButtonStyle.primary)
    async def guess_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.active:
            await interaction.response.send_message("❌ Igra je gotova!", ephemeral=True)
            return
        await interaction.response.send_modal(GuessObjectModal(self))

    @discord.ui.button(label="💡 Još jedan trag", style=discord.ButtonStyle.secondary)
    async def hint_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.active:
            await interaction.response.send_message("❌ Igra je gotova!", ephemeral=True)
            return
        if self.clues_shown < len(self.puzzle["clues"]):
            self.clues_shown += 1
        embed = build_embed(self.puzzle, self.clues_shown, self.attempts)
        await interaction.response.edit_message(embed=embed, view=self)


class PogodiObjekat:
    name = "Pogodi Objekat"
    emoji = "🔍"

    @staticmethod
    async def start(channel: discord.TextChannel):
        view = ObjekatView()
        embed = build_embed(view.puzzle, view.clues_shown, 0)
        msg = await channel.send(embed=embed, view=view)
        view.message = msg
        return view, msg

    @staticmethod
    async def stop(view, message):
        if not view.active:
            return
        view.active = False
        view.gave_up = True
        view.disable_all()
        embed = build_embed(view.puzzle, view.clues_shown, view.attempts, gave_up=True)
        await message.edit(embed=embed, view=view)
