from __future__ import annotations

from datetime import timedelta
from time import time
from typing import TYPE_CHECKING, Optional

from nextcord import ButtonStyle, Color, Embed, ui, utils

from enums import Emojis
from utilities import CustomCog, DiscordSupportButton

if TYPE_CHECKING:
    from nextcord import Message, ShardInfo

    from bot import Smiffy


class ButtonsView(DiscordSupportButton):
    def __init__(self):
        super().__init__()

        self.add_item(
            ui.Button(
                style=ButtonStyle.link,
                url="https://smiffybot.pl/",
                label="Strona Bota",
                disabled=True,
            )
        )


class BotMention(CustomCog):
    def __init__(self, bot: Smiffy) -> None:
        super().__init__(bot)

        self.bot_startup = time()

    @CustomCog.listener()
    async def on_bot_mention(self, message: Message) -> None:
        if not self.bot.user:
            return

        async with message.channel.typing():
            commands: int = len(self.bot.get_all_application_commands())

            reply_emoji: str = "<:reply:1129168370642718833>"
            _members: int = sum((guild.member_count for guild in self.bot.guilds))  # pyright: ignore
            _guilds: int = len(self.bot.guilds)
            help_mention: str = "</help:1040624807768752188>"

            description: str = f"""
## <a:hello:1129534241617739866> Cześć! Nazywam się Smiffy.
{Emojis.REPLY.value} **Pozwól, że pomogę ci skonfigurować Twój serwer.** \
Moje komendy sprawdzisz używając {help_mention}
"""

            embed = Embed(
                color=Color.dark_theme(),
                description=description,
                timestamp=utils.utcnow(),
            )

            if not message.guild:
                return

            shard_id: int = message.guild.shard_id
            shard: Optional[ShardInfo] = self.bot.get_shard(shard_id)

            if not shard:
                return

            latecy: int = round(shard.latency * 1000)

            uptime = str(timedelta(seconds=int(round(time() - self.bot_startup))))
            embed.add_field(
                name="`🌐` Ping",
                value=f"{reply_emoji} `{latecy}ms`",
            )
            embed.add_field(
                name="`〽️` UpTime",
                value=f"{reply_emoji} `{uptime}`",
            )
            embed.add_field(
                name="`🔧` Komendy",
                value=f"{reply_emoji} `{commands}`",
            )
            embed.add_field(
                name="`🧠` Serwery",
                value=f"{reply_emoji} `{_guilds}`",
            )

            embed.add_field(
                name="`👥` Użytkownicy",
                value=f"{reply_emoji} `{_members}`",
            )
            embed.add_field(
                name="`🛠️` Shard",
                value=f"{reply_emoji} `{shard.id + 1}`",
            )

            embed.set_author(
                name=message.author,
                icon_url=self.avatars.get_user_avatar(message.author),
            )

            embed.set_thumbnail(url=self.avatars.get_guild_icon(message.guild))

            opinion = ButtonsView()
            await message.reply(embed=embed, view=opinion)


def setup(bot: Smiffy):
    bot.add_cog(BotMention(bot))
