from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from nextcord import Color, Embed, Member, Message, TextChannel, Thread, errors, utils

from enums import Emojis
from utilities import CustomCog

if TYPE_CHECKING:
    from nextcord.abc import GuildChannel

    from bot import Smiffy


class MessageDelete(CustomCog):
    @CustomCog.listener()
    async def on_message_delete(self, message: Message):
        if not isinstance(message.channel, (Thread, TextChannel)):
            return

        assert isinstance(message.author, Member) and message.guild

        await self.bot.db.execute_fetchone(
            "DELETE FROM reactionroles WHERE guild_id = ? AND message_id = ?",
            (message.guild.id, message.id),
        )

        await self.bot.db.execute_fetchone(
            "DELETE FROM verifications WHERE guild_id = ? AND message_id = ?",
            (message.guild.id, message.id),
        )

        await self.bot.db.execute_fetchone(
            "DELETE FROM tickets WHERE guild_id = ? AND message_id = ?",
            (message.guild.id, message.id),
        )

        if not message.author.bot:
            logs_channel: Optional[GuildChannel] = await self.get_logs_channel(message.guild)

            if isinstance(logs_channel, TextChannel) and message.content:
                embed = Embed(
                    title="<:messagedeleted:992419774221013024> Usunięta wiadomość!",
                    color=Color.red(),
                    timestamp=utils.utcnow(),
                )
                message_content: str = message.content.replace("`", "")

                embed.add_field(
                    name="`📂` Kanał",
                    value=f"{Emojis.REPLY.value} {message.channel.mention}",
                )

                embed.add_field(
                    name="`💬` Treść",
                    value=f"{Emojis.REPLY.value} {message_content}",
                    inline=False,
                )

                embed.set_author(
                    name=message.author,
                    icon_url=self.avatars.get_user_avatar(message.author),
                )
                embed.set_thumbnail(url=self.avatars.get_guild_icon(message.guild))
                embed.set_footer(text=f"Smiffy v{self.bot.__version__}", icon_url=self.bot.avatar_url)

                try:
                    await logs_channel.send(embed=embed)
                except (errors.Forbidden, errors.HTTPException):
                    pass

        ghostping_response = await self.bot.db.execute_fetchone(
            "SELECT * FROM antyghostping WHERE guild_id = ?", (message.guild.id,)
        )

        permissions: bool = message.author.guild_permissions.manage_messages

        if not permissions:
            if ghostping_response and message.mentions or message.mention_everyone:
                author_mention: str = message.author.mention

                embed = Embed(
                    title=f"Wykryto GhostPing {Emojis.REDBUTTON.value}",
                    color=Color.red(),
                    description=f"{Emojis.REPLY.value} {author_mention} usunął wiadomość zawiarającą oznaczenie/a."
                    f"\n\n*Wiadomość zostanie automatycznie usunięta za 6h.*",
                    timestamp=utils.utcnow(),
                )
                embed.set_author(
                    name=message.author,
                    icon_url=self.avatars.get_user_avatar(message.author),
                )
                embed.set_thumbnail(url=self.avatars.get_guild_icon(message.guild))

                embed.set_footer(text=f"Smiffy v{self.bot.__version__}", icon_url=self.bot.avatar_url)

                try:
                    await message.channel.send(embed=embed, delete_after=21600)
                except (errors.HTTPException, errors.Forbidden):
                    pass


def setup(bot: Smiffy):
    bot.add_cog(MessageDelete(bot))
