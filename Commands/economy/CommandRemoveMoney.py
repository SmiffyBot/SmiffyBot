from __future__ import annotations

from typing import TYPE_CHECKING

from nextcord import Color, Embed, Forbidden, HTTPException, Member, SlashOption, utils

from enums import Emojis
from utilities import Avatars, CustomCog, CustomInteraction, PermissionHandler

from .__main__ import EconomyCog, EconomyManager

if TYPE_CHECKING:
    from bot import Smiffy


class CommandRemoveMoney(CustomCog):
    @EconomyCog.main.subcommand(  # pylint: disable=no-member   # pyright: ignore
        name="usuń_pieniądze",
        description="Usuwa wybranej osobie określoną kwotę pieniędzy",
    )
    @PermissionHandler(manage_guild=True)
    async def economy_removemoney(
        self,
        interaction: CustomInteraction,
        member: Member = SlashOption(
            name="osoba",
            description="Podaj osobę której chcesz usunąć balans",
        ),
        amount: int = SlashOption(
            name="kwota",
            description="Podaj kwotę, którą chcesz usunąć",
        ),
    ):
        assert interaction.guild

        await interaction.response.defer()
        amount = abs(amount)

        if member.bot:
            return await interaction.send_error_message(description="Boty nie posiadają kont bankowych.")

        manager: EconomyManager = EconomyManager(bot=self.bot)

        if not await manager.get_guild_economy_status(interaction.guild):
            return await interaction.send_error_message(description="Ekonomia na serwerze jest wyłączona.")

        await manager.remove_user_money(user=member, amount=amount)

        await interaction.send_success_message(
            title=f"Pomyślnie zaktualizowano {Emojis.GREENBUTTON.value}",
            color=Color.dark_theme(),
            description=f"{Emojis.REPLY.value} Usunieto: `{amount}$` z portfela: {member.mention}",
        )
        await self.send_dm_message(member, amount)

    async def send_dm_message(self, member: Member, amount: int) -> None:
        embed = Embed(
            title="`📩` Otrzymano nowy rachunek do zapłaty",
            colour=Color.red(),
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
        embed.set_author(
            name=self.bot.user,
            icon_url=self.bot.avatar_url,
        )
        embed.set_thumbnail(url=Avatars.get_guild_icon(member.guild))

        try:
            await member.send(embed=embed)
        except (HTTPException, Forbidden):
            pass


def setup(bot: Smiffy):
    bot.add_cog(CommandRemoveMoney(bot))
