from __future__ import annotations

from typing import TYPE_CHECKING

from nextcord import Color, Embed, Forbidden, HTTPException, Member, SlashOption, utils

from enums import Emojis
from utilities import Avatars, CustomCog, CustomInteraction

from .__main__ import EconomyCog, EconomyManager

if TYPE_CHECKING:
    from bot import Smiffy


class CommandPay(CustomCog):
    @EconomyCog.main.subcommand(  # pylint: disable=no-member
        name="przelej",
        description="Przelewa wybranej osobie określoną kwotę",
    )
    async def economy_pay(
        self,
        interaction: CustomInteraction,
        member: Member = SlashOption(
            name="osoba",
            description="Podaj osobę do której chcesz przelać pieniądze",
        ),
        amount: int = SlashOption(
            name="kwota",
            description="Podaj kwotę, którą chcesz przelać",
        ),
    ):
        assert isinstance(interaction.user, Member) and interaction.guild
        await interaction.response.defer()
        amount = abs(amount)

        if member.bot:
            return await interaction.send_error_message(description="Boty nie posiadają kont bankowych.")

        manager: EconomyManager = EconomyManager(bot=self.bot)

        if not await manager.get_guild_economy_status(interaction.guild):
            return await interaction.send_error_message(description="Ekonomia na serwerze jest wyłączona.")

        (
            user_money,
            user_bank_money,  # pylint: disable=unused-variable
        ) = await manager.get_user_balance(interaction.user)

        if amount > user_money:
            return await interaction.send_error_message(
                description="Nie posiadasz tylu pieniędzy w portfelu."
            )

        await manager.remove_user_money(interaction.user, amount)
        await manager.add_user_money(member, {"money": amount})

        await interaction.send_success_message(
            title=f"Pomyślnie przelano {Emojis.GREENBUTTON.value}",
            color=Color.dark_theme(),
            description=f"{Emojis.REPLY.value} Przelano `{amount}$` na konta bankowe: {member.mention}",
        )
        await self.send_dm_message(interaction.user, member, amount)

    async def send_dm_message(
        self,
        sender: Member,
        member: Member,
        amount: int,
    ) -> None:
        embed = Embed(
            title="`💡` Otrzymano nowy przelew",
            colour=Color.dark_theme(),
            timestamp=utils.utcnow(),
            description=f"{Emojis.REPLY.value} Serwer: **{member.guild}**",
        )
        embed.add_field(
            name="`👤` Nadawca",
            value=f"{Emojis.REPLY.value} `{sender}`",
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
    bot.add_cog(CommandPay(bot))
