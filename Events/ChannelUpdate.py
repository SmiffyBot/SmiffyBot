from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from nextcord import AuditLogAction, Color, Embed, Member, TextChannel, errors, utils

from enums import Emojis
from utilities import CustomCog

if TYPE_CHECKING:
    from nextcord.abc import GuildChannel

    from bot import Smiffy


class ChannelUpdate(CustomCog):
    @CustomCog.listener()
    async def on_guild_channel_create(self, new_channel: GuildChannel):

        await self.bot.cache.add_channel(
            guild_id=new_channel.guild.id,
            channel=new_channel
        )

        logs_channel: Optional[GuildChannel] = await self.get_logs_channel(new_channel.guild)

        if not isinstance(logs_channel, TextChannel):
            return

        author: Optional[Member] = None
        async for entry in new_channel.guild.audit_logs(
            action=AuditLogAction.channel_create,
            limit=1,
        ):
            if not isinstance(entry.user, Member):
                return

            author = entry.user

        embed = Embed(
            title=f"Stworzono nowy kanał {Emojis.GREENBUTTON.value}",
            timestamp=utils.utcnow(),
            colour=Color.green(),
        )
        embed.set_footer(
            text=f"Smiffy v{self.bot.__version__}",
            icon_url=self.bot.avatar_url,
        )

        embed.set_thumbnail(url=self.avatars.get_guild_icon(new_channel.guild))

        embed.add_field(
            name="`🗨️` Kanał",
            value=f"{Emojis.REPLY.value} {new_channel.mention}",
            inline=False,
        )

        if author:
            embed.set_author(
                name=author,
                icon_url=author.display_avatar.url,
            )

            embed.add_field(
                name="`👤` Autor",
                value=f"{Emojis.REPLY.value} {author.mention}",
            )
        else:
            embed.set_author(
                name=self.bot.user,
                icon_url=self.bot.avatar_url,
            )

        try:
            await logs_channel.send(embed=embed)
        except (
            errors.HTTPException,
            errors.Forbidden,
        ):
            pass

    @CustomCog.listener()
    async def on_guild_channel_delete(self, deleted_channel: GuildChannel):
        await self.bot.cache.remove_channel(deleted_channel.guild.id, deleted_channel.id)

        logs_channel: Optional[GuildChannel] = await self.get_logs_channel(deleted_channel.guild)

        if not isinstance(logs_channel, TextChannel):
            return

        author: Optional[Member] = None

        async for entry in deleted_channel.guild.audit_logs(
            action=AuditLogAction.channel_delete,
            limit=1,
        ):
            if not isinstance(entry.user, Member):
                return

            author = entry.user

        embed = Embed(
            title=f"Usunięto kanał {Emojis.REDBUTTON.value}",
            timestamp=utils.utcnow(),
            colour=Color.red(),
        )
        embed.set_thumbnail(url=self.avatars.get_guild_icon(deleted_channel.guild))
        embed.set_footer(
            text=f"Smiffy v{self.bot.__version__}",
            icon_url=self.bot.avatar_url,
        )

        embed.add_field(
            name="`🗨️` Kanał",
            value=f"{Emojis.REPLY.value} {deleted_channel}",
            inline=False,
        )

        if author:
            embed.set_author(
                name=author,
                icon_url=author.display_avatar.url,
            )

            embed.add_field(
                name="`👤` Usuwajacy",
                value=f"{Emojis.REPLY.value} {author.mention}",
            )
        else:
            embed.set_author(
                name=self.bot.user,
                icon_url=self.bot.avatar_url,
            )

        try:
            await logs_channel.send(embed=embed)
        except (
            errors.HTTPException,
            errors.Forbidden,
        ):
            pass


def setup(bot: Smiffy):
    bot.add_cog(ChannelUpdate(bot))
