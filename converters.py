from __future__ import annotations
from typing import TYPE_CHECKING, Any, Optional, Union, TypeVar, Iterable, Type, Generic

import re
from abc import ABC

from nextcord import OptionConverter, utils, Role, Message, Member, HTTPException
from nextcord.abc import GuildChannel

from enums import GuildChannelTypes

if TYPE_CHECKING:
    from bot import Smiffy
    from utilities import CustomInteraction

    from nextcord import Guild, TextChannel, Thread, DMChannel, PartialMessageable
    from nextcord.gateway import DiscordWebSocket

    PartialMessageableChannel = Union[TextChannel, Thread, DMChannel, PartialMessageable]

CT = TypeVar("CT", bound=GuildChannel)

__all__: tuple[str, ...] = (
    "MessageConverter",
    "RoleConverter",
    "MemberConverter",
    "GuildChannelConverter",
)


class BaseConverter(OptionConverter, ABC):
    @staticmethod
    def _get_id_match(argument: str) -> Optional[re.Match]:
        _ID_REGEX: re.Pattern = re.compile(r"([0-9]{15,20})$")

        return _ID_REGEX.match(argument)

    @staticmethod
    def _get_channel_id_matches(
        interaction: CustomInteraction, argument: str
    ) -> Optional[tuple[Optional[int], ...]]:
        assert interaction.guild

        id_regex: re.Pattern = re.compile(r"(?:(?P<channel_id>[0-9]{15,20})-)?(?P<message_id>[0-9]{15,20})$")

        link_regex: re.Pattern = re.compile(
            r"https?://(?:(ptb|canary|www)\.)?discord(?:app)?\.com/channels/"
            r"(?P<guild_id>[0-9]{15,20}|@me)"
            r"/(?P<channel_id>[0-9]{15,20})/(?P<message_id>[0-9]{15,20})/?$"
        )

        match: Optional[re.Match] = id_regex.match(argument) or link_regex.match(argument)

        if not match:
            return None

        data: dict = match.groupdict()

        channel_id: Optional[int] = utils.get_as_snowflake(data, "channel_id")
        message_id: int = int(data["message_id"])
        guild_id: Optional[int] = data.get("guild_id")

        if guild_id is None:
            guild_id = interaction.guild.id

        elif guild_id == "@me":
            guild_id = None
        else:
            guild_id = int(guild_id)

        if channel_id is None and interaction.channel:
            channel_id = interaction.channel.id

        return guild_id, message_id, channel_id

    @staticmethod
    async def _resolve_channel(
        inter: CustomInteraction, guild_id: Optional[int], channel_id: Optional[int]
    ) -> Optional[PartialMessageableChannel]:
        if guild_id is not None:
            guild: Optional[Guild] = await inter.bot.getch_guild(guild_id)

            if guild is not None and channel_id is not None:
                return guild._resolve_channel(channel_id)  # pyright: ignore

            return None

        return await inter.bot.getch_channel(channel_id) if channel_id else inter.channel  # pyright: ignore

    def __repr__(self) -> str:
        return f"<BaseConverter(type={self.type}, size={self.__sizeof__()})>"


class RoleConverter(BaseConverter):
    def __init__(self):
        super().__init__(Role)

    async def convert(self, interaction: CustomInteraction, value: Any) -> Optional[Role]:
        guild: Optional[Guild] = interaction.guild

        if not guild:
            return None

        match: Optional[re.Match] = self._get_id_match(value) or re.match(r"<@&([0-9]{15,20})>$", value)

        if match:
            result: Optional[Role] = await interaction.bot.getch_role(guild, int(match.group(1)))
        else:
            result: Optional[Role] = utils.get(guild.roles, name=value)

        return result

    def __repr__(self) -> str:
        return f"<RoleConverter(type={self.type})>"


class MessageConverter(BaseConverter):
    def __init__(self):
        super().__init__(Message)

    async def convert(self, interaction: CustomInteraction, value: Any) -> Optional[Message]:
        data: Optional[tuple[Optional[int], ...]] = self._get_channel_id_matches(interaction, value)

        if not data:
            return None

        bot: Smiffy = interaction.bot
        guild_id, message_id, channel_id = data
        message: Optional[Message] = bot._connection._get_message(message_id)

        if message:
            return message

        channel: Optional[PartialMessageableChannel] = await self._resolve_channel(
            inter=interaction, guild_id=guild_id, channel_id=channel_id
        )

        if not channel or not message_id:
            return None

        try:
            return await channel.fetch_message(message_id)
        except Exception as exception:  # pylint: disable=broad-exception-caught
            bot.logger.debug(f"An error was received while fetching the message: {exception} | {self}")

        return None

    def __repr__(self) -> str:
        return f"<MessageConverter(type={self.type})>"


class MemberConverter(BaseConverter):
    def __init__(self):
        super().__init__(Member)

    def __repr__(self) -> str:
        return f"<MemberConverter(type={self.type})>"

    @staticmethod
    async def query_member_named(guild: Guild, argument: str) -> Optional[Member]:
        if len(argument) > 5 and argument[-5] == "#":
            username, _, discriminator = argument.rpartition("#")
            members: list[Member] = await guild.query_members(username, limit=10)

            return utils.get(members, name=username, discriminator=discriminator)

        members: list[Member] = await guild.query_members(argument, limit=10)

        def finder(m: Member) -> bool:
            return argument in (m.name, m.nick)

        return utils.find(finder, members)

    @staticmethod
    async def query_member_by_id(bot: Smiffy, guild: Guild, user_id: int) -> Optional[Member]:
        ws: DiscordWebSocket = bot._get_websocket(shard_id=guild.shard_id)

        if ws.is_ratelimited():
            # If we're being rate limited on the WS, then fall back to using the HTTP API
            # So we don't have to wait ~60 seconds for the query to finish

            try:
                member = await guild.fetch_member(user_id)
            except HTTPException:
                return None

            guild._add_member(member)
            return member

        # If we're not being rate limited then we can use the websocket to actually query
        members: list[Member] = await guild.query_members(limit=1, user_ids=[user_id])

        if not members:
            return None

        return members[0]

    async def convert(self, interaction: CustomInteraction, value: Any) -> Optional[Member]:
        bot: Smiffy = interaction.bot
        guild: Optional[Guild] = interaction.guild

        if not guild:
            return None

        result: Optional[Member] = None
        user_id: Optional[int] = None
        match: Optional[re.Match] = self._get_id_match(value) or re.match(r"<@!?([0-9]{15,20})>$", value)

        if match is None:
            # not a mention...
            result = guild.get_member_named(value)

        else:
            if interaction.message:
                result = utils.get(interaction.message.mentions, id=user_id)  # pyright: ignore

            if not result:
                user_id = int(match.group(1))
                result = await bot.getch_member(guild, user_id)

        if result is None:
            if user_id is not None:
                result = await self.query_member_by_id(bot, guild, user_id)
            else:
                result = await self.query_member_named(guild, value)

        return result


class GuildChannelConverter(Generic[CT]):
    def __getitem__(self, channel_type: GuildChannelTypes) -> GuildChannelConverter:
        if not isinstance(channel_type, GuildChannelTypes):
            raise TypeError("Invalid Channel Type")

        self.channel_type = channel_type
        return self

    def __init__(self):
        self._ID_REGEX = re.compile(r"([0-9]{15,20})$")

        self.channel_type: Optional[GuildChannelTypes] = None

    def convert(self, interaction: CustomInteraction, argument: str) -> Optional[CT]:
        if not self.channel_type:
            raise ValueError("Missing channel type.")

        return self._resolve_channel(
            interaction, argument, self.channel_type.name, self.channel_type.value  # pyright: ignore
        )

    def _get_id_match(self, argument: str) -> Optional[re.Match]:
        return self._ID_REGEX.match(argument)

    def _resolve_channel(
        self,
        inter: CustomInteraction,
        argument: str,
        attribute: str,
        channel_type: Type[CT],
    ) -> Optional[CT]:
        bot: Smiffy = inter.bot

        match: Optional[re.Match] = self._get_id_match(argument) or re.match(r"<#([0-9]{15,20})>$", argument)
        result: Optional[CT] = None

        guild: Optional[Guild] = inter.guild

        if match is None:
            # not a mention
            if guild:
                iterable: Iterable[CT] = getattr(guild, attribute)
                result: Optional[CT] = utils.get(iterable, name=argument)

            else:

                def check(channel: GuildChannel) -> bool:
                    return isinstance(channel, channel_type) and channel.name == argument

                result = utils.find(check, bot.get_all_channels())  # pyright: ignore
        else:
            channel_id: int = int(match.group(1))

            if guild:
                result = guild.get_channel(channel_id)  # type: ignore
            else:
                result = self._get_from_guilds(bot, "get_channel", channel_id)

        if not isinstance(result, channel_type):
            return None

        return result

    @staticmethod
    def _get_from_guilds(bot: Smiffy, getter: str, argument: Any) -> Any:
        result: Any = None

        for guild in bot.guilds:
            result = getattr(guild, getter)(argument)

            if result:
                return result

        return result
