from __future__ import annotations

from asyncio import sleep
from typing import TYPE_CHECKING, Optional

from nextcord import Color, Embed, slash_command, utils

from enums import Emojis
from utilities import CustomCog, CustomInteraction, PermissionHandler

if TYPE_CHECKING:
    from bot import Smiffy
    from typings import DB_RESPONSE


class CommandSettings(CustomCog):
    def __init__(self, bot: Smiffy) -> None:
        super().__init__(bot)

        self.settings_dict: dict[str, str] = {
            "AntyLink": "antylink",
            "Logi": "server_logs",
            "StartowaRola": "startrole",
            "Propozycje": "suggestions",
            "Kary-Warny": "warnings_punishments",
            "Levelowanie": "levels",
            "Tickety": "tickets",
            "ReactionRole": "reactionroles",
            "Powiadomenia-Youtube": "yt_notifications",
            "Weryfikacja": "verifications",
            "Przywitania": "welcomes",
            "Pożegnania": "goodbyes",
            "AntyGhostPing": "antyghostping",
            "Ekonomia": "economy_settings",
            "Formularze": "forms",
            "AntyFlood": "antyflood",
            "AutoResponder": "autoresponder",
            "Partnerstwa": "partnerships",
            "Zaproszenia": "server_invites",
        }

    @slash_command(  # pyright: ignore
        name="ustawienia",
        description="Pokaże ci status wszystkich ustawień na serwerze",
        dm_permission=False,
    )
    @PermissionHandler(manage_guild=True)
    async def settings(self, interaction: CustomInteraction) -> None:
        await interaction.response.defer()

        help_mention: str = interaction.get_command_mention(command_name="help")

        embed = Embed(
            title="`🛠️` Ustawienia na serwerze",
            description=f"{Emojis.REPLY.value} Sprawdź komendy ustawień używając {help_mention}",
            color=Color.yellow(),
            timestamp=utils.utcnow(),
        )
        embed.set_thumbnail(url=interaction.guild_icon_url)
        embed.set_footer(text="Ładowanie...")
        embed.set_author(name=interaction.user, icon_url=interaction.user_avatar_url)

        await interaction.followup.send(embed=embed)
        seconds: float = 0

        for name, raw_name in self.settings_dict.items():
            response: Optional[DB_RESPONSE] = await self.bot.db.execute_fetchone(
                f"SELECT * FROM {raw_name} WHERE guild_id = ?", (interaction.guild_id,)
            )

            if response:
                embed.add_field(
                    name=f"`🔧` {name}",
                    value=f"{Emojis.REPLY.value} <:icon_switch_on:1001386806861901956> *(Włączone)*",
                )
            else:
                embed.add_field(
                    name=f"`🔧` {name}",
                    value=f"{Emojis.REPLY.value} <:icon_switch_off:1001386805121269800> *(Wyłączone)*",
                )

            await interaction.edit_original_message(embed=embed)
            await sleep(0.1)

            seconds += 0.1

        embed.set_footer(text=f"Załadowano w {round(seconds, 3)}s")
        await interaction.edit_original_message(embed=embed)


def setup(bot: Smiffy):
    bot.add_cog(CommandSettings(bot))
