from __future__ import annotations

from ast import literal_eval
from time import mktime
from typing import TYPE_CHECKING, Iterable, Optional

from easy_pil import Editor, Font, load_image_async
from nextcord import Color, Embed, File, TextChannel, errors, utils

from enums import Emojis
from utilities import CustomCog

if TYPE_CHECKING:
    from nextcord import Guild, Member, RawMemberRemoveEvent, User
    from nextcord.abc import GuildChannel

    from bot import Smiffy
    from typings import DB_RESPONSE


class MemberLeaveEvent(CustomCog):
    @staticmethod
    def format_text(
        main_text: str,
        first_text: str,
        second_text: str,
        member: User,
        guild: Guild,
    ) -> Iterable[str]:
        for text in (
            main_text,
            first_text,
            second_text,
        ):
            yield text.replace("{user}", str(member)).replace("{user_name}", member.name).replace(
                "{user_discriminator}",
                "#" + member.discriminator,
            ).replace("{user_id}", str(member.id)).replace("{guild_name}", guild.name).replace(
                "{guild_total_members}",
                str(guild.member_count),
            ).replace(
                "{guild_id}", str(guild.id)
            )

    async def create_welcome_file(
        self,
        data: tuple[str, ...],
        member: User,
        guild: Guild,
    ) -> File:
        main_text: str = data[0]
        second_text: str = data[1]
        third_text: str = data[2]

        (
            main_text,
            second_text,
            third_text,
        ) = self.format_text(
            main_text,
            second_text,
            third_text,
            member,
            guild,
        )

        user_avatar = self.avatars.get_user_avatar(member)

        background: Editor = Editor("./Data/images/welcome_image.jpg")
        profile_image = await load_image_async(user_avatar)

        profile = Editor(profile_image).resize((400, 400)).circle_image()
        poppins = Font.poppins(size=90, variant="bold")

        poppins_medium = Font.poppins(size=65, variant="bold")
        poppins_small = Font.poppins(size=60, variant="light")

        background.paste(profile, (760, 170))
        background.ellipse(
            (760, 170),
            400,
            400,
            outline="#fff",
            stroke_width=4,
        )

        background.text(
            (950, 610),
            f"{main_text}",
            color="#07f763",
            font=poppins,
            align="center",
        )
        background.text(
            (950, 730),
            f"{second_text}",
            color="#fff",
            font=poppins_medium,
            align="center",
        )
        background.text(
            (950, 840),
            f"{third_text}",
            color="#e8dfdf",
            font=poppins_small,
            align="center",
        )

        _file = File(
            fp=background.image_bytes,
            filename="welcomecard.jpg",
        )

        return _file

    @staticmethod
    async def handle_invites_notify(
        inviter: Optional[Member],
        channel: TextChannel,
        user: User,
    ):
        if not inviter:
            try:
                await channel.send(
                    f"Użytkownik **{user}** Wyszedł z serwera. "
                    f"Nie jestem w stanie sprawdzić kto go zaprosił."
                )
            except (
                errors.Forbidden,
                errors.HTTPException,
            ):
                pass
        else:
            try:
                await channel.send(
                    f"Użytkownik **{user}** Wyszedł z serwera. "
                    f"Został on zaproszony przez: {inviter.mention}."
                )
            except (
                errors.Forbidden,
                errors.HTTPException,
            ):
                pass

    async def update_invites(self, member: User, guild: Guild):
        guild_invites_data: Optional[DB_RESPONSE] = await self.get_guild_invites_data(guild)

        if guild_invites_data is None:
            return

        users: Iterable[DB_RESPONSE] = await self.bot.db.execute_fetchall(
            "SELECT * FROM user_invites WHERE guild_id = ?",
            (guild.id,),
        )

        inviter_id: Optional[int] = None

        for user_data in users:
            invited: str = user_data[6]

            if invited != "[]":
                invited_users: list[int] = literal_eval(invited)
                if member.id in invited_users:
                    invited_users.remove(member.id)

                    inviter_id = user_data[1]

                    await self.bot.db.execute_fetchone(
                        "UPDATE user_invites SET left = left + 1, invited = ? WHERE guild_id = ? AND user_id = ?",
                        (
                            str(invited_users),
                            guild.id,
                            inviter_id,
                        ),
                    )

        if guild_invites_data[3]:
            notify_data: dict = literal_eval(guild_invites_data[3])

            inviter: Optional[Member] = None

            if inviter_id:
                inviter: Optional[Member] = await self.bot.getch_member(guild, inviter_id)

            channel: Optional[GuildChannel] = await self.bot.getch_channel(notify_data["notify_channel"])
            if isinstance(channel, TextChannel):
                await self.handle_invites_notify(inviter, channel, member)

    @CustomCog.listener()
    async def on_raw_member_remove(self, event_data: RawMemberRemoveEvent):
        guild: Optional[Guild] = await self.bot.getch_guild(event_data.guild_id)

        if guild:
            await self.update_invites(event_data.user, guild)

        logs_response: Optional[DB_RESPONSE] = await self.bot.db.execute_fetchone(
            "SELECT channel_id FROM server_logs WHERE guild_id = ?",
            (event_data.guild_id,),
        )

        if logs_response:
            logs_channel: Optional[GuildChannel] = await self.bot.getch_channel(logs_response[0])

            account_age_timestamp: str = f"<t:{int(mktime(event_data.user.created_at.timetuple()))}:R>"
            account_age: str = str(event_data.user.created_at)[0:19]

            if isinstance(logs_channel, TextChannel):
                embed = Embed(
                    title="<:user3:992156113678110780> Użytkownik wyszedł!",
                    color=Color.red(),
                    timestamp=utils.utcnow(),
                    description=f"{Emojis.REPLY.value} **Wiek konta:** `{account_age}` ({account_age_timestamp})",
                )
                embed.add_field(
                    name="`⚙️` Identyfikator",
                    value=f"{Emojis.REPLY.value} `{event_data.user.id}`",
                )

                if guild:
                    embed.add_field(
                        name="`👥` Osoby",
                        value=f"{Emojis.REPLY.value} `{guild.member_count}`",
                    )

                embed.set_author(
                    name=event_data.user,
                    icon_url=self.avatars.get_user_avatar(event_data.user),
                )
                embed.set_thumbnail(url=self.avatars.get_guild_icon(guild))

                embed.set_footer(
                    text=f"Smiffy v{self.bot.__version__}",
                    icon_url=self.bot.avatar_url,
                )

                try:
                    await logs_channel.send(embed=embed)
                except (
                    errors.HTTPException,
                    errors.Forbidden,
                ):
                    pass

        lobby_response: Optional[DB_RESPONSE] = await self.bot.db.execute_fetchone(
            "SELECT goodbye_channel_id, goodbye_data FROM goodbyes WHERE guild_id = ?",
            (event_data.guild_id,),
        )
        if lobby_response and lobby_response[0] and guild:
            lobby_channel: Optional[GuildChannel] = await self.bot.getch_channel(lobby_response[0])

            if isinstance(lobby_channel, TextChannel):
                data: tuple[str, ...] = literal_eval(lobby_response[1])
                file: File = await self.create_welcome_file(data, event_data.user, guild)

                try:
                    await lobby_channel.send(file=file)
                except (
                    errors.HTTPException,
                    errors.Forbidden,
                ):
                    pass


def setup(bot: Smiffy):
    bot.add_cog(MemberLeaveEvent(bot))
