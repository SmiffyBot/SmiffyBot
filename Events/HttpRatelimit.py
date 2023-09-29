from __future__ import annotations

from typing import TYPE_CHECKING, Any, Optional

from nextcord import TextChannel, errors
from typing_extensions import Unpack

from errors import InvalidServerData
from utilities import CustomCog, bot_utils

if TYPE_CHECKING:
    from nextcord.abc import GuildChannel

    from bot import Smiffy
    from typings import HTTPRatelimitParams


class HttpRatelimit(CustomCog):
    async def send_ratelimit_notify_to_channel(self, **kwargs: Any):
        channel_id: Optional[int] = bot_utils.get_value_from_config("ERRORS_CHANNEL_NOTIFY")

        if not isinstance(channel_id, int):
            raise InvalidServerData

        channel: Optional[GuildChannel] = await self.bot.getch_channel(channel_id)

        if not isinstance(channel, TextChannel):
            raise InvalidServerData

        try:
            await channel.send(f"`🌟` **Reached HTTP Ratelimit.**\n- {kwargs}")
        except (errors.Forbidden, errors.HTTPException):
            self.bot.logger.warning("Failed to send Ratelimit notify.")

    @CustomCog.listener()
    async def on_http_ratelimit(self, *args: Unpack[HTTPRatelimitParams]):
        limit, remaining, reset_after, bucket = args[0:-1]
        if reset_after <= 0.3:
            # Some commands make a lot of HTTP requests at once causing a small ratelimit.
            return

        self.bot.logger.warning(f"Reached HTTP Ratelimit under bucket: {bucket}.")
        self.bot.logger.warning(f"Remaining requests: {remaining}. Reset after: {reset_after}s.")

        await self.send_ratelimit_notify_to_channel(
            limit=limit, remaining=remaining, reset_after=reset_after, bucket=bucket
        )

    @CustomCog.listener()
    async def on_global_http_ratelimit(self, retry_after: float):
        self.bot.logger.warning("Reached Global HTTP Ratelimit.")
        self.bot.logger.warning(f"Retry after: {retry_after}.")

        await self.send_ratelimit_notify_to_channel(retry_after=retry_after)


def setup(bot: Smiffy):
    bot.add_cog(HttpRatelimit(bot))
