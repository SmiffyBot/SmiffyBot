from __future__ import annotations
from typing import TYPE_CHECKING

from nextcord import Member, SlashOption, Embed, Color, utils, HTTPException, Forbidden

from utilities import CustomInteraction, CustomCog, Avatars, PermissionHandler
from enums import Emojis

from .__main__ import EconomyCog, EconomyManager

if TYPE_CHECKING:
    from bot import Smiffy


class CommandAddMoney(CustomCog):
    @EconomyCog.main.subcommand(  # pylint: disable=no-member  # pyright: ignore
        name="dodaj_pieniądze",
        description="Dodaje wybranej osobie określoną kwotę pieniędzy",
    )
    @PermissionHandler(manage_guild=True)
    async def economy_addmoney(
        self,
        interaction: CustomInteraction,
        member: Member = SlashOption(name="osoba", description="Podaj osobę której chcesz dodać balans"),
        amount: int = SlashOption(name="kwota", description="Podaj kwotę, którą chcesz dodać"),
    ):
        assert interaction.guild

        await interaction.response.defer()
        amount = abs(amount)

        if member.bot:
            return await interaction.send_error_message(description="Boty nie posiadają kont bankowych.")

        manager: EconomyManager = EconomyManager(bot=self.bot)

        if not await manager.get_guild_economy_status(interaction.guild):
            return await interaction.send_error_message(description="Ekonomia na serwerze jest wyłączona.")

        await manager.add_user_money(user=member, money_data={"money": amount})

        await interaction.send_success_message(
            title=f"Pomyślnie zaktualizowano {Emojis.GREENBUTTON.value}",
            color=Color.dark_theme(),
            description=f"{Emojis.REPLY.value} Dodano: `{amount}$` do konta bankowego: {member.mention}",
        )
        await self.send_dm_message(member, amount)

    async def send_dm_message(self, member: Member, amount: int) -> None:
        embed = Embed(
            title="`💡` Otrzymano nowy przelew",
            colour=Color.dark_theme(),
            timestamp=utils.utcnow(),
            description=f"{Emojis.REPLY.value} Serwer: **{member.guild}**",
        )
        embed.add_field(
            name="`👤` Nadawca",
            value=f"{Emojis.REPLY.value} `WziumBank Inc`",
            inline=False,
        )

        embed.add_field(
            name="`👤` Kwota",
            value=f"{Emojis.REPLY.value} `{amount}$`",
        )
        embed.set_author(name=self.bot.user, icon_url=self.bot.avatar_url)
        embed.set_thumbnail(url=Avatars.get_guild_icon(member.guild))

        try:
            await member.send(embed=embed)
        except (HTTPException, Forbidden):
            pass


def setup(bot: Smiffy):
    bot.add_cog(CommandAddMoney(bot))
