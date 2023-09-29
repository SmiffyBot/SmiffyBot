from __future__ import annotations

from ast import literal_eval
from asyncio import sleep
from json import JSONDecodeError
from typing import TYPE_CHECKING, Optional

import scrapetube
from nextcord import (
    AllowedMentions,
    Color,
    Embed,
    SlashOption,
    TextChannel,
    TextInputStyle,
    Thread,
    errors,
    slash_command,
    ui,
    utils,
)
from requests import exceptions

from enums import Emojis
from utilities import CustomCog, CustomInteraction, PermissionHandler

if TYPE_CHECKING:
    from nextcord.abc import GuildChannel

    from bot import Smiffy
    from typings import DB_RESPONSE


class VideoListener:
    def __init__(self, bot: Smiffy):
        self.bot: Smiffy = bot

        self.yt_data: dict[int, dict[str, list | str | int]] = {}
        self.running_loop: bool = False

        self.delay: int = 6

    def add_new_channel(
        self,
        guild_id: int,
        data: dict[str, list | str | int],
    ) -> None:
        self.yt_data[guild_id] = data

        if not self.running_loop:
            self.bot.logger.debug(f"Creating a new VideoListener loop for the server: {guild_id}")
            self.bot.loop.create_task(self.run_new_loop())

    async def update_video_ids_db(self, guild_id: int, video_ids: list[str]) -> None:
        response: Optional[DB_RESPONSE] = await self.bot.db.execute_fetchone(
            "SELECT * FROM yt_notifications WHERE guild_id = ?",
            (guild_id,),
        )
        if response:
            await self.bot.db.execute_fetchone(
                "UPDATE yt_notifications SET video_ids = ? WHERE guild_id = ?",
                (str(video_ids), guild_id),
            )
        else:
            self.delete_channel_data(guild_id)

    def update_channel_data(
        self,
        guild_id: int,
        data: dict[str, list | str | int],
    ) -> dict:
        channel_data: Optional[dict] = self.yt_data.get(guild_id)

        if not channel_data:
            self.add_new_channel(guild_id, data)
            return data

        channel_data.update(data)
        self.yt_data[guild_id] = channel_data

        self.bot.loop.create_task(
            self.update_video_ids_db(
                guild_id,
                channel_data["video_ids"],
            )
        )
        return channel_data

    def delete_channel_data(self, guild_id: int) -> None:
        try:
            del self.yt_data[guild_id]
        except ValueError:
            return

        async def delete_from_db():
            await self.bot.db.execute_fetchone(
                "DELETE FROM yt_notifications WHERE guild_id = ?",
                (guild_id,),
            )

        self.bot.loop.create_task(delete_from_db())

    async def get_latest_video(self, channel_url: str) -> Optional[str]:
        delay: int = int(self.delay / 2)

        async for video_data in scrapetube.get_channel(
            channel_url=channel_url,
            limit=1,
            sleep=delay,
        ):
            latest_video_id = video_data.get("videoId")
            return latest_video_id

    async def fetch_data(self) -> None:
        for data in await self.bot.db.execute_fetchall("SELECT * FROM yt_notifications"):
            guild_data: dict[str, str | list | int] = {
                "channel_id": data[1],
                "video_ids": literal_eval(data[2]),
                "channel_url": data[3],
                "notify_content": data[4],
            }

            self.add_new_channel(guild_id=data[0], data=guild_data)

    async def run_new_loop(self):
        if self.running_loop:
            return

        self.running_loop = True

        while len(self.yt_data):
            for guild_id in self.yt_data.copy():
                try:
                    channel_data: dict = self.yt_data[guild_id]
                except KeyError:
                    continue

                await sleep(self.delay)

                video_ids: list[Optional[str]] = channel_data["video_ids"]
                channel_url: str = channel_data["channel_url"]
                channel_id: int = channel_data["channel_id"]
                notify_content: str = channel_data["notify_content"]
                latest_video_id: Optional[str] = await self.get_latest_video(channel_url)

                if latest_video_id is not None and latest_video_id not in video_ids:
                    self.bot.logger.debug(f"A new video for the channel has been found: {channel_url}")

                    if None in video_ids:
                        video_ids.remove(None)

                    video_ids.append(latest_video_id)

                    channel_data["video_ids"] = video_ids

                    self.update_channel_data(guild_id, channel_data)

                    channel: Optional[GuildChannel] = await self.bot.cache.get_channel(guild_id, channel_id)

                    if not isinstance(channel, TextChannel):
                        self.delete_channel_data(guild_id)
                        continue

                    try:
                        video_url: str = f"\nhttps://www.youtube.com/watch?v={latest_video_id}"
                        await channel.send(
                            notify_content + video_url,
                            allowed_mentions=AllowedMentions(
                                everyone=True,
                                users=True,
                                roles=True,
                            ),
                        )
                    except (
                        errors.HTTPException,
                        errors.Forbidden,
                    ):
                        pass

        self.running_loop = False
        self.bot.logger.debug("Closing the VideoListener loop")

    @classmethod
    def run(cls, bot: Smiffy) -> VideoListener:
        listener: VideoListener = cls(bot)

        bot.loop.create_task(listener.fetch_data())

        return listener


class ReplyMessageModal(ui.Modal):
    def __init__(
        self,
        channel_id: int,
        channel_url: str,
        latest_video_id: Optional[str],
        video_listener: VideoListener,
    ):
        super().__init__("Ustaw komunikat o nowym filmie / streamie")

        (
            self.channel_id,
            self.channel_url,
            self.latest_video_id,
        ) = (
            channel_id,
            channel_url,
            latest_video_id,
        )

        self.video_listener: VideoListener = video_listener

        self.message: ui.TextInput = ui.TextInput(
            label="Podaj treść powiadomienia.",
            min_length=10,
            max_length=2000,
            style=TextInputStyle.paragraph,
            placeholder="Tekst",
        )

        self.add_item(self.message)

    async def callback(self, interaction: CustomInteraction):
        assert interaction.guild and isinstance(
            interaction.channel,
            (TextChannel, Thread),
        )

        if not self.message.value:
            return await interaction.send_error_message(description="Wystąpił nieoczekiwany błąd.")

        bot: Smiffy = interaction.bot

        response: Optional[DB_RESPONSE] = await bot.db.execute_fetchone(
            "SELECT * FROM yt_notifications WHERE guild_id = ?",
            (interaction.guild.id,),
        )

        if response:
            return await interaction.send_error_message(description="Już posiadasz ustawione powiadomienia.")

        await bot.db.execute_fetchone(
            "INSERT INTO yt_notifications(guild_id, channel_id, video_ids, channel_url, reply_message) "
            "VALUES(?,?,?,?,?)",
            (
                interaction.guild.id,
                self.channel_id,
                str([self.latest_video_id]),
                self.channel_url,
                self.message.value,
            ),
        )

        self.video_listener.add_new_channel(
            guild_id=interaction.guild.id,
            data={
                "channel_id": self.channel_id,
                "video_ids": [self.latest_video_id],
                "channel_url": self.channel_url,
                "notify_content": self.message.value,
            },
        )

        embed = Embed(
            title=f"Pomyślnie ustawiono Powiadomienia {Emojis.GREENBUTTON.value}",
            color=Color.green(),
            description=f"- Kanał: [LINK]({self.channel_url})\n"
            f"- Ostatni film: [LINK](https://youtube.com/watch?v={self.latest_video_id})",
            timestamp=utils.utcnow(),
        )
        embed.set_author(
            name=interaction.user,
            icon_url=interaction.user_avatar_url,
        )
        embed.set_thumbnail(url=interaction.guild_icon_url)

        await interaction.channel.send(embed=embed)

        await interaction.send_success_message(
            title=f"Ustawiono Powiadomienia! {Emojis.GREENBUTTON.value}",
            description=f"{Emojis.REPLY.value} Pamiętaj jednak, że wysyłanie powiadomień o nowych filmach / streamach"
            f" trwa dłużej dla małych kanałów **(nawet do 10min)**.",
            color=Color.dark_theme(),
            ephemeral=True,
        )


class CommandYoutubeNotify(CustomCog):
    def __init__(self, bot: Smiffy):
        super().__init__(bot)

        self.video_listener: VideoListener = VideoListener.run(bot)

    @slash_command(name="powiadomienia", dm_permission=False)
    async def notify(self, interaction: CustomInteraction) -> None:
        pass

    @notify.subcommand(name="youtube")
    async def notify_youtube(self, interaction: CustomInteraction):
        pass

    @notify_youtube.subcommand(  # pyright: ignore
        name="włącz",
        description="Włącza powiadomienia o nowych filmach / streamach z twojego kanału.",
    )
    @PermissionHandler(manage_channels=True)
    async def notify_youtube_add(
        self,
        interaction: CustomInteraction,
        text_channel: TextChannel = SlashOption(
            name="kanał_powiadomień",
            description="Wybierz kanał do wysyłania powiadomień",
        ),
        youtube_channel: str = SlashOption(
            name="link_do_kanału",
            description="Podaj link do swojego kanału youtube",
        ),
    ):
        try:
            if "channel" not in youtube_channel and "@" not in youtube_channel:
                raise exceptions.MissingSchema("Invalid channel link.")

            latest_video_id: Optional[str] = None
            channel = scrapetube.get_channel(
                channel_url=youtube_channel,
                limit=1,
            )

            async for data in channel:
                latest_video_id = data["videoId"]
                break

        except (
            exceptions.MissingSchema,
            JSONDecodeError,
        ):
            return await interaction.send_error_message(description="Nieprawidłowy link do kanału youtube.")

        modal = ReplyMessageModal(
            text_channel.id,
            youtube_channel,
            latest_video_id,
            self.video_listener,
        )
        await interaction.response.send_modal(modal)

    @notify_youtube.subcommand(  # pyright: ignore
        name="wyłącz",
        description="Wyłącz powiadomienia o nowych filmach / streamach.",
    )
    @PermissionHandler(manage_channels=True)
    async def notify_youtube_off(self, interaction: CustomInteraction):
        assert interaction.guild

        response: Optional[DB_RESPONSE] = await self.bot.db.execute_fetchone(
            "SELECT * FROM yt_notifications WHERE guild_id = ?",
            (interaction.guild.id,),
        )

        if not response:
            return await interaction.send_error_message(description="Powiadomienia nie są włączone.")

        await self.bot.db.execute_fetchone(
            "DELETE FROM yt_notifications WHERE guild_id = ?",
            (interaction.guild.id,),
        )

        self.video_listener.delete_channel_data(guild_id=interaction.guild.id)

        return await interaction.send_success_message(
            title=f"Pomyślnie wyłączono Powiadomienia {Emojis.GREENBUTTON.value}",
            description=f"{Emojis.REPLY.value} Powiadomienia z kanału youtube zostały wyłączone.",
        )


def setup(bot: Smiffy):
    bot.add_cog(CommandYoutubeNotify(bot))
