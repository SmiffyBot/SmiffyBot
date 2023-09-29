from __future__ import annotations
from typing import TYPE_CHECKING, Optional
from nextcord import Member, errors

if TYPE_CHECKING:
    from utilities import BotBase

    from nextcord import Guild
    from nextcord.gateway import DiscordWebSocket
    from nextcord.state import ConnectionState
    from nextcord.http import HTTPClient


class ChunkedGuild:

    __slots__ = ("guild", "guild_id", "__cached_members")

    def __init__(self, guild: Guild):
        self.guild: Guild = guild
        self.guild_id: int = guild.id

        self.__cached_members: dict[int, Member] = {member.id: member for member in guild.members}

    def add_member(self, member: Member):
        self.__cached_members[member.id] = member

    def remove_member(self, member: Member):
        try:
            del self.__cached_members[member.id]
        except KeyError:
            pass

    def get_member(self, member_id: int) -> Optional[ChunkedGuild]:
        return self.__cached_members.get(member_id)

    def __hash__(self) -> int:
        return hash((self.guild_id, len(self.__cached_members)))

    def __eq__(self, other: object) -> bool:
        return hash(self) == hash(other)

    def __repr__(self) -> str:
        return f"<CachedGuild(guild_id={self.guild_id}, cached_members={len(self.__cached_members)})"


class BotCache:
    __slots__: tuple[str, ...] = (
        "client", "_state", "_http", "_ws", "cached_guilds"
    )

    def __init__(self, client: BotBase, chunk_guilds: bool = True):
        self.client: BotBase = client

        self._state: ConnectionState = client._connection
        self._http: HTTPClient = self._state.http
        self._ws: DiscordWebSocket = self.client.ws

        self.cached_guilds: dict[int, ChunkedGuild] = {}
        if chunk_guilds:
            self.chunk_guilds()

    def chunk_guilds(self):
        for guild in self._state.guilds:
            self.cached_guilds[guild.id] = ChunkedGuild(guild)

    def get_chunked_guild(self, guild_id) -> Optional[ChunkedGuild]:
        cached_guild: Optional[ChunkedGuild] = self.cached_guilds.get(guild_id)

        if cached_guild:
            return cached_guild

        guild: Optional[Guild] = self.client.get_guild(guild_id)

        if not guild:
            return None

        cached_guild: ChunkedGuild = ChunkedGuild(guild)
        self.cached_guilds[guild.id] = cached_guild

        return cached_guild

    async def getch_member(self, guild_id: int, member_id: int) -> Optional[Member]:
        cached_guild: Optional[ChunkedGuild] = self.get_chunked_guild(guild_id)
        if not cached_guild:
            return None

        nc_guild: Guild = cached_guild.guild

        member: Optional[Member] = cached_guild.get_member(member_id)

        if member:
            return member

        if self._ws.is_ratelimited():

            try:
                member_data = await self._http.get_member(guild_id, member_id)
                member: Member = Member(data=member_data, guild=nc_guild, state=self._state)
                cached_guild.add_member(member)

                return member
            except (errors.Forbidden, errors.HTTPException):
                return None

        members: list[Member] = await self._state.query_members(
            nc_guild, query=None, limit=1, user_ids=[member_id], presences=False, cache=True
        )
        if not members:
            return None

        member: Member = member[0]
        cached_guild.add_member(member)
        return member
