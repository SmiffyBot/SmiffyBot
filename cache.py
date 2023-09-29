from __future__ import annotations

from time import time
from typing import TYPE_CHECKING, Optional

from nextcord import Guild, Member, errors

if TYPE_CHECKING:
    from asyncio import AbstractEventLoop

    from nextcord.gateway import DiscordWebSocket
    from nextcord.http import HTTPClient
    from nextcord.state import ConnectionState

    from bot import Smiffy
    from utilities import Logger


__all__ = ("CachedGuild", "BotCache")


class CachedGuild:
    __slots__ = ("guild", "guild_id", "_logger", "__cached_members")

    def __init__(self, guild: Guild, logger: Logger):
        self.guild: Guild = guild
        self.guild_id: int = guild.id

        self._logger: Logger = logger
        self.__cached_members: dict[int, Member] = {member.id: member for member in guild.members}

    async def chunk_members(self, limit: int = 100) -> None:
        """
        The chunk_members function is a coroutine that fetches members of the guild and caches them in a dictionary.
        The function takes an optional limit parameter, which defaults to 100.
        The limit parameter specifies how many members to fetch at once from the API.

        :param limit: Set the limit of members to be fetched at a time
        :return: None
        """
        self._logger.debug(f"Chunking {limit} members. Guild: {self.guild_id}.")

        if limit >= 500:
            self._logger.warning("Chunking more than 500 people at once. This can cause performance losses.")

        async for member in self.guild.fetch_members(limit=limit):
            self.__cached_members[member.id] = member

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

    @property
    def members(self) -> list[Member]:
        return list(self.__cached_members.values())

    def __hash__(self) -> int:
        return hash((self.guild_id, len(self.__cached_members)))

    def __eq__(self, other: object) -> bool:
        return hash(self) == hash(other)

    def __repr__(self) -> str:
        return f"<CachedGuild(guild_id={self.guild_id}, cached_members={len(self.__cached_members)}>)"


class BotCache:
    __slots__: tuple[str, ...] = ("client", "_state", "_http", "_ws", "_logger", "_cached_guilds", "_loop")

    def __init__(self, client: Smiffy) -> None:
        """
        Class that supports Smiffy caching system.

        :param client: Pass the client object into the class
        :return: None
        """

        self._loop: AbstractEventLoop = client.loop
        self._state: ConnectionState = client._connection
        self._http: HTTPClient = self._state.http
        self._ws: DiscordWebSocket = client.ws
        self._logger: Logger = client.logger
        self._cached_guilds: dict[int, CachedGuild] = {}

    @property
    def guilds(self) -> list[CachedGuild]:
        return list(self._cached_guilds.values())

    def chunk_guilds(self) -> None:
        """
        The chunk_guilds function is used to fill the cached_guilds dict of CachedGuild objects.
        The keys are the guild IDs, and the values are the CachedGuild objects themselves.

        :return: None
        """

        start = time()

        for guild in self._state.guilds:
            self._cached_guilds[guild.id] = CachedGuild(guild, self._logger)

        end = time() - start
        self._logger.info(f"Cached {len(self._cached_guilds)} servers in {round(end, 4)}s")

    async def global_chunk_members(self, limit: int = 100) -> None:
        """
        The global_chunk_members function is a coroutine that will chunk all members in the cached guilds.

        :param limit: Set the limit of members to be fetched
        :return: None
        """

        for cached_guilds in self.guilds:
            await cached_guilds.chunk_members(limit=limit)

    def add_guild_to_cache(self, guild: Guild) -> CachedGuild:
        """
        The add_guild_to_cache function is used to add a guild to the cache.

        :param guild: Pass the nextcord guild object
        :return: CachedGuild object.
        """

        cached_guild: CachedGuild = CachedGuild(guild, self._logger)
        self._cached_guilds[guild.id] = cached_guild

        self._logger.debug(f"Added guild: {guild.id} to cache.")

        return cached_guild

    def remove_guild_from_cache(self, guild_id: int) -> None:
        """
        The remove_guild_from_cache function removes a guild from the cache.

        :param guild_id: Specify the guild id that is to be removed from the cache
        :return: None
        """

        try:
            del self._cached_guilds[guild_id]
            self._logger.debug(f"Removed guild: {guild_id} from cache.")
        except KeyError:
            pass

    async def get_cached_guild(self, guild_id: int, fetch: bool = True) -> Optional[CachedGuild]:
        """
        The get_cached_guild function is a helper function that returns the cached guild object for a given guild ID.
        If the guild isn't cached, it will be fetched from Discord and then added to the cache.

        :param guild_id: Get the guild from the client
        :param fetch: Whether method should execute HTTP request if guild was not in cache
        :return: CachedGuild if found.
        """

        cached_guild: Optional[CachedGuild] = self._cached_guilds.get(guild_id)

        if cached_guild or not fetch:
            return cached_guild

        try:
            data = await self._http.get_guild(guild_id)
            guild: Guild = Guild(data=data, state=self._state)
        except (errors.Forbidden, errors.HTTPException):
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

        cached_guild: Optional[CachedGuild] = await self.get_cached_guild(guild_id)
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

    async def remove_member_from_cache(self, guild_id: int, member_id: int) -> None:
        """
        The remove_member_from_cache function removes a member from the cache of a guild.

        :param guild_id: Identify the guild that we want to remove a member from
        :param member_id: Identify the member that is being removed from the cache
        :return: None
        """

        cached_guild: Optional[CachedGuild] = await self.get_cached_guild(guild_id)

        if not cached_guild:
            return None

        cached_guild.remove_member_from_cache(member_id)

    async def add_member_to_cache(self, member: Member, delete_after: Optional[int] = None) -> None:
        """
        The add_member_to_cache function adds a member to the cache.

        :param member: Pass in the member object that we want to add to the cache
        :param delete_after: Value in seconds after which it should remove the member object from the cache
        :return: None
        """

        cached_guild: Optional[CachedGuild] = await self.get_cached_guild(member.guild.id)

        if cached_guild is None:
            cached_guild: CachedGuild = self.add_guild_to_cache(member.guild)

        cached_guild.add_member_to_cache(member)

        if delete_after:
            self._loop.call_later(
                delete_after,
                self._loop.create_task,
                self.remove_member_from_cache(member.guild.id, member.id),
            )
