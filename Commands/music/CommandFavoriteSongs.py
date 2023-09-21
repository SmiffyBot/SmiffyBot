from __future__ import annotations

from ast import literal_eval
from datetime import timedelta
from typing import TYPE_CHECKING, Optional, Union

from mafic import Playlist, SearchType, __version__, errors
from nextcord import (
    Color,
    Embed,
    Member,
    SelectOption,
    SlashOption,
    TextChannel,
    Thread,
    ui,
    utils,
)

from enums import Emojis
from utilities import CustomCog, CustomInteraction

from .__main__ import MusicCog, MusicPlayer

if TYPE_CHECKING:
    from mafic import Node, Track

    from bot import Smiffy
    from typings import DB_RESPONSE, PlayerT


class SongsList(ui.Select):
    def __init__(
        self,
        inter: CustomInteraction,
        songs_data: list[dict[str, str]],
    ):
        self.songs_data: list[dict[str, str]] = songs_data
        self.inter: CustomInteraction = inter

        amount_of_songs: int = len(songs_data)
        pages: int = round((amount_of_songs / 5) + 0.5)
        pages_list: list[SelectOption] = []

        for page in range(1, pages + 1):
            pages_list.append(
                SelectOption(
                    label=f"Strona: {page}",
                    description=f"Wyświetla piosenki na stronie {page}",
                    value=str(page),
                    emoji="📖",
                )
            )

        super().__init__(
            placeholder="Wybierz następną stronę piosenek",
            options=pages_list,
        )

    async def callback(self, interaction: CustomInteraction) -> None:
        assert interaction.message

        selected_page: int = int(self.values[0]) - 1
        min_range: int = selected_page * 5
        max_range: int = (selected_page * 5) + 5

        embed: Embed = interaction.message.embeds[0]
        embed.clear_fields()

        for index, song_data in enumerate(self.songs_data):
            if index >= min_range:
                title: str = song_data["title"]
                url: str = song_data["url"]

                embed.add_field(
                    name=f"`🔊` {title}",
                    value=f"{Emojis.REPLY.value} [`LINK`]({url})",
                    inline=False,
                )

            if index + 1 == max_range:
                break

        await self.inter.edit_original_message(embed=embed)


class SongsListView(ui.View):
    def __init__(
        self,
        inter: CustomInteraction,
        songs_data: list[dict[str, str]],
    ):
        super().__init__(timeout=None)

        self.add_item(SongsList(inter, songs_data))


class SelectMusic(ui.Select):
    def __init__(self, tracks: list[Track]):
        self.tracks: list[Track] = tracks
        options: list[SelectOption] = []

        for track in self.tracks:
            if track.uri:
                options.append(
                    SelectOption(
                        label=f"{track.title}",
                        emoji="<:search:1141586703514083459>",
                        value=track.uri,
                    )
                )

            if len(options) == 5:
                break

        super().__init__(
            placeholder="Wybierz piosenkę",
            options=options,
        )

    async def callback(self, interaction: CustomInteraction) -> None:
        assert isinstance(interaction.user, Member)

        bot: Smiffy = interaction.bot
        song_link: str = self.values[0]

        node: Node = bot.pool.label_to_node["MAIN"]

        tracks: Optional[Union[list[Track], Playlist]] = await node.fetch_tracks(
            query=song_link,
            search_type=SearchType.YOUTUBE.value,
        )

        if not tracks or isinstance(tracks, Playlist):
            await interaction.send_error_message(
                description="Wystąpił nieoczekiwany błąd.",
                ephemeral=True,
            )
            return

        track: Track = tracks[0]

        response: Optional[DB_RESPONSE] = await bot.db.execute_fetchone(
            "SELECT favorite_songs FROM music_users WHERE user_id = ?",
            (interaction.user.id,),
        )

        song_data: dict[str, str | int | None] = {
            "title": track.title,
            "url": track.uri,
            "author": track.author,
            "image_url": track.artwork_url,
            "lenght": track.length,
        }

        if not response:
            data: list[dict[str, str | int | None]] = [song_data]
            await bot.db.execute_fetchone(
                "INSERT INTO music_users(user_id, favorite_songs) VALUES(?,?)",
                (interaction.user.id, str(data)),
            )

            await interaction.send_success_message(
                title=f"Pomyślnie dodano {Emojis.GREENBUTTON.value}",
                description=f"{Emojis.REPLY.value} Dodano wybraną piosenkę do ulubionych",
                ephemeral=True,
            )
        else:
            data: list[dict[str, str | int | None]] = literal_eval(response[0])
            if len(data) >= 25:
                await interaction.send_error_message(
                    description="Osiągnięto limit `25` ulubionych piosenek.",
                    ephemeral=True,
                )
                return

            if song_data in data:
                await interaction.send_error_message(
                    description="Wybrana piosenka już jest w ulubionych.",
                    ephemeral=True,
                )
                return

            data.append(song_data)

            await interaction.send_success_message(
                title=f"Pomyślnie dodano {Emojis.GREENBUTTON.value}",
                description=f"{Emojis.REPLY.value} Dodano wybraną piosenkę do ulubionych",
                ephemeral=True,
            )

            await bot.db.execute_fetchone(
                "UPDATE music_users SET favorite_songs = ? WHERE user_id = ?",
                (str(data), interaction.user.id),
            )


class SelectMusicView(ui.View):
    def __init__(self, tracks: list[Track]):
        super().__init__(timeout=None)

        self.add_item(SelectMusic(tracks))


class CommandFavoriteSongs(CustomCog):
    @MusicCog.main.subcommand(name="ulubione_piosenki")  # pylint: disable=no-member
    async def music_favorite_songs(self, interaction: CustomInteraction):  # pylint: disable=unused-argument
        ...

    @music_favorite_songs.subcommand(
        name="uruchom",
        description="Uruchamia ulubione piosenki",
    )
    async def music_play_favorite_songs(self, interaction: CustomInteraction):
        assert interaction.guild and isinstance(interaction.user, Member)

        await interaction.response.defer()

        response: Optional[DB_RESPONSE] = await self.bot.db.execute_fetchone(
            "SELECT favorite_songs FROM music_users WHERE user_id = ?",
            (interaction.user.id,),
        )

        if not response:
            return await interaction.send_error_message(
                description="Nie posiadasz żadnych ulubionych piosenek."
            )

        songs: list[dict[str, str]] = literal_eval(response[0])

        if not songs:
            return await interaction.send_error_message(
                description="Nie posiadasz żadnych ulubionych piosenek."
            )

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
                player: PlayerT = await interaction.user.voice.channel.connect(  # pyright: ignore
                    cls=MusicPlayer  # pyright: ignore
                )
            except errors.NoNodesAvailable:
                return await interaction.send_error_message(
                    description="Bot nie ma do dyspozycji żadnych wolnych wątków.",
                )
        else:
            player: PlayerT = interaction.guild.voice_client  # pyright: ignore

        assert isinstance(player, MusicPlayer)

        tracks: list[Track] = []

        for song_data in songs:
            songs_found: Optional[list[Track] | Playlist] = await player.fetch_tracks(song_data["url"])
            if isinstance(songs_found, list):
                tracks.append(songs_found[0])

        if not player.current:
            player.queue.extend(tracks[1::])
            __track: Optional[Track] = tracks[0]
            await player.play(tracks[0])
        else:
            __track: Optional[Track] = None
            player.queue.extend(tracks)

        await interaction.send_success_message(
            title=f"Pomyślnie dodano {Emojis.GREENBUTTON.value}",
            description=f"{Emojis.REPLY.value} Pomyślnie dodano ulubione piosenki do kolejki.",
        )

        if __track:
            track_lenght: str = str(timedelta(seconds=__track.length / 1000))

            embed = Embed(
                title="`🔊` Uruchamiam muzykę...",
                colour=Color.dark_theme(),
                timestamp=utils.utcnow(),
            )

            embed.add_field(
                name="`⏰` Długość",
                value=f"{Emojis.REPLY.value} `{track_lenght}`",
            )
            embed.add_field(
                name="`👤` Autor",
                value=f"{Emojis.REPLY.value} `{__track.author}`",
                inline=False,
            )
            embed.add_field(
                name="`📌` Numer w kolejce",
                value=f"{Emojis.REPLY.value} `#{len(tracks)}`",
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

            if isinstance(
                interaction.channel,
                (TextChannel, Thread),
            ):
                await interaction.channel.send(embed=embed)

    @music_favorite_songs.subcommand(
        name="lista",
        description="Lista z ulubionymi piosenkami",
    )
    async def music_list_favorite_song(self, interaction: CustomInteraction):
        assert interaction.user

        await interaction.response.defer(ephemeral=True)

        response: Optional[DB_RESPONSE] = await self.bot.db.execute_fetchone(
            "SELECT favorite_songs FROM music_users WHERE user_id = ?",
            (interaction.user.id,),
        )

        if not response:
            return await interaction.send_error_message(
                description="Nie posiadasz żadnych ulubionych piosenek.",
                ephemeral=True,
            )

        songs: list[dict[str, str]] = literal_eval(response[0])
        if not songs:
            return await interaction.send_error_message(
                description="Nie posiadasz żadnych ulubionych piosenek.",
                ephemeral=True,
            )

        embed = Embed(
            title="`💾` Biblioteka ulubionych piosenek",
            colour=Color.dark_theme(),
            timestamp=utils.utcnow(),
        )
        embed.set_author(
            name=interaction.user,
            icon_url=interaction.user_avatar_url,
        )
        embed.set_thumbnail(url=interaction.guild_icon_url)

        for index, song_data in enumerate(songs):
            if index == 5:
                break

            title: str = song_data["title"]
            url: str = song_data["url"]

            embed.add_field(
                name=f"`🔊` {title}",
                value=f"{Emojis.REPLY.value} [`LINK`]({url})",
                inline=False,
            )
        pages: SongsListView = SongsListView(interaction, songs)
        await interaction.send(
            embed=embed,
            ephemeral=True,
            view=pages,
        )

    @music_favorite_songs.subcommand(
        name="usuń",
        description="Usuwa piosenkę z ulubionych",
    )
    async def music_delete_favorite_song(
        self,
        interaction: CustomInteraction,
        song: str = SlashOption(
            name="piosenka",
            description="Podaj tytuł piosenki",
        ),
    ):
        assert isinstance(interaction.user, Member)

        await interaction.response.defer(ephemeral=True)

        response: Optional[DB_RESPONSE] = await self.bot.db.execute_fetchone(
            "SELECT favorite_songs FROM music_users WHERE user_id = ?",
            (interaction.user.id,),
        )

        if not response:
            return await interaction.send_error_message(
                description="Nie posiadasz żadnych ulubionych piosenek.",
                ephemeral=True,
            )

        songs: list[dict[str, str]] = literal_eval(response[0])

        if not songs:
            return await interaction.send_error_message(
                description="Nie posiadasz żadnych ulubionych piosenek.",
                ephemeral=True,
            )

        for song_data in songs:
            if song_data["title"] == song:
                songs.remove(song_data)

                await interaction.send_success_message(
                    title=f"Pomyślnie usunięto {Emojis.REDBUTTON.value}",
                    description=f"{Emojis.REPLY.value} Usunięto piosenke z ulubionych.",
                    ephemeral=True,
                    color=Color.red(),
                )

                await self.bot.db.execute_fetchone(
                    "UPDATE music_users SET favorite_songs = ? WHERE user_id = ?",
                    (
                        str(songs),
                        interaction.user.id,
                    ),
                )
                return

        return await interaction.send_error_message(
            description="Nie odnalazłem takiej piosenki w twoich ulubionych.",
            ephemeral=True,
        )

    @music_delete_favorite_song.on_autocomplete("song")
    async def song_delete_autocomplete(
        self,
        interaction: CustomInteraction,
        query: Optional[str],
    ) -> Optional[list[str]]:
        assert isinstance(interaction.user, Member)

        response: Optional[DB_RESPONSE] = await self.bot.db.execute_fetchone(
            "SELECT favorite_songs FROM music_users WHERE user_id = ?",
            (interaction.user.id,),
        )

        if not response:
            return None

        songs_data: list[dict[str, str]] = literal_eval(response[0])
        if len(songs_data) == 0:
            return None

        songs_titles: list[str] = []
        for song in songs_data:
            songs_titles.append(song["title"])

        if not query:
            return songs_titles

        get_near_song: list = [title for title in songs_titles if title.lower().startswith(query.lower())]
        return get_near_song

    @music_favorite_songs.subcommand(
        name="dodaj",
        description="Dodaje piosenke do ulubionych",
    )
    async def music_add_favorite_song(
        self,
        interaction: CustomInteraction,
        query: str = SlashOption(
            name="piosenka",
            description="Podaj tytuł piosenki lub jej link.",
        ),
    ):
        await interaction.response.defer(ephemeral=True)

        node: Node = self.bot.pool.label_to_node["MAIN"]

        tracks: Optional[Union[list[Track], Playlist]] = await node.fetch_tracks(
            query=query,
            search_type=SearchType.YOUTUBE.value,
        )

        if not tracks:
            return await interaction.send_error_message(
                description="Nie odnalazłem takiej piosenki.",
                ephemeral=True,
            )

        if isinstance(tracks, Playlist):
            return await interaction.send_error_message(
                description="Niestety, ale nie mogę dodać playlisty do ulubionych piosenek.",
                ephemeral=True,
            )

        embed = Embed(
            title="`🔍️` Wybierz piosenke z listy wyszukiwania.",
            colour=Color.dark_theme(),
            timestamp=utils.utcnow(),
            description=f"{Emojis.REPLY.value} Wybierz z listy, którą piosenkę chcesz dodać.",
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

        await interaction.send(
            embed=embed,
            view=SelectMusicView(tracks),
            ephemeral=True,
        )


def setup(bot: Smiffy):
    bot.add_cog(CommandFavoriteSongs(bot))
