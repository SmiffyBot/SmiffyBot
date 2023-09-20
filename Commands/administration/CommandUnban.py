from __future__ import annotations
from typing import TYPE_CHECKING

from itertools import islice
from nextcord import slash_command, SlashOption, Object, Embed, Color, utils, errors

from utilities import (
    CustomInteraction,
    CustomCog,
    Optional,
    PermissionHandler,
)
from enums import Emojis

if TYPE_CHECKING:
    from bot import Smiffy
    from nextcord import BanEntry


class CommandUnban(CustomCog):
    @slash_command(name="unban", description="Odbanuj użytkownika!", dm_permission=False)  # pyright: ignore
    @PermissionHandler(ban_members=True, user_role_has_permission="unban")
    async def unban(
        self,
        interaction: CustomInteraction,
        member: str = SlashOption(name="osoba", description="Wybierz osobę którą chcesz odbanować."),
    ):
        assert interaction.guild and self.bot.user

        await interaction.response.defer()

        try:
            banned_user: BanEntry = await interaction.guild.fetch_ban(Object(id=int(member)))
        except (errors.Forbidden, errors.NotFound, errors.HTTPException):
            return await interaction.send_error_message(
                description="**Nie odnalazłem takiego użytkownika z banem.**",
            )

        if not banned_user:
            return await interaction.send_error_message(
                description="**Nie odnalazłem takiego użytkownika z banem.**",
            )

        await interaction.guild.unban(banned_user.user)

        embed = Embed(
            title=f"Pomyślnie odbanowano {Emojis.GREENBUTTON.value}",
            timestamp=utils.utcnow(),
            color=Color.green(),
        )
        embed.add_field(
            name="`👤` Użytkownik",
            value=f"{Emojis.REPLY.value} `{banned_user.user}`",
        )
        embed.set_thumbnail(url=interaction.guild_icon_url)
        embed.set_author(name=interaction.user, icon_url=interaction.user_avatar_url)

        embed.set_footer(
            text=f"Smiffy v{self.bot.__version__}",
            icon_url=self.bot.user.display_avatar.url,
        )

        await interaction.send(embed=embed)

    @unban.on_autocomplete("member")
    async def banned_members(self, interaction: CustomInteraction, query: Optional[str]) -> dict:
        if not interaction.guild:
            return {}

        ban_list: dict = {f"{ban.user}": f"{ban.user.id}" async for ban in interaction.guild.bans(limit=None)}

        if not query:
            # get the first 25 results without query

            search: dict = dict(islice(ban_list.items(), 25))

        else:
            # get first 25 results with user query

            get_near_ban: list = [ban for ban in ban_list if ban.lower().startswith(query.lower())]

            search: dict = {}

            for index, key in enumerate(get_near_ban):
                if index == 25:
                    break
                try:
                    search[key] = ban_list[key]
                except KeyError:
                    continue

        return search


def setup(bot: Smiffy):
    bot.add_cog(CommandUnban(bot))
