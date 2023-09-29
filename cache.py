from __future__ import annotations

from time import time
from typing import TYPE_CHECKING, Optional, cast

from nextcord import ChannelType, Guild, Member, Role, errors
from nextcord.channel import _threaded_guild_channel_factory

from typings import CacheRequest

if TYPE_CHECKING:
    from asyncio import AbstractEventLoop

    from nextcord.abc import GuildChannel
    from nextcord.gateway import DiscordWebSocket
    from nextcord.http import HTTPClient
    from nextcord.state import ConnectionState

    from bot import Smiffy
    from utilities import Logger


__all__ = ("CachedGuild", "BotCache")


class RequestLimiter:
    __slots__: tuple[str] = ("dispatched_requests", "client", "limit", "reset_after")

    def __init__(self, client: Smiffy, limit: int = 2, reset_after: int = 60):
        self.client: Smiffy = client
        self.limit = limit
        self.reset_after = reset_after
        self.dispatched_requests: dict[int, list[CacheRequest]] = {}

    def __repr__(self) -> str:
        return f"<RequestLimiter(limit={self.limit}, dispatched={len(self.dispatched_requests)})>"

    def get_exact_request_amount(self, request: CacheRequest) -> int:
        """
        The get_exact_request_amount function is used to get the exact amount of requests.
        The function then returns the number of times that request has been made.

        :param request: Request to compare
        :return: The number of requests that have been made exactly like the request passed as an argument
        """

        exact_requests: int = 0
        data: list[CacheRequest] = self.dispatched_requests.get(request["guild_id"], [])

        for r in data:
            if r == request:
                exact_requests += 1

        return exact_requests

    def get_status_from_request(self, request: CacheRequest) -> bool:
        """
        The get_status_from_request function checks if the next request via api can be executed.

        :param request: Get the request amount
        :return: A boolean
        """

        if self.get_exact_request_amount(request) >= self.limit:
            return False

        return True

    def add_new_request(self, request: CacheRequest) -> None:
        """
        The add_new_request function is used to add a new request to the limiter.
        It also creates a task which removes this request after reset_after seconds.

        :param request: Add a request to the dispatched_requests dictionary
        :return: None
        """

        data: list[CacheRequest] = self.dispatched_requests.get(request["guild_id"], [])

        data.append(request)
        self.dispatched_requests[request["guild_id"]] = data

        self.client.logger.debug(f"Added request: {request} to limiter.")

        self.client.loop.call_later(
            self.reset_after, self.client.loop.create_task, self.remove_request(request)
        )

    def remove_request(self, request: CacheRequest) -> None:
        """
        The remove_request function is used to remove a request from the limiter.

        :param request: Remove a request from the dispatched_requests dictionary
        :return: None
        """

        guild_request: list[CacheRequest] = self.dispatched_requests.get(request["guild_id"], [])

        for r in guild_request.copy():
            if request == r:
                guild_request.remove(request)
                self.client.logger.debug(f"Removed request: {request} from limiter.")

                break

        self.dispatched_requests[request["guild_id"]] = guild_request


class CachedGuild:
    __slots__ = ("guild", "guild_id", "_logger", "__cached_members", "__cached_roles", "__cached_channels")

    def __init__(self, guild: Guild, logger: Logger):
        self.guild: Guild = guild
        self.guild_id: int = guild.id

        self._logger: Logger = logger

        self.__cached_members: dict[int, Member] = {member.id: member for member in guild.members}
        self.__cached_roles: dict[int, Role] = {role.id: role for role in guild.roles}
        self.__cached_channels: dict[int, GuildChannel] = {channel.id: channel for channel in guild.channels}

    async def chunk_members(self, limit: int = 100) -> None:
        """
        The chunk_members function is a coroutine that fetches members of the guild and catch them into cache.
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

        self._logger.debug(f"Getting member: {member_id} from cache.")
        return self.__cached_members.get(member_id)

    def add_role_to_cache(self, role: Role) -> None:
        """
        The add_role_to_cache function adds a role to the cache.

        :param role: Pass in the role object to be added to the cache
        :return: None
        """

        self._logger.debug(f"Added role: {role.id} to cache.")
        self.__cached_roles[role.id] = role

    def remove_role_from_cache(self, role_id: int) -> None:
        """
        The remove_role_from_cache function removes a role from the cache.

        :param role_id: Specify the role id of the role to be removed from cache
        :return: None
        """

        try:
            del self.__cached_roles[role_id]
            self._logger.debug(f"Removed role: {role_id} from cache.")
        except KeyError:
            pass

    def get_role_from_cache(self, role_id: int) -> Optional[Role]:
        """
        The get_role_from_cache function is a coroutine that returns the role object from the cache.
        If it does not exist in the cache, then it will return None.

        :param role_id: Get the role from the cache
        :return: The role from the cache if exists
        """

        self._logger.debug(f"Getting role: {role_id} from cache.")
        return self.__cached_roles.get(role_id)

    def add_channel_to_cache(self, channel: GuildChannel) -> None:
        """
        The add_channel_to_cache function adds a channel to the cache.

        :param channel: GuildChannel: Pass in the channel that is being added to the cache
        :return: None
        """

        self._logger.debug(f"Added channel: {channel.id} to cache.")

        self.__cached_channels[channel.id] = channel

    def remove_channel_from_cache(self, channel_id: int) -> None:
        """
        The remove_channel_from_cache function removes a channel from the cache.

        :param channel_id: Identify the channel to be removed from the cache
        :return: None
        """

        try:
            del self.__cached_channels[channel_id]
            self._logger.debug(f"Removed channel: {channel_id} from cache.")
        except KeyError:
            pass

    def get_channel_from_cache(self, channel_id: int) -> Optional[GuildChannel]:
        """
        The get_channel_from_cache function is a helper function that returns the channel object from the cache.

        :param channel_id: Get the channel id
        :return: The channel from the cache if it exists
        """

        self._logger.debug(f"Getting channel: {channel_id} from cache.")
        return self.__cached_channels.get(channel_id)

    @property
    def chunked(self):
        return self.guild.member_count == len(self.members)

    @property
    def members(self) -> list[Member]:
        return list(self.__cached_members.values())

    @property
    def roles(self) -> list[Role]:
        return list(self.__cached_roles.values())

    @property
    def channels(self) -> list[GuildChannel]:
        return list(self.__cached_channels.values())

    def __hash__(self) -> int:
        return hash((self.guild_id, len(self.members), len(self.roles), len(self.channels)))

    def __eq__(self, other: object) -> bool:
        return hash(self) == hash(other)

    def __repr__(self) -> str:
        return f"<CachedGuild(guild_id={self.guild_id}, chunked={self.chunked})>"


class BotCache:
    __slots__: tuple[str, ...] = (
        "client",
        "_state",
        "_http",
        "_ws",
        "_logger",
        "_cached_guilds",
        "_loop",
        "_dispatched_requests",
        "_request_limiter",
    )

    def __init__(self, client: Smiffy) -> None:
        """
        Class that supports Smiffy caching system.

        :param client: Pass the client object into the class
        :return: None
        """
        self._request_limiter: RequestLimiter = RequestLimiter(client)

        self._loop: AbstractEventLoop = client.loop
        self._state: ConnectionState = client._connection
        self._http: HTTPClient = self._state.http
        self._ws: DiscordWebSocket = client.ws
        self._logger: Logger = client.logger
        self._cached_guilds: dict[int, CachedGuild] = {}

    @property
    def guilds(self) -> list[CachedGuild]:
        return list(self._cached_guilds.values())

    async def chunk_guilds(self, run_in_tasks: bool, small_server_chunk_members: bool = True) -> None:
        """
        The chunk_guilds function is used to fill the cached_guilds dict of CachedGuild objects.
        The keys are the guild IDs, and the values are the CachedGuild objects themselves.

        :param small_server_chunk_members: Is bot supposed to chunk people on servers under 100 people.
        :param run_in_tasks: Whether chunking members is to be done in tasks.
        :return: None
        """

        start = time()

        for guild in self._state.guilds:
            cachedGuild = CachedGuild(guild, self._logger)
            self._cached_guilds[guild.id] = cachedGuild

            if guild.member_count and guild.member_count <= 100 and small_server_chunk_members:
                if run_in_tasks:
                    self._loop.create_task(cachedGuild.chunk_members())
                else:
                    await cachedGuild.chunk_members()

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

    def add_guild(self, guild: Guild) -> CachedGuild:
        """
        The add_guild function is used to add a guild to the cache.

        :param guild: Pass the nextcord guild object
        :return: CachedGuild object.
        """

        cached_guild: CachedGuild = CachedGuild(guild, self._logger)
        self._cached_guilds[guild.id] = cached_guild

        self._logger.debug(f"Added guild: {guild.id} to cache.")

        return cached_guild

    def remove_guild(self, guild_id: int) -> None:
        """
        The remove_guild function removes a guild from the cache.

        :param guild_id: Specify the guild id that is to be removed from the cache
        :return: None
        """

        try:
            del self._cached_guilds[guild_id]
            self._logger.debug(f"Removed guild: {guild_id} from cache.")
        except KeyError:
            pass

    async def get_guild(self, guild_id: int, fetch: bool = True) -> Optional[CachedGuild]:
        """
        The get_guild function is a helper function that returns the cached guild object for a given guild ID.
        If the guild isn't cached, it will be fetched from Discord and then added to the cache.

        :param guild_id: Get the guild from the client
        :param fetch: Whether method should execute HTTP request if guild was not in cache
        :return: CachedGuild if found.
        """

        cached_guild: Optional[CachedGuild] = self._cached_guilds.get(guild_id)
        self._logger.debug(f"Getting guild: {guild_id} from cache.")

        if cached_guild or not fetch:
            return cached_guild

        request = CacheRequest(guild_id=guild_id, request_type="guild", args=(guild_id,))
        if not self._request_limiter.get_status_from_request(request):
            self._logger.debug(
                f"Ignoring sending request to discord API for guild: {guild_id}. "
                f"Limit requests: {self._request_limiter.limit} reached."
            )
            return

        self._request_limiter.add_new_request(request)

        try:
            self._logger.warning(f"Guild: {guild_id} was not found in the cache. Sending HTTP Request.")

            data = await self._http.get_guild(guild_id)
            guild: Guild = Guild(data=data, state=self._state)
        except (errors.Forbidden, errors.HTTPException):
            self._logger.debug(f"Fetching guild: {guild_id} using HTTP failed.")
            return None

        cached_guild = self.add_guild(guild)
        return cached_guild

    async def add_member(self, member: Member, delete_after: Optional[int] = None) -> None:
        """
        The add_member function adds a member to the cache.

        :param member: Pass in the member object that we want to add to the cache
        :param delete_after: Value in seconds after which it should remove the member object from the cache
        :return: None
        """

        cached_guild: Optional[CachedGuild] = await self.get_guild(member.guild.id)

        if cached_guild is None:
            cached_guild = self.add_guild(member.guild)

        cast(CachedGuild, cached_guild)
        cached_guild.add_member_to_cache(member)

        if delete_after:
            self._loop.call_later(
                delete_after,
                self._loop.create_task,
                self.remove_member(member.guild.id, member.id),
            )

    async def remove_member(self, guild_id: int, member_id: int) -> None:
        """
        The remove_member function removes a member from the cache of a guild.

        :param guild_id: Identify the guild that we want to remove a member from
        :param member_id: Identify the member that is being removed from the cache
        :return: None
        """

        cached_guild: Optional[CachedGuild] = await self.get_guild(guild_id)

        if not cached_guild:
            return None

        cached_guild.remove_member_from_cache(member_id)

    async def get_member(self, guild_id: int, member_id: int) -> Optional[Member]:
        """
        The get_member function is used to get a member object from the cache.
        If it's not in the cache, then we will try to fetch it from Discord.
        If that fails, then we return None.

        :param guild_id: Get the guild from the cache
        :param member_id: Get the member id of a specific user
        :return: A member object that contains all the information about a specific user in a guild
        """

        cached_guild: Optional[CachedGuild] = await self.get_guild(guild_id)
        self._logger.debug(f"Getting member: {member_id} from cache.")

        if not cached_guild:
            return None

        member: Optional[Member] = cached_guild.get_member_from_cache(member_id)

        if member:
            return member

        request = CacheRequest(guild_id=guild_id, request_type="member", args=(guild_id, member_id))

        if not self._request_limiter.get_status_from_request(request):
            self._logger.debug(
                f"Ignoring sending request to discord API for member: {member_id}. "
                f"Limit requests: {self._request_limiter.limit} reached."
            )
            return

        self._request_limiter.add_new_request(request)

        self._logger.warning(f"Member: {member_id} was not found in the cache. Sending HTTP Request.")

        if self._ws and self._ws.is_ratelimited():
            try:
                member_data = await self._http.get_member(guild_id, member_id)
                member = Member(data=member_data, guild=cached_guild.guild, state=self._state)
            except (errors.Forbidden, errors.HTTPException):
                self._logger.debug(f"Fetching member: {member_id} using HTTP failed.")
                return None

        else:
            members: list[Member] = await self._state.query_members(
                cached_guild.guild, query=None, limit=1, user_ids=[member_id], presences=False, cache=True
            )

            if not members:
                return None

            member = members[0]

        if member:
            cached_guild.add_member_to_cache(member)

        return member

    async def add_role(self, guild_id: int, role: Role, delete_after: Optional[int] = None) -> None:
        """
        The add_role function adds a role to the cache.

        :param guild_id: Identify the guild that the role is being added to
        :param role: Add a role to the cache
        :param delete_after: the amount of time the role should be in the cache
        :return: None
        """

        cached_guild: Optional[CachedGuild] = await self.get_guild(guild_id)
        if not cached_guild:
            return None

        cached_guild.add_role_to_cache(role)

        if delete_after:
            self._loop.call_later(delete_after, self._loop.create_task, self.remove_role(guild_id, role.id))

    async def remove_role(self, guild_id: int, role_id: int) -> None:
        """
        The remove_role function removes a role from the cache.

        :param guild_id: Identify the guild
        :param role_id: Identify the role that is being removed from the cache
        :return: None
        """

        cached_guild: Optional[CachedGuild] = await self.get_guild(guild_id)

        if not cached_guild:
            return None

        cached_guild.remove_role_from_cache(role_id)

    async def get_role(self, guild_id: int, role_id: int, fetch: bool = False) -> Optional[Role]:
        """
        The get_role function is used to get a role from the cache. if fetch is True
        it will fetch all roles from Discord and add them to the cache if if they are not there.
        It then returns either None or a Role object.

        :param guild_id:Get the guild from the cache
        :param role_id: Get the role id
        :param fetch: Determine if the role should be fetched from discord or not if not found in the cache
        :return: The role object of the given guild if exists
        """

        cached_guild: Optional[CachedGuild] = await self.get_guild(guild_id)
        self._logger.debug(f"Getting role: {role_id} from cache.")

        if not cached_guild:
            return None

        role: Optional[Role] = cached_guild.get_role_from_cache(role_id)

        if role or not fetch:
            return role

        request = CacheRequest(guild_id=guild_id, request_type="role", args=(guild_id, role_id))

        if not self._request_limiter.get_status_from_request(request):
            self._logger.debug(
                f"Ignoring sending request to discord API for role: {role_id}. "
                f"Limit requests: {self._request_limiter.limit} reached."
            )
            return

        self._request_limiter.add_new_request(request)

        self._logger.warning(f"Role: {role_id} was not found in the cache. Sending HTTP Request.")

        data = await self._state.http.get_roles(guild_id)
        requested_roles: list[Role] = [
            Role(guild=cached_guild.guild, state=self._state, data=role_data) for role_data in data
        ]

        for requested_role in requested_roles:
            if not cached_guild.get_role_from_cache(requested_role.id):
                cached_guild.add_role_to_cache(requested_role)

        return cached_guild.get_role_from_cache(role_id)

    async def add_channel(
        self, guild_id: int, channel: GuildChannel, delete_after: Optional[int] = None
    ) -> None:
        """
        The add_channel function adds a channel to the cache.

        :param guild_id: Identify the guild
        :param channel: Add the channel to the cache
        :param delete_after: Value in seconds after which it should remove the channel object from the cache
        :return: None
        """

        cached_guild: Optional[CachedGuild] = await self.get_guild(guild_id)

        if not cached_guild:
            return None

        cached_guild.add_channel_to_cache(channel)

        if delete_after:
            self._loop.call_later(
                delete_after, self._loop.create_task, self.remove_channel(guild_id, channel.id)
            )

    async def remove_channel(self, guild_id: int, channel_id: int) -> None:
        """
        The remove_channel function removes a channel from the cache.

        :param guild_id: Identify the guild
        :param channel_id: Remove a channel from the cache
        :return: None
        """

        cached_guild: Optional[CachedGuild] = await self.get_guild(guild_id)

        if not cached_guild:
            return None

        cached_guild.remove_channel_from_cache(channel_id)

    async def get_channel(self, guild_id: int, channel_id: int, fetch: bool = True) -> Optional[GuildChannel]:
        """
        The get_channel function is used to get a channel from the cache.
        If it's not in the cache, then it will be retrieved from Discord and added to the cache.

        :param guild_id: Specify the guild id of the channel we want to get
        :param channel_id: Get the channel id
        :param fetch: Whether method should execute HTTP request if channel or guild was not in cache
        :return: The channel object or None
        """

        cached_guild: Optional[CachedGuild] = await self.get_guild(guild_id, fetch)
        self._logger.debug(f"Getting channel: {channel_id} from cache.")

        if not cached_guild:
            return None

        channel: Optional[GuildChannel] = cached_guild.get_channel_from_cache(channel_id)
        if channel or not fetch:
            return channel

        request = CacheRequest(guild_id=guild_id, request_type="channel", args=(guild_id, channel_id))

        if not self._request_limiter.get_status_from_request(request):
            self._logger.debug(
                f"Ignoring sending request to discord API for channel: {channel_id}. "
                f"Limit requests: {self._request_limiter.limit} reached."
            )
            return

        self._request_limiter.add_new_request(request)

        self._logger.warning(f"Channel: {channel_id} was not found in the cache. Sending HTTP Request.")

        try:
            data = await self._state.http.get_channel(channel_id)

            factory, channel_type = _threaded_guild_channel_factory(data["type"])
            if factory is None:
                raise errors.InvalidData("Unknown channel type {type} for channel ID {id}.".format_map(data))

            if channel_type in (ChannelType.group, ChannelType.private):
                raise errors.InvalidData("Channel ID resolved to a private channel")

            data_guild_id: int = int(data["guild_id"])  # pyright: ignore

            if guild_id != data_guild_id:
                raise errors.InvalidData("Guild ID resolved to a different guild")

            channel = factory(guild=cached_guild.guild, state=self._state, data=data)  # pyright: ignore

        except (errors.Forbidden, errors.HTTPException, errors.InvalidData):
            self._logger.debug(f"Fetching channel: {channel_id} using HTTP failed.")
            return None

        if channel:
            await self.add_channel(guild_id, channel)
        return channel
