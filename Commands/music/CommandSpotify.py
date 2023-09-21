from __future__ import annotations

from asyncio import sleep
from datetime import timedelta
from typing import TYPE_CHECKING, Any

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
from errors import MissingSpotifyData
from utilities import CustomCog, CustomInteraction, PermissionHandler, bot_utils

from .__main__ import MusicCog, MusicPlayer
from .CommandPlay import MusicManagerView

if TYPE_CHECKING:
    from mafic import Node, Track

    from bot import Smiffy
    from typings import DB_RESPONSE, PlayerT
    from utilities import ClientResponse, Optional


class SelectPlaylist(ui.Select):
    def __init__(
        self,
        playlists_data: dict[str, list[dict]],
        cog: CommandSpotify,
    ):
        self.cog: CommandSpotify = cog

        options: list[SelectOption] = []

        for playlist_data in playlists_data["items"]:
            tracks_data: dict = playlist_data["tracks"]
            if tracks_data["total"] == 0:
                continue

            description: str = playlist_data["description"]
            if len(description) >= 100:
                description: str = description[0:100]

            options.append(
                SelectOption(
                    label=playlist_data["name"],
                    value=playlist_data["id"],
                    description=description,
                    emoji="<:spotify_logo:1142231812068888666>",
                )
            )

            if len(options) == 25:
                # Discord limitation
                break

        super().__init__(
            placeholder="Wybierz playliste",
            options=options,
        )

    async def get_tracks_links(
        self,
        bot: Smiffy,
        playlist_id: str,
        inter: CustomInteraction,
    ) -> list[str]:
        tracks_links: list[str] = []

        headers: dict[str, str] = {"Authorization": f"Bearer {self.cog.authorization_token}"}

        response: ClientResponse = await bot.session.get(
            url=f"https://api.spotify.com/v1/playlists/{playlist_id}/tracks",
            headers=headers,
        )

        if response.status == 429:
            await self.cog.handle_ratelimit(inter, response)
            return []

        if response.status == 401:
            await inter.send_error_message(
                description="Wygląda na to, że bot napotkał nieoczekiwany błąd. Spróbuj ponownie.",
            )
            return []

        if response.status == 404:
            await inter.send_error_message(description="Wystąpił problem z twoim kontem spotify.")
            return []

        data: dict = await response.json()
        playlist_tracks: list[dict] = data["items"]

        for playlist_data in playlist_tracks:
            if not playlist_data.get("track"):
                await inter.send_error_message(
                    description="Playlista nie zawiera tylko piosenek - nie może zostać wczytana.",
                )

                return []

            track_data: dict = playlist_data["track"]
            track_id: str = track_data["id"]
            tracks_links.append(f"https://open.spotify.com/track/{track_id}")

        return tracks_links

    async def callback(self, interaction: CustomInteraction) -> None:
        assert isinstance(interaction.user, Member)
        assert interaction.guild

        await interaction.response.defer()

        playlist_id: str = self.values[0]
        bot: Smiffy = interaction.bot

        tracks_links: list[str] = await self.get_tracks_links(
            bot=bot,
            playlist_id=playlist_id,
            inter=interaction,
        )
        if not tracks_links:
            return

        try:
            node: Node = bot.pool.label_to_node["Smiffy-Europe"]
        except KeyError:
            await interaction.send_error_message(
                description="Wygląda na to, że bot nie zdołał się jeszcze w pełni uruchomić.",
            )
            return

        tracks: list[Track] = []

        for uri in tracks_links:
            if not uri:
                continue

            _track: Optional[list[Track] | Playlist] = await node.fetch_tracks(
                query=uri,
                search_type=SearchType.SPOTIFY_SEARCH.value,
            )

            if isinstance(_track, list):
                tracks.append(_track[0])

        if not interaction.user.voice or not interaction.user.voice.channel:
            await interaction.send_error_message(
                description="Aby użyć tej funkcji musisz znajdować się na kanale głosowym.",
            )
            return

        if interaction.guild.me.voice and interaction.guild.me.voice.channel:
            if interaction.user.voice.channel.id != interaction.guild.me.voice.channel.id:
                await interaction.send_error_message(
                    description="Aby użyć tej funkcji musisz znajdować się na tym samym kanale co bot.",
                )
                return

        if not interaction.guild.voice_client:
            try:
                player: PlayerT = await interaction.user.voice.channel.connect(  # pyright: ignore
                    cls=MusicPlayer  # pyright: ignore
                )
            except errors.NoNodesAvailable:
                await interaction.send_error_message(
                    description="Bot nie ma do dyspozycji żadnych wolnych wątków. Spróbuj ponownie później.",
                )
                return
        else:
            player: PlayerT = interaction.guild.voice_client  # pyright: ignore

        assert isinstance(player, MusicPlayer)

        if interaction.guild.me.voice:
            await interaction.guild.change_voice_state(
                channel=interaction.guild.me.voice.channel,
                self_deaf=True,
            )

        player._connected = True

        if len(player.queue) >= 100:
            await interaction.send_error_message(
                description="Osiągnięto limit piosenek w kolejce. **100/100**",
            )
            return None

        if len(tracks) == 0:
            await interaction.send_error_message(description="Wystąpił błąd z twoją playlista.")
            return

        if len(tracks) > 100:
            tracks = tracks[0:100]

        if not player.current:
            if len(tracks) <= 1:
                player.queue.extend(tracks)
                __track: Optional[Track] = None
            else:
                player.queue.extend(tracks[1::])
                __track: Optional[Track] = tracks[0]
                await player.play(__track)

        else:
            __track: Optional[Track] = None
            for track_to_queue in tracks.copy():
                if len(player.queue) != 100:
                    player.queue.extend([track_to_queue])
                else:
                    tracks.remove(track_to_queue)

        total_seconds: int = 0
        for track in tracks:
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
            value=f"{Emojis.REPLY.value} `{len(tracks)}`",
            inline=False,
        )

        embed.set_footer(
            text=f"Smiffy v{bot.__version__} | Mafic v{__version__}",
            icon_url=bot.avatar_url,
        )

        if tracks[0]:
            embed.set_thumbnail(url=tracks[0].artwork_url)

        embed.set_author(
            name=interaction.user,
            icon_url=interaction.user_avatar_url,
        )
        buttons_view = MusicManagerView(
            player=player,
            author_id=interaction.user.id,
        )
        await interaction.send(embed=embed, view=buttons_view)

        if __track:
            track_lenght: str = str(timedelta(seconds=int(__track.length / 1000)))

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
                value=f"{Emojis.REPLY.value} `#{len(player.queue)}`",
            )

            embed.set_footer(
                text=f"Smiffy v{bot.__version__} | Mafic v{__version__}",
                icon_url=bot.avatar_url,
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


class SelectPlaylistView(ui.View):
    def __init__(
        self,
        playlists_data: dict[str, list[dict]],
        cog: CommandSpotify,
    ):
        super().__init__(timeout=None)

        self.add_item(SelectPlaylist(playlists_data, cog))


class CommandSpotify(CustomCog):
    def __init__(self, bot: Smiffy):
        super().__init__(bot)

        self.authorization_token: Optional[str] = None
        self.bot.loop.create_task(self.get_access_token())

    @staticmethod
    async def handle_ratelimit(
        inter: CustomInteraction,
        response: ClientResponse,
    ) -> None:
        if response.headers.get("Retry-After"):
            seconds: int = int(response.headers["Retry-After"]) + 1

            await inter.send_error_message(
                description=f"**Wygląda na to, że bot osiągnął limit requestów do Spotify.** "
                f"Spróbuj ponownie za `{seconds}s`",
            )
            return

        await inter.send_error_message(
            description="**Wygląda na to, że bot osiągnął limit requestów do Spotify.** "
            "Spróbuj ponownie później.",
        )

    async def get_access_token(self):
        await self.bot.wait_until_ready()

        client_id: Optional[str] = bot_utils.get_value_from_config("SPOTIFY_CLIENT_ID")
        client_secret: Optional[str] = bot_utils.get_value_from_config("SPOTIFY_CLIENT_SECRET")

        if not client_secret or not client_id:
            self.bot.logger.error("Connection to Spotify API failed.")
            raise MissingSpotifyData

        async def get_app_data(secret: str, _id: str) -> Optional[dict]:
            url: str = "https://accounts.spotify.com/api/token"

            headers: dict = {"Content-Type": "application/x-www-form-urlencoded"}

            data: dict = {
                "grant_type": "client_credentials",
                "client_id": _id,
                "client_secret": secret,
            }

            response: ClientResponse = await self.bot.session.post(
                url=url,
                data=data,
                headers=headers,
            )
            if response.status != 200:
                self.bot.logger.error("Connection to Spotify API failed. Invalid parameters.")
                return None

            return await response.json()

        app_data: Optional[dict] = await get_app_data(client_secret, client_id)

        if app_data:
            self.authorization_token = app_data["access_token"]
            interval: int = app_data["expires_in"]
            self.bot.logger.info("Connected to Spotify API.")

            while True:
                await sleep(interval)

                app_data = await get_app_data(client_secret, client_id)

                self.bot.logger.debug(f"Spotify API response has been received: {app_data}")

                if not app_data:
                    self.bot.logger.error("Spotify API connection has been terminated.")
                    break

                self.authorization_token = app_data["access_token"]
                interval: int = app_data["expires_in"]

                self.bot.logger.debug("Keeping alive connection to the Spotify API.")

    @MusicCog.main.subcommand(name="spotify")  # pylint: disable=no-member
    async def music_spotify(self, interaction: CustomInteraction):  # pylint: disable=unused-argument
        ...

    @music_spotify.subcommand(  # pyright: ignore
        name="playlisty",
        description="Wyświetla playliste możliwe do odtworzenia",
    )
    @PermissionHandler(user_role_has_permission="music")
    async def music_spotify_playlists(self, interaction: CustomInteraction):
        assert isinstance(interaction.user, Member)

        await interaction.response.defer()

        db_response: Optional[DB_RESPONSE] = await self.bot.db.execute_fetchone(
            "SELECT spotify_account FROM music_users WHERE user_id = ?",
            (interaction.user.id,),
        )
        if not db_response or not db_response[0]:
            return await interaction.send_error_message(
                description="Nie posiadasz podłączonego konta spotify."
            )

        account_id: str = db_response[0]

        url: str = f"https://api.spotify.com/v1/users/{account_id}/playlists?limit=25"
        headers: dict[str, str] = {"Authorization": f"Bearer {self.authorization_token}"}

        response: ClientResponse = await self.bot.session.get(url=url, headers=headers)

        if response.status == 429:
            await self.handle_ratelimit(interaction, response)
            return

        if response.status == 401:
            return await interaction.send_error_message(
                description="Wygląda na to, że bot napotkał nieoczekiwany błąd. Spróbuj ponownie.",
            )

        if response.status == 404:
            return await interaction.send_error_message(
                description="Wystąpił problem z twoim kontem spotify."
            )

        response_data: dict = await response.json()

        if len(response_data) == 0:
            return await interaction.send_error_message(
                description="Twoje konto spotify nie posiada żadnych playlist.",
            )

        embed = Embed(
            title="`🔊` Wybierz playliste do odtworzenia",
            description=f"{Emojis.REPLY.value} Wybierz playliste, którą chcesz odtworzyć.",
            timestamp=utils.utcnow(),
            colour=Color.dark_theme(),
        )
        embed.set_author(
            name=interaction.user,
            icon_url=interaction.user_avatar_url,
        )
        embed.set_thumbnail(url=interaction.guild_icon_url)
        view = SelectPlaylistView(response_data, self)
        await interaction.send(embed=embed, view=view)

    @music_spotify.subcommand(
        name="odłącz_konto",
        description="Odłącza konto spotify od konta discord",
    )
    async def music_spotify_disconnect(self, interaction: CustomInteraction):
        assert isinstance(interaction.user, Member)

        await interaction.response.defer()

        db_response: Optional[DB_RESPONSE] = await self.bot.db.execute_fetchone(
            "SELECT spotify_account FROM music_users WHERE user_id = ?",
            (interaction.user.id,),
        )
        if not db_response or not db_response[0]:
            return await interaction.send_error_message(
                description="Nie posiadasz podłączonego konta spotify."
            )

        await self.bot.db.execute_fetchone(
            "UPDATE music_users SET spotify_account = ? WHERE user_id = ?",
            (None, interaction.user.id),
        )

        await interaction.send_success_message(
            title=f"Pomyślnie odłączono {Emojis.GREENBUTTON.value}",
            description=f"{Emojis.REPLY.value} Odłączono konto spotify.",
        )

    @music_spotify.subcommand(
        name="podłącz_konto",
        description="Łączy twoje konto discord z kotnem spotify",
    )
    async def music_spotify_connect(
        self,
        interaction: CustomInteraction,
        account_url: str = SlashOption(
            name="link_do_konta",
            description="Podaj link do twojego konta spotify",
            min_length=10,
        ),
    ):
        assert isinstance(interaction.user, Member)

        await interaction.response.defer()

        if not self.authorization_token:
            return await interaction.send_error_message(
                description="Bot nie został jeszcze w pełni uruchomiony."
            )

        if not account_url.startswith("https://"):
            account_url = "https://" + account_url

        if account_url[0:30] != "https://open.spotify.com/user/":
            return await interaction.send_error_message(description="Nieprawidłowy link do profilu.")

        url_segments: list[str] = account_url.split("/")
        account_id: str = url_segments[-1]

        url: str = f"https://api.spotify.com/v1/users/{account_id}"
        headers: dict[str, str] = {"Authorization": f"Bearer {self.authorization_token}"}

        response: ClientResponse = await self.bot.session.get(url=url, headers=headers)

        if response.status == 429:
            await self.handle_ratelimit(interaction, response)
            return

        if response.status == 401:
            return await interaction.send_error_message(
                description="Wygląda na to, że bot napotkał nieoczekiwany błąd. Spróbuj ponownie.",
            )

        if response.status == 404:
            return await interaction.send_error_message(description="Nie odnalazłem twojego konta spotify.")

        db_response: Optional[DB_RESPONSE] = await self.bot.db.execute_fetchone(
            "SELECT spotify_account FROM music_users WHERE user_id = ?",
            (interaction.user.id,),
        )

        if db_response and db_response[0]:
            return await interaction.send_error_message(description="Już masz podłączone konto spotify.")

        user_data: dict[str, Any] = await response.json()

        try:
            display_name: str = user_data["display_name"]
            account_link: str = user_data["external_urls"]["spotify"]
        except KeyError:
            return await interaction.send_error_message(
                description="Wystąpił błąd podczas pozyskawania informacji o twoim koncie."
            )

        if not db_response:
            await self.bot.db.execute_fetchone(
                "INSERT INTO music_users(user_id, favorite_songs, spotify_account) VALUES(?,?,?)",
                (
                    interaction.user.id,
                    "[]",
                    account_id,
                ),
            )
        else:
            await self.bot.db.execute_fetchone(
                "UPDATE music_users SET spotify_account = ? WHERE user_id = ?",
                (account_id, interaction.user.id),
            )

        await interaction.send_success_message(
            title=f"Pomyślnie podłączono {Emojis.GREENBUTTON.value}",
            description=f"{Emojis.REPLY.value} Konto: [{display_name}]({account_link}) zostało podłączone.",
        )


def setup(bot: Smiffy):
    bot.add_cog(CommandSpotify(bot))
