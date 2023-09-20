from __future__ import annotations
from typing import TYPE_CHECKING, Optional

from time import mktime
from nextcord import Embed, Color, utils, slash_command

from utilities import CustomInteraction, CustomCog
from enums import Emojis

if TYPE_CHECKING:
    from bot import Smiffy
    from nextcord import Member


class CommandSerwer(CustomCog):
    @slash_command(
        name="serwerinfo",
        description="Pokazuje informacje o serwerze",
        dm_permission=False,
    )
    async def serwer(self, interaction: CustomInteraction):
        assert interaction.guild and interaction.guild.owner_id

        guild_name: str = interaction.guild.name

        guild_owner: Optional[Member] = await self.bot.getch_member(
            interaction.guild, interaction.guild.owner_id
        )

        if not guild_owner:
            return await interaction.send_error_message(description="Wystąpił nieoczekiwany błąd.")

        guild_created_at: str = f"<t:{int(mktime(interaction.guild.created_at.timetuple()))}:R>"

        guild_boosts: int = interaction.guild.premium_subscription_count

        guild_members: str = (
            f"{interaction.guild.member_count - len(interaction.guild.bots)}"
            if interaction.guild.member_count
            else "0"
        )

        guild_bots: str = f"{len(interaction.guild.bots)}"
        guild_roles: str = f"{len(interaction.guild.roles)}"
        guild_text_channels: str = f"{len(interaction.guild.text_channels)}"
        guild_voice_channels: str = f"{len(interaction.guild.voice_channels)}"

        reply_emoji: str = Emojis.REPLY.value

        embed = Embed(
            title=f"`📃` Informacje o serwerze: {interaction.guild.name}",
            color=Color.dark_theme(),
            timestamp=utils.utcnow(),
        )
        embed.set_author(name=interaction.user, icon_url=interaction.user_avatar_url)
        embed.set_thumbnail(url=interaction.guild_icon_url)

        embed.add_field(name="`📝` Nazwa Serwera", value=f"{reply_emoji} `{guild_name}`")

        embed.add_field(name="`👑` Właściciel", value=f"{reply_emoji} {guild_owner.mention}")

        embed.add_field(name="`🔗` Wiek serwera", value=f"{reply_emoji} {guild_created_at}")

        embed.add_field(name="`✨` Boosty", value=f"{reply_emoji} `{guild_boosts}`")

        embed.add_field(name="`💬` Kanały Tekstowe", value=f"{reply_emoji} `{guild_text_channels}`")

        embed.add_field(name="`📞` Kanały Głosowe", value=f"{reply_emoji} `{guild_voice_channels}`")

        embed.add_field(name="`👥` Osoby", value=f"{reply_emoji} `{guild_members}`")

        embed.add_field(name="`🤖` Boty", value=f"{reply_emoji} `{guild_bots}`")

        embed.add_field(name="`⭐` Role", value=f"{reply_emoji} `{guild_roles}`")

        embed.set_footer(text=f"Smiffy v{self.bot.__version__}", icon_url=self.bot.avatar_url)
        await interaction.send(embed=embed)


def setup(bot: Smiffy):
    bot.add_cog(CommandSerwer(bot))
