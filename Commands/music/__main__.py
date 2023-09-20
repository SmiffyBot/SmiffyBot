from __future__ import annotations
from typing import TYPE_CHECKING, Optional, Type

from asyncio import sleep
from datetime import timedelta

from nextcord import slash_command, Guild, Embed, Color, utils, TextChannel, ui
from mafic import NodePool, TrackEndEvent, Strategy, Player, VoiceRegion, __version__
from aiohttp import client_exceptions

from utilities import CustomCog, bot_utils, CustomInteraction
from bot import Smiffy
from enums import Emojis

if TYPE_CHECKING:
    from nextcord.abc import Connectable, GuildChannel
    from mafic import Track, Node

    from typings import DB_RESPONSE


class MusicPlayer(Player[Smiffy]):
    def __init__(self, bot: Smiffy, channel: Connectable):
        super().__init__(bot, channel)

        self.bot: Smiffy = bot
        self.loop: bool = False
        self.channel_last_command: Optional[GuildChannel] = None
        self.queue: list[Track] = []

        @bot.listen()
        async def on_track_end(event: TrackEndEvent):
            assert isinstance(event.player, MusicPlayer)

            if self.loop:
                return await event.player.play(event.track)

            if self.queue:
                current_track: Track = event.player.queue.pop(0)

                await event.player.play(current_track)

                if await self.get_notify_status(event.player.guild):
                    await self.send_playing_song_notify(event.player, current_track)

    async def get_notify_status(self, guild: Guild) -> bool:
        response: Optional[DB_RESPONSE] = await self.bot.db.execute_fetchone(
            "SELECT notify FROM music_settings WHERE guild_id = ?", (guild.id,)
        )
        if not response or not response[0]:
            return True

        return False

    async def send_playing_song_notify(
        self, player: MusicPlayer, track: Track, view: Optional[ui.View] = None
    ):
        if not isinstance(player.channel_last_command, TextChannel):
            return

        track_lenght: str = str(timedelta(seconds=int(track.length / 1000)))
        track_position: int = len(player.queue) + 1

        embed = Embed(
            title="`🔊` Uruchamiam muzykę...",
            colour=Color.dark_theme(),
            timestamp=utils.utcnow(),
        )

        embed.add_field(name="`⏰` Długość", value=f"{Emojis.REPLY.value} `{track_lenght}`")
        embed.add_field(
            name="`👤` Autor",
            value=f"{Emojis.REPLY.value} `{track.author}`",
            inline=False,
        )
        embed.add_field(
            name="`📌` Numer w kolejce",
            value=f"{Emojis.REPLY.value} `#{track_position}`",
        )

        embed.set_footer(
            text=f"Smiffy v{self.bot.__version__} | Mafic v{__version__}",
            icon_url=self.bot.avatar_url,
        )
        embed.set_thumbnail(url=track.artwork_url)
        embed.set_author(
            name=track.title,
            url=track.uri,
            icon_url=self.bot.avatar_url,
        )

        await player.channel_last_command.send(embed=embed, view=view)


class MusicCog(CustomCog):
    def __init__(self, bot: Smiffy) -> None:
        super().__init__(bot=bot)

        self.player_regions: tuple[VoiceRegion, ...] = (
            VoiceRegion.EUROPE,  # Currently we support only Europe
        )

        attempts: Optional[int] = bot_utils.get_value_from_config("LAVALINK_CONNECTION_ATTEMPTS")
        interval: Optional[int] = bot_utils.get_value_from_config("LAVALINK_ATTEMPT_INTERVAL")

        self.connection_attempts: int = attempts if attempts else 1
        self.attempt_interval: int = interval if interval else 3

        self.bot.pool = NodePool(bot, default_strategies=[Strategy.USAGE, Strategy.SHARD])
        self.bot.loop.create_task(self.add_music_nodes())

    @property
    def get_node_settings(
        self,
    ) -> dict[str, str | None | Type[MusicPlayer] | tuple[VoiceRegion, ...]]:
        host: Optional[str] = bot_utils.get_value_from_config("LAVALINK_ADDRESS")
        port: Optional[str] = bot_utils.get_value_from_config("LAVALINK_PORT")
        password: Optional[str] = bot_utils.get_value_from_config("LAVALINK_PASSWORD")

        return {
            "host": host,
            "port": port,
            "password": password,
            "label": "Smiffy-Europe",
            "player_cls": MusicPlayer,
            "regions": self.player_regions,
        }

    async def add_music_nodes(self):
        for _ in range(self.connection_attempts):
            try:
                await self.bot.pool.create_node(**self.get_node_settings)  # pyright: ignore
                break
            except client_exceptions.ClientConnectorError:
                if bot_utils.get_value_from_config("LAVALINK_SHOW_ATTEMPTS") is True:
                    self.bot.logger.error(
                        f"Connection to Lavalink server failed. " f"Re-connect in {self.attempt_interval}s."
                    )

            await sleep(self.attempt_interval)

            if _ + 1 == self.connection_attempts:
                self.bot.logger.error("Connection to Lavalink server failed.")

    @CustomCog.listener()
    async def on_node_ready(self, node: Node[Smiffy]):
        self.bot.logger.info(f"Music node: {node.label} ({node.session_id}) is ready.")

    @slash_command(name="muzyka", dm_permission=False)
    async def main(self, intraction: CustomInteraction) -> None:  # pylint: disable=unused-argument
        ...


def setup(bot: Smiffy):
    bot.add_cog(MusicCog(bot))
