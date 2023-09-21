from __future__ import annotations

from ast import literal_eval
from time import mktime
from typing import TYPE_CHECKING, Iterable, Optional

from easy_pil import Editor, Font, load_image_async
from nextcord import Color, Embed, File, Role, TextChannel, errors, utils

from enums import Emojis
from utilities import CustomCog

if TYPE_CHECKING:
    from nextcord import Guild, Invite, Member, User
    from nextcord.abc import GuildChannel

    from bot import Smiffy
    from typings import DB_RESPONSE


class MemberJoin(CustomCog):
    @staticmethod
    def format_text(main_text: str, first_text: str, second_text: str, member: Member) -> Iterable[str]:
        for text in (main_text, first_text, second_text):
            yield text.replace("{user}", str(member)).replace("{user_name}", member.name).replace(
                "{user_discriminator}", "#" + member.discriminator
            ).replace("{user_id}", str(member.id)).replace("{guild_name}", member.guild.name).replace(
                "{guild_total_members}", str(member.guild.member_count)
            ).replace(
                "{guild_id}", str(member.guild.id)
            )

    async def create_welcome_file(self, data: tuple, member: Member) -> File:
        main_text: str = data[0]
        second_text: str = data[1]
        third_text: str = data[2]

        main_text, second_text, third_text = self.format_text(main_text, second_text, third_text, member)

        user_avatar = self.avatars.get_user_avatar(member)

        background: Editor = Editor("./Data/images/welcome_image.jpg")
        profile_image = await load_image_async(user_avatar)

        profile = Editor(profile_image).resize((400, 400)).circle_image()
        poppins = Font.poppins(size=90, variant="bold")

        poppins_medium = Font.poppins(size=65, variant="bold")
        poppins_small = Font.poppins(size=60, variant="light")

        background.paste(profile, (760, 170))
        background.ellipse((760, 170), 400, 400, outline="#fff", stroke_width=4)

        background.text((950, 610), f"{main_text}", color="#07f763", font=poppins, align="center")
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

        _file = File(fp=background.image_bytes, filename="welcomecard.jpg")

        return _file

    async def update_invites(self, inviter: User, member: Member, normal: int = 0, fake: int = 0):
        response: Optional[DB_RESPONSE] = await self.bot.db.execute_fetchone(
            "SELECT normal, fake, invited FROM user_invites WHERE guild_id = ? AND user_id = ?",
            (member.guild.id, inviter.id),
        )

        if not response:
            return await self.bot.db.execute_fetchone(
                "INSERT INTO user_invites(guild_id, user_id, normal, left, fake, bonus, invited) VALUES(?,?,?,?,?,?,?)",
                (member.guild.id, inviter.id, normal, 0, fake, 0, f"[{member.id}]"),
            )

        normal_i, fake_i = response[0:2]

        normal_i += normal
        fake_i += fake

        invited: list[int] = literal_eval(response[2])

        if member.id not in invited:
            invited.append(member.id)

        await self.bot.db.execute_fetchone(
            "UPDATE user_invites SET normal = ?, fake = ?, invited = ? WHERE guild_id = ? AND user_id = ?",
            (normal_i, fake_i, str(invited), member.guild.id, inviter.id),
        )

    @staticmethod
    def format_invite_notify(content: str, inviter: User, joiner: Member, inviter_invites: int) -> str:
        content = (
            content.replace("{user}", str(joiner))
            .replace("{user_name}", str(joiner.name))
            .replace("{user_mention}", str(joiner.mention))
            .replace("{user_discriminator}", str(joiner.discriminator))
            .replace("{user_id}", str(joiner.id))
            .replace("{guild_name}", str(joiner.guild.name))
            .replace("{guild_total_members}", str(joiner.guild.member_count))
            .replace("{guild_id}", str(joiner.guild.id))
            .replace("{inviter}", str(inviter))
            .replace("{inviter_name}", str(inviter.name))
            .replace("{inviter_mention}", str(inviter.mention))
            .replace("{inviter_discriminator}", str(inviter.discriminator))
            .replace("{inviter_id}", str(inviter.id))
            .replace("{inviter_total_invites}", str(inviter_invites))
        )

        return content

    async def handle_invites_notify(self, data: dict, inviter: Optional[User], joiner: Member):
        channel_id: int = data["notify_channel"]
        notify_content: str = data["notify_content"]

        channel: Optional[GuildChannel] = await self.bot.getch_channel(channel_id)

        if not isinstance(channel, TextChannel):
            return

        if inviter:
            (
                normal,
                left,
                fake,  # pylint: disable=unused-variable
                bonus,
            ) = await self.get_user_invites(joiner.guild.id, inviter.id)
            total: int = (normal - left) + bonus

            formatted_content: str = self.format_invite_notify(notify_content, inviter, joiner, total)

            try:
                await channel.send(formatted_content)
            except (errors.Forbidden, errors.HTTPException):
                pass
        else:
            try:
                await channel.send(
                    f"Nie jestem w stanie sprawdzić kto zaprosił: **{joiner}**. "
                    f"Być może to zaproszenie tymczasowe."
                )
            except (errors.Forbidden, errors.HTTPException):
                pass

    async def handle_invites(self, member: Member):
        guild: Guild = member.guild

        guild_invites_data: Optional[DB_RESPONSE] = await self.get_guild_invites_data(guild)

        if not guild_invites_data:
            return

        try:
            notify_data: Optional[dict] = literal_eval(guild_invites_data[3])
        except ValueError:
            notify_data = None

        invites_data: list[dict] = literal_eval(guild_invites_data[1])

        guild_invites: list[Invite] = await guild.invites()
        inviter: Optional[User] = None

        for guild_invite, db_invite in zip(guild_invites, invites_data):
            if guild_invite.inviter and guild_invite.inviter.id == db_invite["inviter_id"]:
                if db_invite["invite_uses"] + 1 == guild_invite.uses:
                    now = utils.utcnow()
                    inviter = guild_invite.inviter

                    if (now.year, now.month) == (
                        member.created_at.year,
                        member.created_at.month,
                    ):
                        if now.day - member.created_at.day < 7:
                            return await self.update_invites(
                                inviter=guild_invite.inviter, member=member, fake=1
                            )

                    await self.update_invites(inviter=guild_invite.inviter, member=member, normal=1)

        self.bot.dispatch("invite_update", member.guild)
        # Even if the bot did not find an inviter we still update,
        # because used invites may have changed while the bot was offline.

        if notify_data:
            await self.handle_invites_notify(notify_data, inviter, member)

    @CustomCog.listener()
    async def on_member_join(self, member: Member):
        await self.handle_invites(member)

        logs_channel: Optional[GuildChannel] = await self.get_logs_channel(member.guild)

        if isinstance(logs_channel, TextChannel):
            try:
                account_age_timestamp: str = f"<t:{int(mktime(member.created_at.timetuple()))}:R>"
                account_age: str = str(member.created_at)[0:19]

                embed = Embed(
                    title="<:user2:992156083231666267> Dołączył nowy użytkownik!",
                    color=Color.green(),
                    timestamp=utils.utcnow(),
                    description=f"{Emojis.REPLY.value} **Wiek konta:** `{account_age}` ({account_age_timestamp})",
                )

                embed.add_field(
                    name="`⚙️` Identyfikator",
                    value=f"{Emojis.REPLY.value} `{member.id}`",
                )

                embed.add_field(
                    name="`👥` Osoby",
                    value=f"{Emojis.REPLY.value} `{member.guild.member_count}`",
                )

                embed.set_author(name=member, icon_url=self.avatars.get_user_avatar(member))
                embed.set_thumbnail(url=self.avatars.get_guild_icon(member.guild))

                embed.set_footer(text=f"Smiffy v{self.bot.__version__}", icon_url=self.bot.avatar_url)

                await logs_channel.send(embed=embed)

            except (errors.HTTPException, errors.Forbidden):
                pass

        startrole_response: Optional[DB_RESPONSE] = await self.bot.db.execute_fetchone(
            "SELECT role_id FROM startrole WHERE guild_id = ?", (member.guild.id,)
        )

        if startrole_response and startrole_response[0]:
            try:
                role: Optional[Role] = await self.bot.getch_role(member.guild, startrole_response[0])
                if role:
                    await member.add_roles(role, reason="Smiffy - (StartRole)")
            except (errors.Forbidden, errors.HTTPException):
                pass

        welcomes_response: Optional[DB_RESPONSE] = await self.bot.db.execute_fetchone(
            "SELECT welcome_channel_id, welcome_data FROM welcomes WHERE guild_id = ?",
            (member.guild.id,),
        )

        if welcomes_response and welcomes_response[0]:
            lobby_channel: Optional[GuildChannel] = await self.bot.getch_channel(welcomes_response[0])
            if isinstance(lobby_channel, TextChannel):
                try:
                    data: tuple[str, ...] = literal_eval(welcomes_response[1])
                    file: File = await self.create_welcome_file(data, member)

                    await lobby_channel.send(file=file, content=f"{member.mention}")
                except (errors.HTTPException, errors.Forbidden):
                    pass


def setup(bot: Smiffy):
    bot.add_cog(MemberJoin(bot))
