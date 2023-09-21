from __future__ import annotations

from typing import TYPE_CHECKING

from mafic import Equalizer, Filter, Rotation, Timescale
from nextcord import SlashOption

from enums import Emojis
from utilities import CustomCog, CustomInteraction, PermissionHandler

from .__main__ import MusicCog, MusicPlayer

if TYPE_CHECKING:
    from bot import Smiffy
    from typings import PlayerT


class CommandFilters(CustomCog):
    @MusicCog.main.subcommand(name="filtry")  # pylint: disable=no-member
    async def music_filters(self, interaction: CustomInteraction):
        pass

    @music_filters.subcommand(  # pyright: ignore
        name="bassboost", description="Włącza lub wyłącza efekt bassboost"
    )
    @PermissionHandler(user_role_has_permission="music")
    async def music_bassboost(
        self,
        interaction: CustomInteraction,
        status: str = SlashOption(
            name="status",
            description="Włącz lub wyłącz efekt bassboost",
            choices={"Włącz": "on", "Wyłącz": "off"},
        ),
    ):
        assert interaction.guild

        if not interaction.guild.voice_client or not interaction.guild.me.voice:
            return await interaction.send_error_message(description="Bot aktualnie nic nie gra.")
        if not interaction.guild.me.voice.channel:
            return await interaction.send_error_message(description="Bot aktualnie nic nie gra.")

        await interaction.response.defer()
        player: PlayerT = interaction.guild.voice_client  # pyright: ignore

        assert isinstance(player, MusicPlayer)

        if not player.current:
            return await interaction.send_error_message(description="Bot aktualnie nic nie gra.")

        if status == "on":
            equalizer = Equalizer(
                bands=[
                    (0, 0.25),
                    (1, 0.25),
                    (2, 0.15),
                    (3, 0.05),
                    (4, 0.2),
                    (5, -0.15),
                    (6, -0.1),
                    (7, -0.1),
                    (8, -0.1),
                    (9, -0.1),
                    (10, -0.2),
                    (11, -0.2),
                    (12, -0.3),
                    (13, -0.3),
                    (14, -0.3),
                ]
            )

            filter_equalizer = Filter(equalizer=equalizer)
            await player.add_filter(filter_equalizer, label="bassboost", fast_apply=True)
            await interaction.send_success_message(
                title=f"Pomyślnie zaktualizowano {Emojis.GREENBUTTON.value}",
                description=f"{Emojis.REPLY.value} Włączono efekt bassboost.",
            )

        else:
            try:
                await player.remove_filter(label="bassboost", fast_apply=True)
            except KeyError:
                return await interaction.send_error_message(
                    description="Filtr bassboost nie jest aktualnie włączony.",
                )

            await interaction.send_success_message(
                title=f"Pomyślnie zaktualizowano {Emojis.GREENBUTTON.value}",
                description=f"{Emojis.REPLY.value} Wyłączono efekt bassboost.",
            )

    @music_filters.subcommand(name="8d", description="Włącza lub wyłącza efekt 8D")  # pyright: ignore
    @PermissionHandler(user_role_has_permission="music")
    async def music_8d(
        self,
        interaction: CustomInteraction,
        status: str = SlashOption(
            name="status",
            description="Włącz lub wyłącz efekt 8D",
            choices={"Włącz": "on", "Wyłącz": "off"},
        ),
    ):
        assert interaction.guild

        if not interaction.guild.voice_client or not interaction.guild.me.voice:
            return await interaction.send_error_message(description="Bot aktualnie nic nie gra.")
        if not interaction.guild.me.voice.channel:
            return await interaction.send_error_message(description="Bot aktualnie nic nie gra.")

        await interaction.response.defer()
        player: PlayerT = interaction.guild.voice_client  # pyright: ignore
        assert isinstance(player, MusicPlayer)

        if not player.current:
            return await interaction.send_error_message(description="Bot aktualnie nic nie gra.")

        if status == "on":
            rotation = Rotation(rotation_hz=0.15)
            filter_rotation = Filter(rotation=rotation)

            await player.add_filter(filter_rotation, label="8d", fast_apply=True)
            await interaction.send_success_message(
                title=f"Pomyślnie zaktualizowano {Emojis.GREENBUTTON.value}",
                description=f"{Emojis.REPLY.value} Włączono efekt 8D.",
            )

        else:
            try:
                await player.remove_filter(label="8d", fast_apply=True)
            except KeyError:
                return await interaction.send_error_message(
                    description="Filtr 8D nie jest aktualnie włączony."
                )

            await interaction.send_success_message(
                title=f"Pomyślnie zaktualizowano {Emojis.GREENBUTTON.value}",
                description=f"{Emojis.REPLY.value} Wyłączono efekt 8D.",
            )

    @music_filters.subcommand(  # pyright: ignore
        name="nightcore", description="Włącza lub wyłącza efekt nightcore"
    )
    @PermissionHandler(user_role_has_permission="music")
    async def music_nightcore(
        self,
        interaction: CustomInteraction,
        status: str = SlashOption(
            name="status",
            description="Włącz lub wyłącz efekt bassboost",
            choices={"Włącz": "on", "Wyłącz": "off"},
        ),
    ):
        assert interaction.guild

        if not interaction.guild.voice_client or not interaction.guild.me.voice:
            return await interaction.send_error_message(description="Bot aktualnie nic nie gra.")
        if not interaction.guild.me.voice.channel:
            return await interaction.send_error_message(description="Bot aktualnie nic nie gra.")

        await interaction.response.defer()
        player: PlayerT = interaction.guild.voice_client  # pyright: ignore
        assert isinstance(player, MusicPlayer)

        if not player.current:
            return await interaction.send_error_message(description="Bot aktualnie nic nie gra.")

        if status == "on":
            timescale = Timescale(speed=1.1, pitch=1.2, rate=1.2)

            filter_timescale = Filter(timescale=timescale)
            await player.add_filter(filter_timescale, label="nightcore", fast_apply=True)

            await interaction.send_success_message(
                title=f"Pomyślnie zaktualizowano {Emojis.GREENBUTTON.value}",
                description=f"{Emojis.REPLY.value} Włączono efekt nightcore.",
            )

        else:
            try:
                await player.remove_filter(label="nightcore", fast_apply=True)
            except KeyError:
                return await interaction.send_error_message(
                    description="Filtr nightcore nie jest aktualnie włączony.",
                )

            await interaction.send_success_message(
                title=f"Pomyślnie zaktualizowano {Emojis.GREENBUTTON.value}",
                description=f"{Emojis.REPLY.value} Wyłączono efekt nightcore.",
            )


def setup(bot: Smiffy):
    bot.add_cog(CommandFilters(bot))
