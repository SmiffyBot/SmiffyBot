from __future__ import annotations

from typing import TYPE_CHECKING, Iterable, Optional

from nextcord import Color, Embed, TextChannel, errors, utils

from enums import Emojis
from utilities import CustomCog, check_giveaway_requirement

if TYPE_CHECKING:
    from nextcord import (
        Member,
        Message,
        PartialEmoji,
        PartialMessage,
        RawReactionActionEvent,
        Role,
    )
    from nextcord.abc import GuildChannel

    from bot import Smiffy
    from typings import DB_RESPONSE


class ReactionUpdateEvent(CustomCog):
    @CustomCog.listener()
    async def on_raw_reaction_add(self, payload: RawReactionActionEvent):
        channel: Optional[GuildChannel] = await self.bot.getch_channel(payload.channel_id)

        if not isinstance(channel, TextChannel):
            return

        message: PartialMessage = channel.get_partial_message(payload.message_id)
        member: Optional[Member] = await self.bot.getch_member(channel.guild, payload.user_id)

        if not member or member.bot:
            return

        clicked_emoji: PartialEmoji = payload.emoji

        assert message.guild

        reactionroles_response: Iterable[DB_RESPONSE] = await self.bot.db.execute_fetchall(
            "SELECT * FROM reactionroles WHERE guild_id = ? AND message_id = ?",
            (message.guild.id, message.id),
        )

        if reactionroles_response:
            embed = Embed(
                title=f"Otrzymałeś/aś role {Emojis.GREENBUTTON.value}",
                color=Color.green(),
                timestamp=utils.utcnow(),
            )
            embed.set_author(
                name=member,
                icon_url=self.avatars.get_user_avatar(member),
            )
            embed.set_thumbnail(url=self.avatars.get_guild_icon(channel.guild))

            for data in reactionroles_response:
                if data[4] == str(clicked_emoji):
                    role: Optional[Role] = await self.bot.getch_role(channel.guild, data[3])
                    if not role:
                        embed = Embed(
                            title=f"{Emojis.REDBUTTON.value} Wystąpił bląd.",
                            description=f"{Emojis.REPLY.value} Nie mogłem nadać roli.\n\n"
                            f"(Rola nie została odnaleźiona)",
                            colour=Color.red(),
                            timestamp=utils.utcnow(),
                        )
                        embed.set_author(
                            name=member,
                            icon_url=self.avatars.get_user_avatar(member),
                        )
                        embed.set_thumbnail(url=self.avatars.get_guild_icon(channel.guild))
                        try:
                            await member.send(embed=embed)
                        except errors.Forbidden:
                            pass

                        return

                    embed.add_field(
                        name="`➕` Dodana rola",
                        value=f"{Emojis.REPLY.value} `{role}`",
                    )
                    try:
                        await member.add_roles(
                            role,
                            reason="Smiffy (ReactionRole)",
                        )
                    except errors.Forbidden:
                        embed = Embed(
                            title=f"{Emojis.REDBUTTON.value} Wystąpił bląd.",
                            description=f"{Emojis.REPLY.value} Nie mogłem nadać roli: {role.mention}.\n\n"
                            f"(Rola posiada większe uprawnienia)",
                            colour=Color.red(),
                            timestamp=utils.utcnow(),
                        )
                        embed.set_author(
                            name=member,
                            icon_url=self.avatars.get_user_avatar(member),
                        )
                        embed.set_thumbnail(url=self.avatars.get_guild_icon(channel.guild))

                    try:
                        await member.send(embed=embed)
                    except errors.Forbidden:
                        pass

                    break
                return

        try:
            message_obj: Message = await message.fetch()
        except (errors.Forbidden, errors.HTTPException, errors.NotFound):
            self.bot.logger.warning("Fetching full message object from partial message failed.")
            return

        suggestion_response: Optional[DB_RESPONSE] = await self.bot.db.execute_fetchone(
            "SELECT * FROM suggestions WHERE guild_id = ?",
            (message.guild.id,),
        )

        if suggestion_response and suggestion_response[1] == payload.channel_id:
            if clicked_emoji.id in (
                951968571540529233,
                951968542083932250,
            ):
                for embed in message_obj.embeds:
                    upvotes: int = -1
                    downvotes: int = -1

                    for reaction in message_obj.reactions:
                        if isinstance(reaction.emoji, str):
                            continue

                        if reaction.emoji.id == 951968571540529233:
                            upvotes += reaction.count
                        elif reaction.emoji.id == 951968542083932250:
                            downvotes += reaction.count

                    percent = 100 * float(downvotes) / float(upvotes + downvotes)
                    percent = int(100.0 - percent)
                    embed.set_footer(text=f"Głosowanie: {percent}%")

                    await message.edit(embed=embed)

        status: bool = await check_giveaway_requirement(self.bot, member, message_obj)
        if not status:
            await message_obj.remove_reaction(clicked_emoji, member)

            embed = Embed(
                title=f"{Emojis.REDBUTTON.value} Wystąpił błąd.",
                color=Color.red(),
                timestamp=utils.utcnow(),
                description=f"{Emojis.REPLY.value} Nie spełniasz podanych wymagań aby dołączyć do konkursu.",
            )
            embed.set_author(
                name=member,
                icon_url=self.avatars.get_user_avatar(member),
            )
            embed.set_thumbnail(url=self.avatars.get_guild_icon(channel.guild))

            try:
                await member.send(embed=embed)
            except errors.Forbidden:
                pass

    @CustomCog.listener()
    async def on_raw_reaction_remove(self, payload: RawReactionActionEvent):
        channel: Optional[GuildChannel] = await self.bot.getch_channel(payload.channel_id)

        if not isinstance(channel, TextChannel):
            return

        message: PartialMessage = channel.get_partial_message(payload.message_id)
        member: Optional[Member] = await self.bot.getch_member(channel.guild, payload.user_id)

        if not member or member.bot:
            return

        assert message.guild

        clicked_emoji: PartialEmoji = payload.emoji

        reactionroles_response: Iterable[DB_RESPONSE] = await self.bot.db.execute_fetchall(
            "SELECT * FROM reactionroles WHERE guild_id = ? AND message_id = ?",
            (message.guild.id, message.id),
        )

        if reactionroles_response:
            embed = Embed(
                title=f"Straciłeś/aś role {Emojis.REDBUTTON.value}",
                color=Color.red(),
                timestamp=utils.utcnow(),
            )
            embed.set_author(
                name=member,
                icon_url=self.avatars.get_user_avatar(member),
            )
            embed.set_thumbnail(url=self.avatars.get_guild_icon(channel.guild))

            for data in reactionroles_response:
                if data[4] == str(clicked_emoji):
                    role: Optional[Role] = await self.bot.getch_role(channel.guild, data[3])

                    if not role:
                        embed = Embed(
                            title=f"{Emojis.REDBUTTON.value} Wystąpił bląd.",
                            description=f"{Emojis.REPLY.value} Nie mogłem usunąć roli.\n\n"
                            f"(Rola nie została odnaleźiona)",
                            colour=Color.red(),
                            timestamp=utils.utcnow(),
                        )
                        embed.set_author(
                            name=member,
                            icon_url=self.avatars.get_user_avatar(member),
                        )
                        embed.set_thumbnail(url=self.avatars.get_guild_icon(channel.guild))
                        try:
                            await member.send(embed=embed)
                        except errors.Forbidden:
                            pass

                        return

                    embed.add_field(
                        name="`➖` Usunięta rola",
                        value=f"{Emojis.REPLY.value} `{role}`",
                    )
                    try:
                        await member.remove_roles(
                            role,
                            reason="Smiffy (ReactionRole)",
                        )
                    except errors.Forbidden:
                        embed = Embed(
                            title=f"{Emojis.REDBUTTON.value} Wystąpił bląd.",
                            description=f"{Emojis.REPLY.value} Nie mogłem usunąć roli: {role.mention}.\n\n"
                            f"(Rola posiada większe uprawnienia)",
                            colour=Color.red(),
                            timestamp=utils.utcnow(),
                        )
                        embed.set_author(
                            name=member,
                            icon_url=self.avatars.get_user_avatar(member),
                        )
                        embed.set_thumbnail(url=self.avatars.get_guild_icon(channel.guild))

                    try:
                        await member.send(embed=embed)
                    except errors.Forbidden:
                        pass

                    break

                return

        try:
            message_obj: Message = await message.fetch()
        except (errors.Forbidden, errors.HTTPException, errors.NotFound):
            self.bot.logger.warning("Fetching full message object from partial message failed.")
            return

        suggestion_response: Optional[DB_RESPONSE] = await self.bot.db.execute_fetchone(
            "SELECT * FROM suggestions WHERE guild_id = ?",
            (message.guild.id,),
        )

        if suggestion_response and suggestion_response[1] == payload.channel_id:
            if clicked_emoji.id in (
                951968571540529233,
                951968542083932250,
            ):
                for embed in message_obj.embeds:
                    upvotes: int = -1
                    downvotes: int = -1

                    for reaction in message_obj.reactions:
                        if isinstance(reaction.emoji, str):
                            continue

                        if reaction.emoji.id == 951968571540529233:
                            upvotes += reaction.count
                        elif reaction.emoji.id == 951968542083932250:
                            downvotes += reaction.count

                    try:
                        percent = 100 * float(downvotes) / float(upvotes + downvotes)
                    except ZeroDivisionError:
                        return

                    percent = int(100.0 - percent)
                    embed.set_footer(text=f"Głosowanie: {percent}%")
                    await message.edit(embed=embed)


def setup(bot: Smiffy):
    bot.add_cog(ReactionUpdateEvent(bot))
