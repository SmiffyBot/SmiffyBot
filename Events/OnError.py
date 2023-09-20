from __future__ import annotations
from typing import TYPE_CHECKING, Optional, Any

from traceback import format_exception
from nextcord import TextChannel

from utilities import CustomCog, CustomInteraction, bot_utils
from errors import InvalidServerData

if TYPE_CHECKING:
    from bot import Smiffy

    from nextcord import BaseApplicationCommand, SlashApplicationSubcommand
    from nextcord.abc import GuildChannel


class OnError(CustomCog):
    def __init__(self, bot: Smiffy):
        super().__init__(bot)

        self.channel_id: Optional[int] = bot_utils.get_value_from_config("ERRORS_CHANNEL_NOTIFY")

        if not isinstance(self.channel_id, int):
            raise InvalidServerData

    async def send_error_log_to_channel(self, exception: Any, *args: Any):
        if isinstance(self.channel_id, int):
            channel: Optional[GuildChannel] = await self.bot.getch_channel(self.channel_id)

            if not isinstance(channel, TextChannel):
                raise InvalidServerData

            await channel.send(f"`❌` **An error occurred:** {exception}\n- `{args}`")

    @CustomCog.listener()
    async def on_application_command_error(self, inter: CustomInteraction, exception: Exception):
        exception_traceback: str = "".join(
            format_exception(type(exception), exception, exception.__traceback__)
        )
        if isinstance(exception, self.bot.ignore_exceptions):
            self.bot.logger.debug(f"Ignoring exception: {type(exception)}.")
            return

        guild: str = inter.guild.name if inter.guild else "None"
        guild_id: int = 0 if not inter.guild else inter.guild.id

        command: Optional[BaseApplicationCommand | SlashApplicationSubcommand] = inter.application_command

        command_name: str = "None" if not command else str(command.name)

        exception_traceback: str = "".join(
            format_exception(type(exception), exception, exception.__traceback__)
        )

        self.bot.logger.error(
            f"An error occured: {exception}\n"
            f"• Guild: {guild} ({guild_id})\n"
            f"• Command: /{command_name}"
        )

        await self.send_error_log_to_channel(
            f"\n```{exception_traceback}```",
            f"{guild} ({guild_id})",
            f"/{command_name}",
        )

    @CustomCog.listener("on_client_error")
    async def on_client_error(self, *args, **kwargs):
        traceback: str = kwargs["traceback"]

        await self.send_error_log_to_channel(
            f"\n```{traceback}```",
            args,
        )


def setup(bot: Smiffy):
    bot.add_cog(OnError(bot))
