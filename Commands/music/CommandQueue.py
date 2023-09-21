from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING

from nextcord import Color, Embed, SelectOption, ui, utils

from enums import Emojis
from utilities import CustomCog, CustomInteraction

from .__main__ import MusicCog, MusicPlayer

if TYPE_CHECKING:
    from mafic import Track

    from bot import Smiffy
    from typings import PlayerT


class QueueList(ui.Select):
    def __init__(self, queue_data: list[Track]):
        self.queue_data: list[Track] = queue_data

        quque_lenght: int = len(queue_data)
        pages: int = round((quque_lenght / 5) + 0.5)
        pages_list: list[SelectOption] = []

        for page in range(1, pages + 1):
            pages_list.append(
                SelectOption(
                    label=f"Strona: {page}",
                    description=f"Wyświetla kolejke na stronie {page}",
                    value=str(page),
                    emoji="📖",
                )
            )

        super().__init__(
            placeholder="Wybierz następną stronę kolejki",
            options=pages_list,
        )

    async def callback(self, interaction: CustomInteraction) -> None:
        if not interaction.message:
            await interaction.send_error_message(description="Wystąpił nieoczekiwany błąd.")
            return

        selected_page: int = int(self.values[0]) - 1
        min_range: int = selected_page * 5
        max_range: int = (selected_page * 5) + 5

        embed: Embed = interaction.message.embeds[0]
        embed.clear_fields()

        for index, track in enumerate(self.queue_data):
            if index >= min_range:
                track_lenght: str = str(timedelta(seconds=track.length / 1000))

                embed.add_field(
                    name=f"`🔔` {index + 1}. {track.title}",
                    value=f"{Emojis.REPLY.value} Długość: `{track_lenght}`",
                    inline=False,
                )

            if index + 1 == max_range:
                break

        await interaction.message.edit(embed=embed)


class QuqueListView(ui.View):
    def __init__(self, queue_data: list[Track]):
        super().__init__(timeout=None)

        self.add_item(QueueList(queue_data))


class CommandQueue(CustomCog):
    @MusicCog.main.subcommand(  # pylint: disable=no-member
        name="kolejka",
        description="Pomija aktualną graną piosenke",
    )
    async def music_queue(self, interaction: CustomInteraction):
        assert interaction.guild

        await interaction.response.defer()

        if not interaction.guild.me.voice or not interaction.guild.me.voice.channel:
            return await interaction.send_error_message(
                description="Bot nie jest aktualnie podłączony pod żaden kanał.",
            )

        if not interaction.guild.voice_client:
            return await interaction.send_error_message(description="Bot aktualnie nic nie gra.")

        player: PlayerT = interaction.guild.voice_client  # pyright: ignore
        assert isinstance(player, MusicPlayer)

        if not player.queue:
            return await interaction.send_error_message(description="Kolejka bota jest pusta.")

        embed = Embed(
            title="`📃` Kolejka piosenek na serwerze",
            color=Color.dark_theme(),
            timestamp=utils.utcnow(),
        )
        embed.set_author(
            name=interaction.user,
            icon_url=interaction.user_avatar_url,
        )
        embed.set_thumbnail(url=interaction.guild_icon_url)

        embed.set_footer(
            text=f"Smiffy v{self.bot.__version__}",
            icon_url=self.bot.avatar_url,
        )

        for index, track in enumerate(player.queue[0:5]):
            track_lenght: str = str(timedelta(seconds=track.length / 1000))

            embed.add_field(
                name=f"`🔔` {index + 1}. {track.title}",
                value=f"{Emojis.REPLY.value} Długość: `{track_lenght}`",
                inline=False,
            )

        await interaction.send(
            embed=embed,
            view=QuqueListView(queue_data=player.queue),
        )


def setup(bot: Smiffy):
    bot.add_cog(CommandQueue(bot))
