from __future__ import annotations
from typing import TYPE_CHECKING, Any, Optional
from typing_extensions import Unpack

from nextcord import TextChannel, errors

from utilities import CustomCog, bot_utils
from errors import InvalidServerData

if TYPE_CHECKING:

    from bot import Smiffy
    from typings import HTTPRatelimitParams

    from nextcord.abc import GuildChannel


class HttpRatelimit(CustomCog):

    async def send_ratelimit_notify_to_channel(self, **kwargs: Any):
        channel_id: Optional[int] = bot_utils.get_value_from_config("ERRORS_CHANNEL_NOTIFY")

        if not isinstance(channel_id, int):
            raise InvalidServerData

        if isinstance(channel_id, int):
            channel: Optional[GuildChannel] = await self.bot.getch_channel(channel_id)

            if not isinstance(channel, TextChannel):
                raise InvalidServerData

            try:
                await channel.send(f"`🌟` **Reached HTTP Ratelimit.**\n- {kwargs}")
            except (errors.Forbidden, errors.HTTPException):
                self.bot.logger.warning("Failed to send Ratelimit notify.")

    @CustomCog.listener()
    async def on_http_ratelimit(self, *args: Unpack[HTTPRatelimitParams]):
        limit: int = args[0]
        remaining: int = args[1]
        reset_after: float = args[2]
        bucket: str = args[3]

        self.bot.logger.warning(f"Reached HTTP Ratelimit under bucket: {bucket}.")
        self.bot.logger.warning(f"Remaining requests: {remaining}. Reset after: {reset_after}s.")

        await self.send_ratelimit_notify_to_channel(limit=limit, remaining=remaining,
                                                    reset_after=reset_after, bucket=bucket)

    @CustomCog.listener()
    async def on_global_http_ratelimit(self, retry_after: float):
        self.bot.logger.warning("Reached Global HTTP Ratelimit.")
        self.bot.logger.warning(f"Retry after: {retry_after}.")

        await self.send_ratelimit_notify_to_channel(retry_after=retry_after)


def setup(bot: Smiffy):
    bot.add_cog(HttpRatelimit(bot))
