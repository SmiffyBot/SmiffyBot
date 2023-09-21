from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from nextcord import Color, Embed, Member, SlashOption, errors, slash_command, utils

from enums import Emojis
from utilities import Avatars, CustomCog, CustomInteraction, PermissionHandler

if TYPE_CHECKING:
    from bot import Smiffy


class CommandBan(CustomCog):
    @slash_command(name="ban", description="Zbanuj użytkownika!", dm_permission=False)  # pyright: ignore
    @PermissionHandler(ban_members=True, user_role_has_permission="ban")
    async def ban(
        self,
        interaction: CustomInteraction,
        member: Member = SlashOption(name="osoba", description="Podaj osobę, którą chcesz zbanować."),
        delete_messages: int = SlashOption(
            name="wiadomosci",
            description="Wybierz czy usuwać ostatnie" " wiadomości użytkownika",
            choices={"Ostatnie 7 dni": 7, "Ostatnie 24h": 1, "Nie usuwaj": 0},
        ),
        reason: Optional[str] = SlashOption(name="powod", description="Podaj powód bana", max_length=256),
    ):
        if not isinstance(member, Member) or not isinstance(interaction.user, Member):
            # This should never happen, but discord sometimes messes things up - not sure why.

            return await interaction.send_error_message(description="Wystąpił nieoczekiwany błąd. Kod: 51")

        assert delete_messages in (0, 1, 7) and self.bot.user and interaction.guild
        # Stuff for proper type checking

        await interaction.response.defer()

        if interaction.guild.me.top_role <= member.top_role or interaction.guild.owner_id == member.id:
            return await interaction.send_error_message(
                description=f"Użytkownik: {member.mention} posiada większe uprawnienia ode mnie."
            )
        if interaction.user.top_role.position <= member.top_role.position:
            return await interaction.send_error_message(
                description=f"Posiadasz zbyt małe uprawnienia, aby zbanować: {member.mention}"
            )
        if not reason:
            reason = "Brak"

        embed = Embed(
            title=f"Pomyslnie zbanowano {Emojis.GREENBUTTON.value}",
            timestamp=utils.utcnow(),
            color=Color.green(),
        )
        embed.set_thumbnail(url=interaction.guild_icon_url)
        embed.add_field(name="`👤` Użytkownik", value=f"{Emojis.REPLY.value} `{member}`")

        embed.add_field(name="`🗨️` Powód", value=f"{Emojis.REPLY.value} `{reason}`", inline=False)

        embed.set_author(name=interaction.user, icon_url=interaction.user_avatar_url)
        embed.set_footer(
            text=f"Smiffy v{self.bot.__version__}",
            icon_url=self.bot.user.display_avatar.url,
        )

        try:
            await self.send_dm_message(member=member, reason=reason, root=interaction.user)
            await member.ban(reason=reason, delete_message_days=delete_messages)  # pyright: ignore

        except Exception as exception:  # pylint: disable=broad-exception-caught
            return await interaction.send_error_message(
                description=f"Wystąpił nieoczekiwany błąd. `{exception}`"
            )

        await interaction.send(embed=embed)

    async def send_dm_message(self, member: Member, reason: str, root: Member) -> None:
        embed = Embed(
            title=f"Zostałeś/aś zbanowany/a {Emojis.REDBUTTON.value}",
            timestamp=utils.utcnow(),
            color=Color.red(),
        )
        embed.set_author(name=root, icon_url=root.display_avatar.url)
        embed.set_thumbnail(url=Avatars.get_guild_icon(root.guild))

        embed.add_field(name="`👤` Administrator", value=f"{Emojis.REPLY.value} `{root}`")
        embed.add_field(name="`🗨️` Powód", value=f"{Emojis.REPLY.value} `{reason}`", inline=False)
        embed.add_field(name="`📌` Serwer", value=f"{Emojis.REPLY.value} `{root.guild.name}`")

        embed.set_footer(text=f"Smiffy v{self.bot.__version__}", icon_url=self.bot.avatar_url)

        try:
            await member.send(embed=embed)
        except errors.Forbidden:
            pass


def setup(bot: Smiffy):
    bot.add_cog(CommandBan(bot))
