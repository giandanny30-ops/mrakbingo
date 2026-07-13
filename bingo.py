import random
import discord


def build_embed(secret, attempts, signal, winner=None, stopped=False):
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


class GuessModal(discord.ui.Modal, title="Pogodi broj (1-100)"):
    number = discord.ui.TextInput(
        label="Unesi broj od 1 do 100",
        placeholder="npr. 42",
        min_length=1,
        max_length=3,
    )

    def __init__(self, view):
        super().__init__()
        self.game_view = view

    async def on_submit(self, interaction: discord.Interaction):
        try:
            guess = int(self.number.value.strip())
            if guess < 1 or guess > 100:
                raise ValueError
        except ValueError:
            await interaction.response.send_message(
                "❌ Unesi validan broj između 1 i 100!", ephemeral=True
            )
            return

        v = self.game_view
        v.attempts += 1
        diff = abs(guess - v.secret)

        if diff == 0:
            v.winner = interaction.user.id
            v.active = False
            embed = build_embed(v.secret, v.attempts, "", winner=interaction.user.id)
            v.disable_all()
            await interaction.response.edit_message(embed=embed, view=v)
            return

        if diff <= 5:
            signal = f"🔥 Prevrelo! (tvoj broj: `{guess}`)"
        elif diff <= 15:
            signal = f"♨️ Toplije! (tvoj broj: `{guess}`)"
        elif diff <= 30:
            signal = f"🌤️ Hladnije... (tvoj broj: `{guess}`)"
        else:
            signal = f"🧊 Hladno! (tvoj broj: `{guess}`)"

        v.signal = f"<@{interaction.user.id}> — {signal}"
        embed = build_embed(v.secret, v.attempts, v.signal)
        await interaction.response.edit_message(embed=embed, view=v)


class ToploHladnoView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.secret = random.randint(1, 100)
        self.attempts = 0
        self.signal = ""
        self.winner = None
        self.active = True

    def disable_all(self):
        for item in self.children:
            item.disabled = True

    @discord.ui.button(label="🌡️ Pogodi broj", style=discord.ButtonStyle.primary)
    async def guess_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.active:
            await interaction.response.send_message("❌ Igra je gotova!", ephemeral=True)
            return
        await interaction.response.send_modal(GuessModal(self))

    @discord.ui.button(label="🎯 Završi igru", style=discord.ButtonStyle.danger)
    async def stop_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.active:
            await interaction.response.send_message("❌ Igra je već gotova!", ephemeral=True)
            return
        self.active = False
        self.disable_all()
        embed = build_embed(self.secret, self.attempts, "", stopped=True)
        await interaction.response.edit_message(embed=embed, view=self)


class ToploHladnoGame:
    name = "Toplo-Hladno"
    emoji = "☀️"

    @staticmethod
    async def start(channel: discord.TextChannel):
        view = ToploHladnoView()
        embed = build_embed(view.secret, 0, "")
        msg = await channel.send(embed=embed, view=view)
        return view, msg

    @staticmethod
    async def stop(view, message):
        if not view.active:
            return
        view.active = False
        view.disable_all()
        embed = build_embed(view.secret, view.attempts, "", stopped=True)
        await message.edit(embed=embed, view=view)
