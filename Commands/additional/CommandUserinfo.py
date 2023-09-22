from __future__ import annotations

from time import mktime
from typing import TYPE_CHECKING

from nextcord import Color, Embed, Member, slash_command, user_command, utils

from enums import Emojis
from utilities import CustomCog, CustomInteraction

if TYPE_CHECKING:
    from nextcord import Role

    from bot import Smiffy


class CommandUserInfo(CustomCog):
    @user_command(name="userinfo")
    async def userinfo_application(
        self,
        interaction: CustomInteraction,
        member: Member,
    ) -> None:
        await self.userinfo(interaction, member)

    @slash_command(
        name="userinfo",
        description="Pokazuje informacje na temat użytkownika.",
        dm_permission=False,
    )
    async def userinfo(
        self,
        interaction: CustomInteraction,
        member: Member,
    ) -> None:
        if member.joined_at:
            account_joined_at: str = f"<t:{int(mktime(member.joined_at.timetuple()))}:R>"
        else:
            account_joined_at: str = "None"

        account_created_at: str = f"<t:{int(mktime(member.created_at.timetuple()))}:R>"
        account_id: int = member.id
        account_top_role: Role = member.top_role
        account_nickname: str = f"{member.display_name}"
        account_roles_amount: int = len(member.roles)

        reply_emoji: str = Emojis.REPLY.value

        embed = Embed(
            title=f"Informacje o: {member.name}",
            color=Color.dark_theme(),
            timestamp=utils.utcnow(),
        )
        embed.set_author(
            name=interaction.user,
            icon_url=interaction.user_avatar_url,
        )
        embed.set_thumbnail(url=interaction.guild_icon_url)

        embed.add_field(
            name="`📝` Nick",
            value=f"{reply_emoji} `{member}`",
        )

        embed.add_field(
            name="`🔖` Pseudonim",
            value=f"{reply_emoji} `{account_nickname}`",
        )

        embed.add_field(
            name="`💫` Ilość ról",
            value=f"{reply_emoji} `{account_roles_amount}`",
        )

        embed.add_field(
            name="`⏰` Wiek Konta",
            value=f"{reply_emoji} {account_created_at}",
        )

        embed.add_field(
            name="`⌛` Dołączył na serwer",
            value=f"{reply_emoji} {account_joined_at}",
        )

        embed.add_field(
            name="`⚡` Najwyższa rola",
            value=f"{reply_emoji} {account_top_role.mention}",
        )

        embed.add_field(
            name="`⚙️` ID",
            value=f"{reply_emoji} `{account_id}`",
        )

        embed.set_footer(
            text=f"Smiffy v{self.bot.__version__}",
            icon_url=self.bot.avatar_url,
        )

        await interaction.send(embed=embed)


def setup(bot: Smiffy):
    bot.add_cog(CommandUserInfo(bot))
