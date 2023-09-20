from __future__ import annotations
from typing import TYPE_CHECKING, Optional

from nextcord import Embed, Color, utils, errors, TextChannel

from utilities import CustomCog
from enums import Emojis

if TYPE_CHECKING:
    from bot import Smiffy

    from nextcord.abc import GuildChannel
    from nextcord import Message


class MessageEdit(CustomCog):
    @CustomCog.listener()
    async def on_message_edit(self, before: Message, after: Message):
        assert after.guild

        if before.author.bot or before.content == after.content:
            return

        logs_channel: Optional[GuildChannel] = await self.get_logs_channel(after.guild)

        if isinstance(logs_channel, TextChannel):
            embed = Embed(
                title="<a:messageicon:992174529675804742> Wiadomość została edytowana.",
                color=Color.dark_theme(),
                description=f"{Emojis.REPLY.value} Wiadomość: [Link]({after.jump_url})",
                timestamp=utils.utcnow(),
            )

            embed.set_author(name=after.author, icon_url=self.avatars.get_user_avatar(after.author))
            embed.set_thumbnail(url=self.avatars.get_guild_icon(after.guild))

            before_content, after_content = before.content.replace("`", ""), after.content.replace("`", "")

            embed.add_field(name="`🔴` Wcześniej", value=f"- ```{before_content}```", inline=False)

            embed.add_field(name="`🟢` Aktualnie", value=f"- ```{after_content}```")

            try:
                await logs_channel.send(embed=embed)
            except (errors.Forbidden, errors.HTTPException):
                pass


def setup(bot: Smiffy):
    bot.add_cog(MessageEdit(bot))
