from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from nextcord import AuditLogAction, Color, Embed, Role, TextChannel, errors, utils

from enums import Emojis
from utilities import CustomCog

if TYPE_CHECKING:
    from nextcord.abc import GuildChannel

    from bot import Smiffy


class RoleUpdate(CustomCog):
    @CustomCog.listener()
    async def on_guild_role_create(self, role: Role):
        logs_channel: Optional[GuildChannel] = await self.get_logs_channel(role.guild)

        if isinstance(logs_channel, TextChannel):
            async for entry in logs_channel.guild.audit_logs(
                action=AuditLogAction.role_create,
                limit=1,
            ):
                user = entry.user

                embed = Embed(
                    title=f"Utworzono role {Emojis.GREENBUTTON.value}",
                    color=Color.green(),
                    timestamp=utils.utcnow(),
                )

                embed.add_field(
                    name="`📃` Mazwa",
                    value=f"{Emojis.REPLY.value} {role.mention}",
                    inline=False,
                )

                embed.add_field(
                    name="`⚙️` Identyfikator",
                    value=f"{Emojis.REPLY.value} `{role.id}`",
                )

                embed.set_author(
                    name=user,
                    icon_url=self.avatars.get_user_avatar(user),
                )
                embed.set_thumbnail(url=self.avatars.get_guild_icon(role.guild))

                try:
                    await logs_channel.send(embed=embed)
                except errors.Forbidden:
                    pass

    @CustomCog.listener()
    async def on_guild_role_update(self, before: Role, after: Role):
        logs_channel: Optional[GuildChannel] = await self.get_logs_channel(before.guild)

        new_name: Optional[str] = None
        new_color: Optional[Color] = None

        if isinstance(logs_channel, TextChannel):
            if before.name != after.name:
                new_name = after.name

            if before.color != after.color:
                new_color = after.color

            if not new_color and not new_name:
                return

            async for entry in before.guild.audit_logs(
                action=AuditLogAction.role_update,
                limit=1,
            ):
                user = entry.user

                embed = Embed(
                    title="`〽️` Zaktualizowano role!",
                    color=Color.green(),
                    timestamp=utils.utcnow(),
                )
                embed.description = str()

                embed.add_field(
                    name="`⚙️` Identyfikator",
                    value=f"{Emojis.REPLY.value} `{after.id}`",
                    inline=False,
                )

                if new_name:
                    embed.description += f"- Stara nazwa: `{before.name}`"

                    embed.add_field(
                        name="`✉️` Nowa nazwa",
                        value=f"{Emojis.REPLY.value} `{after.name}`",
                    )

                if new_color:
                    embed.description += f"\n- Stary kolor: `{before.color}`"

                    embed.add_field(
                        name="`🟢` Stary kolor",
                        value=f"{Emojis.REPLY.value} `{before.color}`",
                    )

                embed.set_author(
                    name=user,
                    icon_url=self.avatars.get_user_avatar(user),
                )
                embed.set_thumbnail(url=self.avatars.get_guild_icon(after.guild))

                try:
                    await logs_channel.send(embed=embed)
                except errors.Forbidden:
                    pass

    @CustomCog.listener()
    async def on_guild_role_delete(self, role: Role):
        logs_channel: Optional[GuildChannel] = await self.get_logs_channel(role.guild)

        if isinstance(logs_channel, TextChannel):
            async for entry in logs_channel.guild.audit_logs(
                action=AuditLogAction.role_delete,
                limit=1,
            ):
                user = entry.user

                embed = Embed(
                    title=f"Usunięto role {Emojis.REDBUTTON.value}",
                    color=Color.red(),
                    timestamp=utils.utcnow(),
                    description=f"- Nazwa: `{role.name}`",
                )

                embed.add_field(
                    name="`⚙️` Identyfikator",
                    value=f"{Emojis.REPLY.value} `{role.id}`",
                    inline=False,
                )
                embed.add_field(
                    name="`🔵` Kolor",
                    value=f"{Emojis.REPLY.value} `{role.color}`",
                )

                embed.set_author(
                    name=user,
                    icon_url=self.avatars.get_user_avatar(user),
                )
                embed.set_thumbnail(url=self.avatars.get_guild_icon(role.guild))

                try:
                    await logs_channel.send(embed=embed)
                except errors.Forbidden:
                    pass


def setup(bot: Smiffy):
    bot.add_cog(RoleUpdate(bot))
