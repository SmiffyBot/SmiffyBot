from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from utilities import CustomCog

if TYPE_CHECKING:
    from nextcord import Guild, Invite

    from bot import Smiffy
    from typings import DB_RESPONSE


class InviteUpdate(CustomCog):
    @CustomCog.listener()
    async def on_invite_update(self, guild: Guild):
        guild_data: Optional[DB_RESPONSE] = await self.get_guild_invites_data(guild)

        if guild_data is None:
            return

        timestamp: int = guild_data[2]
        notify_data: str = guild_data[3]

        await self.bot.db.execute_fetchone(
            "DELETE FROM server_invites WHERE guild_id = ?",
            (guild.id,),
        )

        invite_codes: list[dict[str, str | int]] = []

        for g_invite in await guild.invites():
            if g_invite.id and g_invite.inviter and g_invite.uses:
                invite_codes.append(
                    {
                        "invite_id": g_invite.id,
                        "invite_uses": g_invite.uses,
                        "inviter_id": g_invite.inviter.id,
                    }
                )

        await self.bot.db.execute_fetchone(
            "INSERT INTO server_invites(guild_id, invites_data, enabled_at, notify_data) VALUES(?,?,?,?)",
            (
                guild.id,
                str(invite_codes),
                timestamp,
                notify_data,
            ),
        )

    @CustomCog.listener()
    async def on_invite_create(self, invite: Invite):
        self.bot.dispatch("invite_update", invite.guild)

    @CustomCog.listener()
    async def on_invite_delete(self, invite: Invite):
        self.bot.dispatch("invite_update", invite.guild)


def setup(bot: Smiffy):
    bot.add_cog(InviteUpdate(bot))
