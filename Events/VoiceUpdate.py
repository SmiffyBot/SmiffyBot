from __future__ import annotations

from asyncio import sleep
from typing import TYPE_CHECKING, Optional

from nextcord import Color, Embed, Member, TextChannel, utils

from enums import Emojis
from utilities import CustomCog

if TYPE_CHECKING:
    from nextcord import Guild, VoiceState

    from bot import Smiffy
    from typings import DB_RESPONSE, PlayerT


class VoiceUpdate(CustomCog):
    async def alerts_enabled(self, guild: Guild) -> bool:
        response: Optional[DB_RESPONSE] = await self.bot.db.execute_fetchone(
            "SELECT notify FROM music_settings WHERE guild_id = ?", (guild.id,)
        )
        if not response or not response[0]:
            return True

        return False

    async def handle_bot_disconnect(self, state: VoiceState):
        if not state.channel:
            return

        seconds: int = 0
        while not len(state.channel.members) - 1:
            if not state.channel.guild.me.voice or not state.channel.guild.me.voice.channel:
                break

            await sleep(5)
            seconds += 5

            if seconds >= 150:
                await state.channel.guild.me.disconnect()

                if await self.alerts_enabled(state.channel.guild):
                    player: Optional[PlayerT] = state.channel.guild.voice_client  # pyright: ignore

                    if player and getattr(player, "channel_last_command", None):
                        channel: TextChannel = player.channel_last_command  # pyright: ignore

                        embed = Embed(
                            title="`🔊` Odłączono z kanału",
                            colour=Color.dark_theme(),
                            description=f"{Emojis.REPLY.value} Wygląda na to, "
                            f"że spędziłem na kanale sam zbyt dużo czasu.",
                            timestamp=utils.utcnow(),
                        )
                        embed.set_author(
                            name="Smiffy v2.0 - Muzyka",
                            icon_url=self.bot.avatar_url,
                        )
                        embed.set_thumbnail(self.avatars.get_guild_icon(channel.guild))
                        await channel.send(embed=embed)

                break

    @CustomCog.listener()
    async def on_voice_state_update(
        self,
        member: Member,  # pylint: disable=unused-argument
        before: VoiceState,
        after: VoiceState,  # pylint: disable=unused-argument
    ):
        if before.channel and before.channel.guild.me.voice and before.channel.guild.me.voice.channel:
            if before.channel.id == before.channel.guild.me.voice.channel.id:
                self.bot.loop.create_task(self.handle_bot_disconnect(state=before))


def setup(bot: Smiffy):
    bot.add_cog(VoiceUpdate(bot))
