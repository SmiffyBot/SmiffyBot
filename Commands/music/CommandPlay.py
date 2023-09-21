from __future__ import annotations

from ast import literal_eval
from datetime import timedelta
from typing import TYPE_CHECKING

from mafic import Playlist, SearchType, __version__, errors
from nextcord import (
    ButtonStyle,
    Color,
    Embed,
    Member,
    SlashOption,
    TextChannel,
    Thread,
    ui,
    utils,
)

from enums import Emojis
from utilities import (
    CustomCog,
    CustomInteraction,
    DiscordSupportButton,
    PermissionHandler,
)

from .__main__ import MusicCog, MusicPlayer

if TYPE_CHECKING:
    from mafic import Node, Track
    from nextcord import Guild

    from bot import Smiffy
    from typings import PlayerT
    from utilities import DB_RESPONSE, Optional, Union


class MusicManagerView(ui.View):
    def __init__(self, player: PlayerT, author_id: int):  # pyright: ignore
        super().__init__(timeout=None)

        self.author_id: int = author_id
        self.player: MusicPlayer = player  # pyright: ignore

    async def interaction_check(self, interaction: CustomInteraction) -> bool:
        assert interaction.user

        if not interaction.data:
            return False

        if interaction.data.get("custom_id") in (
            "button_queue",
            "button_fav",
            "button_info",
        ):
            return True

        if interaction.user.id != self.author_id:
            await interaction.send_error_message(
                description="Tylko autor tej wiadomości może użyć tego przycisku.",
                ephemeral=True,
            )

            return False
        return True

    @ui.button(
        emoji="<:stop:1141100669193965768>", style=ButtonStyle.grey
    )  # pyright: ignore[reportGeneralTypeIssues]
    async def button_stop(
        self,
        button: ui.Button,  # pylint: disable=unused-argument
        interaction: CustomInteraction,
    ) -> None:
        assert interaction.guild and isinstance(interaction.user, Member)

        if not interaction.guild.me.voice or not interaction.guild.me.voice.channel:
            await interaction.send_error_message(
                description="Bot nie jest aktualnie podłączony pod żaden kanał.",
                ephemeral=True,
            )
            return

        if not interaction.user.voice or not interaction.user.voice.channel:
            await interaction.send_error_message(
                description="Aby użyć tej funkcji musisz znajdować się na kanale głosowym.",
                ephemeral=True,
            )
            return

        if interaction.user.voice.channel.id != interaction.guild.me.voice.channel.id:
            await interaction.send_error_message(
                description="Aby użyć tej funkcji musisz znajdować się na tym samym kanale głosowym co bot.",
                ephemeral=True,
            )
            return

        self.player.queue.clear()
        self.player.cleanup()
        await self.player.stop()

        await interaction.send_success_message(
            title=f"Pomyślnie wyłączono muzykę {Emojis.GREENBUTTON.value}",
            description=f"{Emojis.REPLY.value} Wszystkie piosenki zostały wyłączone."
            f"\n\n(*Wiadomość zostanie usunięta za 30s*)",
            color=Color.dark_theme(),
            delete_after=30,
        )

    @ui.button(
        emoji="<:pause:1141102297414385684>", style=ButtonStyle.grey
    )  # pyright: ignore[reportGeneralTypeIssues]
    async def button_pause(
        self,
        button: ui.Button,  # pylint: disable=unused-argument
        interaction: CustomInteraction,
    ) -> None:
        assert interaction.guild and isinstance(interaction.user, Member)

        if not interaction.guild.me.voice or not interaction.guild.me.voice.channel:
            await interaction.send_error_message(
                description="Bot nie jest aktualnie podłączony pod żaden kanał.",
                ephemeral=True,
            )
            return

        if not interaction.user.voice or not interaction.user.voice.channel:
            await interaction.send_error_message(
                description="Aby użyć tej funkcji musisz znajdować się na kanale głosowym.",
                ephemeral=True,
            )
            return

        if interaction.user.voice.channel.id != interaction.guild.me.voice.channel.id:
            await interaction.send_error_message(
                description="Aby użyć tej funkcji musisz znajdować się na tym samym kanale głosowym co bot.",
                ephemeral=True,
            )
            return

        if not self.player.current:
            await interaction.send_error_message(description="Aktualnie bot nic nie gra.", ephemeral=True)
            return

        if self.player.paused:
            await interaction.send_error_message(
                description="Aktualna muzyka już jest zatrzymana.", ephemeral=True
            )
            return

        await self.player.pause()

        await interaction.send_success_message(
            title=f"Pomyślnie włączono pauze {Emojis.GREENBUTTON.value}",
            description=f"{Emojis.REPLY.value} Aktualna piosenka została zatrzymana."
            f"\n\n(*Wiadomość zostanie usunięta za 30s*)",
            color=Color.dark_theme(),
            delete_after=30,
        )

    @ui.button(
        emoji="<:play:1141100670490005635>", style=ButtonStyle.grey
    )  # pyright: ignore[reportGeneralTypeIssues]
    async def button_resume(
        self,
        button: ui.Button,  # pylint: disable=unused-argument
        interaction: CustomInteraction,
    ) -> None:
        assert interaction.guild and isinstance(interaction.user, Member)

        if not interaction.guild.me.voice or not interaction.guild.me.voice.channel:
            await interaction.send_error_message(
                description="Bot nie jest aktualnie podłączony pod żaden kanał.",
                ephemeral=True,
            )
            return

        if not interaction.user.voice or not interaction.user.voice.channel:
            await interaction.send_error_message(
                description="Aby użyć tej funkcji musisz znajdować się na kanale głosowym.",
                ephemeral=True,
            )
            return

        if interaction.user.voice.channel.id != interaction.guild.me.voice.channel.id:
            await interaction.send_error_message(
                description="Aby użyć tej funkcji musisz znajdować się na tym samym kanale głosowym co bot.",
                ephemeral=True,
            )
            return

        if not self.player.current:
            await interaction.send_error_message(description="Aktualnie bot nic nie gra.", ephemeral=True)
            return

        if not self.player.paused:
            await interaction.send_error_message(
                description="Aktualna muzyka nie jest zatrzymana.", ephemeral=True
            )
            return

        await interaction.send_success_message(
            title=f"Pomyślnie wyłączono pauze {Emojis.GREENBUTTON.value}",
            description=f"{Emojis.REPLY.value} Aktualna piosenka została wznowiona."
            f"\n\n(*Wiadomość zostanie usunięta za 30s*)",
            color=Color.dark_theme(),
            delete_after=30,
        )

        await self.player.resume()

    @ui.button(
        emoji="<:skip:1141100666610257971>", style=ButtonStyle.grey
    )  # pyright: ignore[reportGeneralTypeIssues]
    async def button_skip(
        self,
        button: ui.Button,  # pylint: disable=unused-argument
        interaction: CustomInteraction,
    ) -> None:
        assert interaction.guild and isinstance(interaction.user, Member)

        if not interaction.guild.me.voice or not interaction.guild.me.voice.channel:
            await interaction.send_error_message(
                description="Bot nie jest aktualnie podłączony pod żaden kanał.",
                ephemeral=True,
            )
            return
        if not interaction.user.voice or not interaction.user.voice.channel:
            await interaction.send_error_message(
                description="Aby użyć tej funkcji musisz znajdować się na kanale głosowym.",
                ephemeral=True,
            )
            return
        if interaction.user.voice.channel.id != interaction.guild.me.voice.channel.id:
            await interaction.send_error_message(
                description="Aby użyć tej funkcji musisz znajdować się na tym samym kanale głosowym co bot.",
                ephemeral=True,
            )
            return

        if self.player.loop:
            await interaction.send_error_message(
                description="Najpierw musisz wyłączyć zapętlanie piosenki.",
                ephemeral=True,
            )
            return

        if not self.player.current:
            await interaction.send_error_message(description="Aktualnie bot nic nie gra.", ephemeral=True)
            return

        current_track: Optional[Track] = self.player.current
        if not current_track:
            await interaction.send_error_message(
                description="Nie mogłem pozyskać informacji na temat nowej piosenki.",
                ephemeral=True,
            )
            return

        await self.player.stop()

        await interaction.send_success_message(
            title=f"Pomyślnie pominięto piosenke {Emojis.GREENBUTTON.value}",
            description=f"{Emojis.REPLY.value} Pominięta piosenka: [`LINK`]({current_track.uri})"
            f"\n\n(*Wiadomość zostanie usunięta za 30s*)",
            delete_after=30,
        )

    @ui.button(
        emoji="<:music_loop:1141102281467629689>", style=ButtonStyle.grey, row=2
    )  # pyright: ignore[reportGeneralTypeIssues]
    async def button_loop(
        self,
        button: ui.Button,  # pylint: disable=unused-argument
        interaction: CustomInteraction,
    ) -> None:
        assert interaction.guild and isinstance(interaction.user, Member)

        if not interaction.guild.me.voice or not interaction.guild.me.voice.channel:
            await interaction.send_error_message(
                description="Bot nie jest aktualnie podłączony pod żaden kanał.",
                ephemeral=True,
            )
            return

        if not interaction.user.voice or not interaction.user.voice.channel:
            await interaction.send_error_message(
                description="Aby użyć tej funkcji musisz znajdować się na kanale głosowym.",
                ephemeral=True,
            )
            return

        if interaction.user.voice.channel.id != interaction.guild.me.voice.channel.id:
            await interaction.send_error_message(
                description="Aby użyć tej funkcji musisz znajdować się na tym samym kanale głosowym co bot.",
                ephemeral=True,
            )
            return

        if self.player.loop:
            self.player.loop = False

            await interaction.send_success_message(
                title=f"Pomyślnie wyłączono zapętlanie {Emojis.GREENBUTTON.value}",
                description=f"{Emojis.REPLY.value} Zapętlanie zostało wyłączone."
                f"\n\n(*Wiadomość zostanie usunięta za 30s*)",
                delete_after=30,
            )

        else:
            self.player.loop = True

            await interaction.send_success_message(
                title=f"Pomyślnie włączono zapętlanie {Emojis.GREENBUTTON.value}",
                description=f"{Emojis.REPLY.value} Zapętlanie zostało włączone."
                f"\n\n(*Wiadomość zostanie usunięta za 30s*)",
                delete_after=30,
            )

    @ui.button(  # pyright: ignore[reportGeneralTypeIssues]
        emoji="<:queue:1141511641222099065>",
        style=ButtonStyle.grey,
        row=2,
        custom_id="button_queue",
    )
    async def button_queue(
        self,
        button: ui.Button,  # pylint: disable=unused-argument
        interaction: CustomInteraction,
    ) -> None:
        assert interaction.guild

        if not interaction.guild.me.voice or not interaction.guild.me.voice.channel:
            await interaction.send_error_message(
                description="Bot nie jest aktualnie podłączony pod żaden kanał.",
                ephemeral=True,
            )
            return

        if not interaction.guild.voice_client:
            await interaction.send_error_message(
                description="Bot aktualnie nic nie gra.",
                ephemeral=True,
            )
            return

        if not self.player.queue:
            await interaction.send_error_message(
                description="Bot nie ma żadnych piosenek w kolejce.",
                ephemeral=True,
            )
            return

        command_mention: str = interaction.get_command_mention(command_name="muzyka", sub_command="kolejka")
        embed = Embed(
            title="`📃` Kolejka piosenek na serwerze",
            color=Color.dark_theme(),
            description=f"{Emojis.REPLY.value} **Aby uzyskać pełną kolejke użyj:** {command_mention}",
            timestamp=utils.utcnow(),
        )
        embed.set_author(name=interaction.user, icon_url=interaction.user_avatar_url)
        embed.set_thumbnail(url=interaction.guild_icon_url)

        embed.set_footer(
            text=f"Smiffy v{interaction.bot.__version__}",
            icon_url=interaction.bot.avatar_url,
        )

        for index, track in enumerate(self.player.queue[0:5]):
            track_lenght: str = str(timedelta(seconds=int(track.length / 1000)))

            embed.add_field(
                name=f"`🔔` {index + 1}. {track.title}",
                value=f"{Emojis.REPLY.value} Długość: `{track_lenght}`",
                inline=False,
            )

        await interaction.send(embed=embed, ephemeral=True)

    @ui.button(  # pyright: ignore[reportGeneralTypeIssues]
        emoji="<:favorite:1141511639556968478>",
        style=ButtonStyle.grey,
        row=2,
        custom_id="button_fav",
    )
    async def button_favorite(
        self,
        button: ui.Button,  # pylint: disable=unused-argument
        interaction: CustomInteraction,
    ) -> None:
        assert isinstance(interaction.user, Member) and interaction.guild

        if not interaction.guild.me.voice or not interaction.guild.me.voice.channel:
            await interaction.send_error_message(
                description="Bot nie jest aktualnie podłączony pod żaden kanał.",
                ephemeral=True,
            )
            return

        if not interaction.guild.voice_client:
            await interaction.send_error_message(
                description="Bot aktualnie nic nie gra.",
                ephemeral=True,
            )
            return

        player: PlayerT = interaction.guild.voice_client  # pyright: ignore
        assert isinstance(player, MusicPlayer)

        if not player.current:
            await interaction.send_error_message(
                description="Bot aktualnie nic nie gra.",
                ephemeral=True,
            )
            return

        track: Track = player.current
        bot: Smiffy = interaction.bot

        response: Optional[DB_RESPONSE] = await bot.db.execute_fetchone(
            "SELECT favorite_songs FROM music_users WHERE user_id = ?",
            (interaction.user.id,),
        )

        song_data: dict[str, Union[int, str, None]] = {
            "title": track.title,
            "url": track.uri,
            "author": track.author,
            "image_url": track.artwork_url,
            "lenght": track.length,
        }

        if not response:
            data: list[dict[str, Union[int, str, None]]] = [song_data]
            await bot.db.execute_fetchone(
                "INSERT INTO music_users(user_id, favorite_songs) VALUES(?,?)",
                (interaction.user.id, str(data)),
            )
            await interaction.send_success_message(
                title=f"Pomyślnie dodano {Emojis.GREENBUTTON.value}",
                description=f"{Emojis.REPLY.value} Dodano aktualnie grającą piosenke do ulubionych.",
                ephemeral=True,
            )

        else:
            data: list[dict[str, Union[int, str, None]]] = literal_eval(response[0])
            if song_data in data:
                data.remove(song_data)

                if len(data) <= 0:
                    data = []

                await interaction.send_success_message(
                    title=f"Pomyślnie usunięto {Emojis.REDBUTTON.value}",
                    description=f"{Emojis.REPLY.value} Usunięto aktualnie grającą piosenke z ulubionych.",
                    ephemeral=True,
                    color=Color.dark_theme(),
                )

                await bot.db.execute_fetchone(
                    "UPDATE music_users SET favorite_songs = ? WHERE user_id = ?",
                    (str(data), interaction.user.id),
                )
                return

            if len(data) >= 25:
                await interaction.send_error_message(
                    description="Osiągnięto limit `25` ulubionych piosenek.",
                    ephemeral=True,
                )
                return

            data.append(song_data)

            await interaction.send_success_message(
                title=f"Pomyślnie dodano {Emojis.GREENBUTTON.value}",
                description=f"{Emojis.REPLY.value} Dodano aktualnie grającą piosenke z ulubionych.",
                ephemeral=True,
            )

            await bot.db.execute_fetchone(
                "UPDATE music_users SET favorite_songs = ? WHERE user_id = ?",
                (str(data), interaction.user.id),
            )

    @ui.button(  # pyright: ignore[reportGeneralTypeIssues]
        emoji="<:info:1141511636256038963>",
        style=ButtonStyle.grey,
        row=2,
        custom_id="button_info",
    )
    async def button_info(
        self,
        button: ui.Button,  # pylint: disable=unused-argument
        interaction: CustomInteraction,
    ) -> None:
        embed = Embed(
            title="`❓` Potrzebujesz pomocy?",
            description=f"{Emojis.REPLY.value} Potrzebujesz pomocy lub masz pytania? Dołącz "
            f"na naszego discorda przyciskiem poniżej.",
            colour=Color.yellow(),
            timestamp=utils.utcnow(),
        )
        embed.set_author(name=interaction.user, icon_url=interaction.user_avatar_url)
        embed.set_thumbnail(url=interaction.guild_icon_url)
        embed.set_footer(text="Made with ❤️", icon_url=interaction.bot.avatar_url)

        button_discord: ui.View = DiscordSupportButton()

        await interaction.send(embed=embed, ephemeral=True, view=button_discord)


class CommandPlay(CustomCog):
    async def alerts_enabled(self, guild: Guild) -> bool:
        response: Optional[DB_RESPONSE] = await self.bot.db.execute_fetchone(
            "SELECT notify FROM music_settings WHERE guild_id = ?", (guild.id,)
        )
        if not response or not response[0]:
            return True

        return False

    @MusicCog.main.subcommand(  # pylint: disable=no-member  # pyright: ignore
        name="play", description="uruchamia muzykę"
    )
    @PermissionHandler(user_role_has_permission="music")
    async def music_play(
        self,
        interaction: CustomInteraction,
        query: str = SlashOption(name="piosenka", description="Podaj nazwę piosenki lub link do niej."),
    ):
        assert interaction.guild and isinstance(interaction.user, Member)

        await interaction.response.defer()

        if not interaction.user.voice or not interaction.user.voice.channel:
            return await interaction.send_error_message(
                description="Aby użyć tej komendy musisz znajdować się na kanale głosowym.",
            )

        if interaction.guild.me.voice and interaction.guild.me.voice.channel:
            if interaction.user.voice.channel.id != interaction.guild.me.voice.channel.id:
                return await interaction.send_error_message(
                    description="Aby użyć tej komendy musisz znajdować się na tym samym kanale co bot.",
                )

        if not interaction.guild.voice_client:
            try:
                player: PlayerT = (  # pyright: ignore
                    await interaction.user.voice.channel.connect(  # pyright: ignore
                        cls=MusicPlayer  # pyright: ignore
                    )
                )
            except errors.NoNodesAvailable:
                return await interaction.send_error_message(
                    description="Bot nie ma do dyspozycji żadnych wolnych wątków. Spróbuj ponownie później.",
                )
        else:
            player: PlayerT = interaction.guild.voice_client  # pyright: ignore

        assert isinstance(player, MusicPlayer)

        await interaction.guild.change_voice_state(
            channel=interaction.guild.me.voice.channel,  # pyright: ignore
            self_deaf=True,  # pyright: ignore
        )

        player.channel_last_command = interaction.channel  # pyright: ignore

        tracks: Optional[Union[list[Track], Playlist]] = await player.fetch_tracks(query)

        if not tracks:
            return await interaction.send_error_message(description="Nie odnalazłem żadnej podanej piosenki.")

        buttons_view: MusicManagerView = MusicManagerView(player=player, author_id=interaction.user.id)

        if not isinstance(tracks, Playlist):
            track: Track = tracks[0]
            track_lenght: str = str(timedelta(seconds=track.length / 1000))

            if not player.current:
                await player.play(track)

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
                embed.add_field(name="`📌` Numer w kolejce", value=f"{Emojis.REPLY.value} `#1`")

                embed.set_footer(
                    text=f"Smiffy v{self.bot.__version__} | Mafic v{__version__}",
                    icon_url=self.bot.avatar_url,
                )

                embed.set_thumbnail(url=track.artwork_url)
                embed.set_author(
                    name=track.title,
                    url=track.uri,
                    icon_url=interaction.user_avatar_url,
                )

                await interaction.send(embed=embed, view=buttons_view)

            else:
                player.queue.extend([track])
                quque_position: int = len(player.queue) + 1

                embed = Embed(
                    title=f"Pomyślnie dodano muzykę do kolejki {Emojis.GREENBUTTON.value}",
                    colour=Color.green(),
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
                    value=f"{Emojis.REPLY.value} `#{quque_position}`",
                )
                embed.set_footer(
                    text=f"Smiffy v{self.bot.__version__} | Mafic v{__version__}",
                    icon_url=self.bot.avatar_url,
                )

                embed.set_thumbnail(url=track.artwork_url)
                embed.set_author(
                    name=track.title,
                    url=track.uri,
                    icon_url=interaction.user_avatar_url,
                )

                await interaction.send(embed=embed, view=buttons_view)

        else:
            tracks_list: list[Track] = tracks.tracks
            total_tracks: int = len(tracks_list) + len(player.queue)
            if total_tracks > 100:
                return await interaction.send_error_message(
                    description=f"Osiągnięto limit piosenek w kolejce. **{total_tracks}/100**",
                )

            if not player.current:
                player.queue.extend(tracks_list[1::])
                __track: Optional[Track] = tracks_list[0]
                await player.play(__track)

            else:
                __track: Optional[Track] = None
                player.queue.extend(tracks_list)

            total_seconds: int = 0
            for track in tracks_list:
                total_seconds += int(track.length / 1000)

            tracks_lenght: str = str(timedelta(seconds=total_seconds))

            embed = Embed(
                title=f"Pomyślnie załadowano playliste {Emojis.GREENBUTTON.value}",
                colour=Color.dark_theme(),
                timestamp=utils.utcnow(),
            )
            embed.add_field(
                name="`⏰` Łączna długość",
                value=f"{Emojis.REPLY.value} `{tracks_lenght}`",
            )
            embed.add_field(
                name="`📂` Ilość piosenek",
                value=f"{Emojis.REPLY.value} `{len(tracks_list)}`",
                inline=False,
            )

            embed.set_footer(
                text=f"Smiffy v{self.bot.__version__} | Mafic v{__version__}",
                icon_url=self.bot.avatar_url,
            )

            embed.set_thumbnail(url=tracks_list[0].artwork_url)
            embed.set_author(name=tracks.name, icon_url=interaction.user_avatar_url, url=query)

            await interaction.followup.send(embed=embed, view=buttons_view)

            if __track and await self.alerts_enabled(interaction.guild):
                track_lenght: str = str(timedelta(seconds=__track.length / 1000))

                embed = Embed(
                    title="`🔊` Uruchamiam muzykę...",
                    colour=Color.dark_theme(),
                    timestamp=utils.utcnow(),
                )

                embed.add_field(name="`⏰` Długość", value=f"{Emojis.REPLY.value} `{track_lenght}`")
                embed.add_field(
                    name="`👤` Autor",
                    value=f"{Emojis.REPLY.value} `{__track.author}`",
                    inline=False,
                )
                embed.add_field(
                    name="`📌` Numer w kolejce",
                    value=f"{Emojis.REPLY.value} `#{len(tracks_list)}`",
                )

                embed.set_footer(
                    text=f"Smiffy v{self.bot.__version__} | Mafic v{__version__}",
                    icon_url=self.bot.avatar_url,
                )

                embed.set_thumbnail(url=__track.artwork_url)
                embed.set_author(
                    name=__track.title,
                    url=__track.uri,
                    icon_url=interaction.user_avatar_url,
                )

                if isinstance(interaction.channel, (TextChannel, Thread)):
                    await interaction.channel.send(embed=embed)

    @music_play.on_autocomplete("query")
    async def search_songs(self, interaction: CustomInteraction, search: str) -> Optional[dict[str, str]]:
        assert interaction.user

        bot: Smiffy = interaction.bot

        if not search:
            response: Optional[DB_RESPONSE] = await bot.db.execute_fetchone(
                "SELECT favorite_songs FROM music_users WHERE user_id = ?",
                (interaction.user.id,),
            )
            if response:
                songs: list[dict[str, str]] = literal_eval(response[0])
                songs_dict: dict[str, str] = {}

                for song in songs:
                    songs_dict = {**songs_dict, **{song["title"]: song["url"]}}

                return songs_dict

        try:
            node: Node = self.bot.pool.label_to_node["Smiffy-Europe"]
        except KeyError:
            return

        tracks: Union[Playlist, list[Track], None] = await node.fetch_tracks(
            query=search, search_type=SearchType.YOUTUBE.value
        )

        if not tracks:
            return

        if isinstance(tracks, Playlist):
            return {tracks.name: search}

        songs_dict: dict[str, str] = {}
        for song in tracks:
            if len(songs_dict) == 25:
                break

            if song.uri:
                songs_dict[song.title] = song.uri

        return songs_dict


def setup(bot: Smiffy):
    bot.add_cog(CommandPlay(bot))
