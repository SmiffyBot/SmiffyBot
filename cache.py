from __future__ import annotations
from typing import TYPE_CHECKING, Optional

from nextcord import Member, errors
from time import time

if TYPE_CHECKING:
    from bot import Smiffy
    from utilities import Logger

    from nextcord import Guild
    from nextcord.gateway import DiscordWebSocket
    from nextcord.state import ConnectionState
    from nextcord.http import HTTPClient


__all__ = (
    "CachedGuild",
    "BotCache"
)


class CachedGuild:

    __slots__ = ("guild", "guild_id", "_logger", "__cached_members")

    def __init__(self, guild: Guild, logger: Logger):
        self.guild: Guild = guild
        self.guild_id: int = guild.id

        self._logger: Logger = logger
        self.__cached_members: dict[int, Member] = {member.id: member for member in guild.members}

    def add_member_to_cache(self, member: Member) -> None:
        """
        The add_member_to_cache function adds a member to the cache.

        :param member: Pass in the member object
        :return: None
        """

        self._logger.debug(f"Added member: {member.id} to cache.")

        self.__cached_members[member.id] = member

    def remove_member_from_cache(self, member_id: int) -> None:
        """
        The remove_member_from_cache function removes a member from the cache.

        :param member_id: Specify the member id of the member to be removed from cache
        :return: None
        """

        try:
            del self.__cached_members[member_id]
            self._logger.debug(f"Removed member: {member_id} from cache.")
        except KeyError:
            pass

    def get_member_from_cache(self, member_id: int) -> Optional[Member]:
        """
        The get_member_from_cache function is a helper function that returns the cached member object
        for the given member_id. If no such object exists, it will return None.

        :param member_id: Specify the member id of the user
        :return: Member object if found.
        """

        self._logger.debug(f"Getting: {member_id} from cache.")
        return self.__cached_members.get(member_id)

    def __hash__(self) -> int:
        return hash((self.guild_id, len(self.__cached_members)))

    def __eq__(self, other: object) -> bool:
        return hash(self) == hash(other)

    def __repr__(self) -> str:
        return f"<CachedGuild(guild_id={self.guild_id}, cached_members={len(self.__cached_members)}>)"


class BotCache:
    __slots__: tuple[str, ...] = (
        "client", "_state", "_http", "_ws", "_logger", "cached_guilds"
    )

    def __init__(self, client: Smiffy) -> None:
        """
        Class that supports Smiffy caching system.

        :param client: Pass the client object into the class
        :return: None
        """

        self.client: Smiffy = client

        self._state: ConnectionState = client._connection
        self._http: HTTPClient = self._state.http
        self._ws: DiscordWebSocket = client.ws
        self._logger: Logger = client.logger

        self.cached_guilds: dict[int, CachedGuild] = {}

    def chunk_guilds(self) -> None:
        """
        The chunk_guilds function is used to fill the cached_guilds dict of CachedGuild objects.
        The keys are the guild IDs, and the values are the CachedGuild objects themselves.

        :return: None
        """

        start = time()

        for guild in self._state.guilds:
            self.cached_guilds[guild.id] = CachedGuild(guild, self._logger)

        end = time() - start
        self._logger.info(f"Cached {len(self.cached_guilds)} servers in {round(end, 4)}s")

    def add_guild_to_cache(self, guild: Guild) -> CachedGuild:
        """
        The add_guild_to_cache function is used to add a guild to the cache.

        :param guild: Pass the nextcord guild object
        :return: CachedGuild object.
        """

        cached_guild: CachedGuild = CachedGuild(guild, self._logger)
        self.cached_guilds[guild.id] = cached_guild

        self._logger.debug(f"Added guild: {guild.id} to cache.")

        return cached_guild

    def remove_guild_from_cache(self, guild_id: int) -> None:
        """
        The remove_guild_from_cache function removes a guild from the cache.

        :param guild_id: Specify the guild id that is to be removed from the cache
        :return: None
        """

        try:
            del self.cached_guilds[guild_id]
            self._logger.debug(f"Removed guild: {guild_id} from cache.")
        except KeyError:
            pass

    def get_cached_guild(self, guild_id: int) -> Optional[CachedGuild]:
        """
        The get_cached_guild function is a helper function that returns the cached guild object for a given guild ID.
        If the guild isn't cached, it will be fetched from Discord and then added to the cache.

        :param guild_id: Get the guild from the client
        :return: CachedGuild if found.
        """

        cached_guild: Optional[CachedGuild] = self.cached_guilds.get(guild_id)

        if cached_guild:
            return cached_guild

        guild: Optional[Guild] = self.client.get_guild(guild_id)

        if not guild:
            return None

        cached_guild = self.add_guild_to_cache(guild)
        return cached_guild

    async def get_member(self, guild_id: int, member_id: int) -> Optional[Member]:
        """
        The get_member function is used to get a member object from the cache.
        If it's not in the cache, then we will try to fetch it from Discord.
        If that fails, then we return None.

        :param guild_id: Get the guild from the cache
        :param member_id: Get the member id of a specific user
        :return: A member object that contains all the information about a specific user in a guild
        """

        cached_guild: Optional[CachedGuild] = self.get_cached_guild(guild_id)
        if not cached_guild:
            return None

        nc_guild: Guild = cached_guild.guild

        member: Optional[Member] = cached_guild.get_member_from_cache(member_id)

        if member:
            return member

        if self._ws.is_ratelimited():

            try:
                member_data = await self._http.get_member(guild_id, member_id)
                member: Member = Member(data=member_data, guild=nc_guild, state=self._state)
            except (errors.Forbidden, errors.HTTPException):
                return None

        else:
            members: list[Member] = await self._state.query_members(
                nc_guild, query=None, limit=1, user_ids=[member_id], presences=False, cache=True
            )

            if not members:
                return None

            member: Member = member[0]

        cached_guild.add_member_to_cache(member)
        return member

    def remove_member_from_cache(self, guild_id: int, member_id: int) -> None:
        """
        The remove_member_from_cache function removes a member from the cache of a guild.

        :param guild_id: Identify the guild that we want to remove a member from
        :param member_id: Identify the member that is being removed from the cache
        :return: None
        """

        cached_guild: Optional[CachedGuild] = self.get_cached_guild(guild_id)

        if not cached_guild:
            return None

        cached_guild.remove_member_from_cache(member_id)

    def add_member_to_cache(self, member: Member) -> None:
        """
        The add_member_to_cache function adds a member to the cache.

        :param member: Pass in the member object that we want to add to the cache
        :return: None
        """

        cached_guild: Optional[CachedGuild] = self.get_cached_guild(member.guild.id)

        if not cached_guild:
            cached_guild: CachedGuild = self.add_guild_to_cache(member.guild)

        cached_guild.add_member_to_cache(member)
