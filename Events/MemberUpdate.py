from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from nextcord import Color, Embed, TextChannel, errors, utils

from enums import Emojis
from utilities import CustomCog

if TYPE_CHECKING:
    from nextcord import Member
    from nextcord.abc import GuildChannel

    from bot import Smiffy


class MemberUpdate(CustomCog):
    @CustomCog.listener()
    async def on_member_update(self, before: Member, after: Member):
        if before.roles != after.roles:
            logs_channel: Optional[GuildChannel] = await self.get_logs_channel(after.guild)

            if not isinstance(logs_channel, TextChannel):
                return

            deleted_roles: list[str] = []
            added_roles: list[str] = []

            for _role in tuple(before.roles + after.roles):
                if _role not in after.roles:
                    deleted_roles.append(_role.mention)

                if _role not in before.roles:
                    added_roles.append(_role.mention)

            if not deleted_roles and not added_roles:
                return

            embed = Embed(
                title="<a:ping:987762816062726224> Użytkownik zaktualizował role.",
                timestamp=utils.utcnow(),
                colour=Color.dark_theme(),
            )

            if len(deleted_roles) > 0:
                embed.add_field(
                    name="`➖` Usunięte role",
                    value=f"{Emojis.REPLY.value} {' '.join(deleted_roles)}",
                    inline=False,
                )

            if len(added_roles) > 0:
                embed.add_field(
                    name="`➕` Dodane role",
                    value=f"{Emojis.REPLY.value} {' '.join(added_roles)}",
                    inline=False,
                )

            embed.set_author(
                name=after,
                icon_url=self.avatars.get_user_avatar(after),
            )
            embed.set_thumbnail(url=self.avatars.get_guild_icon(after.guild))
            embed.set_footer(
                text=f"Smiffy v{self.bot.__version__}",
                icon_url=self.bot.avatar_url,
            )

            try:
                await logs_channel.send(embed=embed)
            except (
                errors.Forbidden,
                errors.HTTPException,
            ):
                pass


def setup(bot: Smiffy):
    bot.add_cog(MemberUpdate(bot))
