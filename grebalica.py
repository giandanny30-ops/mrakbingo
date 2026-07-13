import random
import discord

SYMBOLS = ["💎", "🍒", "⭐", "🍋", "🔔", "🍀", "🎰", "💰", "🌈"]


def scratch():
    roll = random.random()

    if roll < 0.05:  # 5% jackpot
        s = random.choice(SYMBOLS)
        symbols = [s] * 9
        prize = "🎉 JACKPOT! Tri iste posvuda!"
        emoji = "🏆"
    elif roll < 0.25:  # 20% mali dobitak
        s = random.choice(SYMBOLS)
        pool = [x for x in SYMBOLS if x != s]
        row = [s, s, s]
        rest = random.sample(pool, 6)
        symbols = row + rest
        random.shuffle(symbols)
        prize = "🎊 Mala pobjeda! Jedan red!"
        emoji = "✨"
    elif roll < 0.45:  # 20% skoro
        s = random.choice(SYMBOLS)
        pool = [x for x in SYMBOLS if x != s]
        symbols = [s, s] + random.sample(pool, 7)
        random.shuffle(symbols)
        prize = "😅 Skoro! Samo još jedan..."
        emoji = "😬"
    else:  # 55% ništa
        symbols = random.sample(SYMBOLS, 9)
        prize = "💨 Nema sreće ovaj put!"
        emoji = "😢"

    return symbols, prize, emoji


def render_grid(symbols):
    rows = []
    for i in range(3):
        rows.append(" ".join(symbols[i * 3:(i + 1) * 3]))
    return "\n".join(rows)


def build_embed(total_plays, recent):
    recent_text = "\n".join(
        f"<@{uid}>: {res['prize_emoji']} {res['prize']}"
        for uid, res in list(recent.items())[-5:]
    ) if recent else "Nitko još nije igrao!"

    embed = discord.Embed(
        title="🎰 Grebalica",
        description="Klikni **Grebi!** da otkriješ svoju tablicu! Poklopi tri iste i osvoji nagradu!",
        color=discord.Color.gold(),
    )
    embed.add_field(name="🎟️ Ukupno odigranih", value=f"`{total_plays}`", inline=True)
    embed.add_field(name="📊 Nedavni rezultati", value=recent_text, inline=False)
    embed.set_footer(text="SQUAD Bot • Sretno na Grebalici!")
    return embed


class GrebalicaView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.total_plays = 0
        self.recent = {}  # uid -> {prize, prize_emoji}
        self.active = True
        self.message = None

    def disable_all(self):
        for item in self.children:
            item.disabled = True

    @discord.ui.button(label="🎰 Grebi!", style=discord.ButtonStyle.primary)
    async def scratch_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.active:
            await interaction.response.send_message("❌ Igra je gotova!", ephemeral=True)
            return

        symbols, prize, prize_emoji = scratch()
        self.total_plays += 1
        self.recent[interaction.user.id] = {"prize": prize, "prize_emoji": prize_emoji}

        grid = render_grid(symbols)
        await interaction.response.send_message(
            f"🎰 **Tvoja Grebalica:**\n\n{grid}\n\n{prize_emoji} {prize}",
            ephemeral=True,
        )

        embed = build_embed(self.total_plays, self.recent)
        if self.message:
            await self.message.edit(embed=embed, view=self)


class Grebalica:
    name = "Grebalica"
    emoji = "🎰"

    @staticmethod
    async def start(channel: discord.TextChannel):
        view = GrebalicaView()
        embed = build_embed(0, {})
        msg = await channel.send(embed=embed, view=view)
        view.message = msg
        return view, msg

    @staticmethod
    async def stop(view, message):
        view.active = False
        view.disable_all()
        embed = build_embed(view.total_plays, view.recent)
        await message.edit(embed=embed, view=view)
