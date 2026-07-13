import random
import asyncio
import discord

TOTAL_NUMBERS = 30
CALL_INTERVAL = 20  # seconds


def generate_card():
    pool = list(range(1, TOTAL_NUMBERS + 1))
    random.shuffle(pool)
    return pool[:9]


def render_card(card, called):
    rows = []
    for i in range(3):
        row = []
        for j in range(3):
            n = card[i * 3 + j]
            row.append(f"~~`{n:02d}`~~" if n in called else f"`{n:02d}`")
        rows.append(" ".join(row))
    return "\n".join(rows)


def check_bingo(card, called):
    lines = [
        [0, 1, 2], [3, 4, 5], [6, 7, 8],
        [0, 3, 6], [1, 4, 7], [2, 5, 8],
        [0, 4, 8], [2, 4, 6],
    ]
    return any(all(card[i] in called for i in line) for line in lines)


def build_embed(called, players, winner=None, round_num=0):
    last = called[-5:] if called else []
    last_str = " ".join(f"`{n}`" for n in last) if last else "Čekamo..."

    if winner:
        color = discord.Color.green()
        desc = f"🏆 <@{winner}> je pobijedio/la! **BINGO!**"
    else:
        color = discord.Color.purple()
        desc = "Skupi karticu i čekaj svoja polja! Kad budeš imao red — stisni BINGO!"

    embed = discord.Embed(title="🎱 Bingo!", description=desc, color=color)
    embed.add_field(name="🔢 Izvučeni brojevi", value=last_str, inline=False)
    embed.add_field(name="👥 Igrači", value=f"{len(players)} u igri" if players else "Nitko još", inline=True)
    embed.add_field(name="🔄 Runda", value=str(round_num), inline=True)
    embed.set_footer(text="SQUAD Bot • Uzmi karticu i igraj Bingo!")
    return embed


class BingoView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.called = []
        self.players = {}  # user_id -> card (list of 9 ints)
        self.pool = list(range(1, TOTAL_NUMBERS + 1))
        random.shuffle(self.pool)
        self.winner = None
        self.active = True
        self.round = 0
        self.message = None
        self._task = None

    def disable_all(self):
        for item in self.children:
            item.disabled = True

    async def call_loop(self):
        while self.active and self.pool:
            await asyncio.sleep(CALL_INTERVAL)
            if not self.active or not self.pool:
                break
            num = self.pool.pop()
            self.called.append(num)
            self.round += 1
            if self.message:
                embed = build_embed(self.called, self.players, round_num=self.round)
                try:
                    await self.message.edit(embed=embed, view=self)
                except Exception:
                    pass

    @discord.ui.button(label="🎟️ Uzmi karticu", style=discord.ButtonStyle.success)
    async def join_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.active:
            await interaction.response.send_message("❌ Igra je gotova!", ephemeral=True)
            return
        uid = interaction.user.id
        if uid in self.players:
            await interaction.response.send_message(
                "✅ Već imaš karticu! Klikni **Moja kartica**.", ephemeral=True
            )
            return
        card = generate_card()
        self.players[uid] = card
        called_set = set(self.called)
        card_str = render_card(card, called_set)
        await interaction.response.send_message(
            f"🎟️ Tvoja Bingo kartica:\n\n{card_str}\n\nPrati izvučene brojeve i stisni **BINGO!** kad popuniš red!",
            ephemeral=True,
        )
        if self.message:
            embed = build_embed(self.called, self.players, round_num=self.round)
            await self.message.edit(embed=embed, view=self)

    @discord.ui.button(label="📋 Moja kartica", style=discord.ButtonStyle.secondary)
    async def card_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        uid = interaction.user.id
        card = self.players.get(uid)
        if not card:
            await interaction.response.send_message(
                "❌ Nemaš karticu! Klikni **Uzmi karticu** prvo.", ephemeral=True
            )
            return
        called_set = set(self.called)
        card_str = render_card(card, called_set)
        called_str = " ".join(f"`{n}`" for n in self.called) if self.called else "Nitko još nije pozvan"
        await interaction.response.send_message(
            f"📋 Tvoja kartica:\n\n{card_str}\n\n🔢 Izvučeni: {called_str}",
            ephemeral=True,
        )

    @discord.ui.button(label="🎉 BINGO!", style=discord.ButtonStyle.primary)
    async def bingo_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.active:
            await interaction.response.send_message("❌ Igra je gotova!", ephemeral=True)
            return
        uid = interaction.user.id
        card = self.players.get(uid)
        if not card:
            await interaction.response.send_message(
                "❌ Nemaš karticu! Klikni **Uzmi karticu** prvo.", ephemeral=True
            )
            return
        called_set = set(self.called)
        if check_bingo(card, called_set):
            self.winner = uid
            self.active = False
            self.disable_all()
            if self._task:
                self._task.cancel()
            embed = build_embed(self.called, self.players, winner=uid, round_num=self.round)
            await interaction.response.edit_message(embed=embed, view=self)
        else:
            await interaction.response.send_message(
                "❌ Još nemaš Bingo! Nastavi čekati brojeve.", ephemeral=True
            )


class BingoGame:
    name = "Bingo"
    emoji = "🎱"

    @staticmethod
    async def start(channel: discord.TextChannel):
        view = BingoView()
        embed = build_embed([], {}, round_num=0)
        msg = await channel.send(embed=embed, view=view)
        view.message = msg
        view._task = asyncio.create_task(view.call_loop())
        return view, msg

    @staticmethod
    async def stop(view, message):
        view.active = False
        if view._task:
            view._task.cancel()
        view.disable_all()
        embed = build_embed(view.called, view.players, round_num=view.round)
        await message.edit(embed=embed, view=view)
