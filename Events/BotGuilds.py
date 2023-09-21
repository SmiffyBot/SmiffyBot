from __future__ import annotations

from typing import TYPE_CHECKING

from nextcord import Color, Embed, File, Guild, errors, utils

from utilities import CustomCog, DiscordSupportButton

if TYPE_CHECKING:
    from bot import Smiffy


class BotGuilds(CustomCog):
    @CustomCog.listener()
    async def on_guild_available(self, guild: Guild):
        self.bot.dispatch("invite_update", guild)

    @CustomCog.listener()
    async def on_guild_join(self, guild: Guild):
        for text_channel in guild.text_channels:
            try:
                gif: File = File("./Data/images/smiffy-help-2.gif", filename="bot.gif")
                commands: int = len(self.bot.get_all_application_commands())
                help_mention: str = "</help:1040624807768752188>"
                report_bug_mention: str = "</bot blad:1092585173029244930>"

                description: str = f"""## <a:hello:1129534241617739866> Cześć! Nazywam się Smiffy
- `🔧` Pozwól, że pomogę ci skonfigurować Twój serwer. Aktualnie posiadam: `{commands}` poleceń, które możesz \
sprawdzić używając {help_mention}.

- `❌` Jeśli znajdziesz jakiś błąd, zgłoś go proszę na serwerze bota lub komendą {report_bug_mention}.

- `〽️` Masz ciekawą propozycje dotyczącą bota? Napisz ją na serwerze bota!
"""
                embed = Embed(
                    color=Color.dark_theme(),
                    timestamp=utils.utcnow(),
                    description=description,
                )

                embed.set_author(name=guild.me, icon_url=self.bot.avatar_url)

                embed.set_image(url="attachment://bot.gif")
                embed.set_footer(text=f"Serwery: {len(self.bot.guilds)}")

                await text_channel.send(embed=embed, file=gif, view=DiscordSupportButton())
                break
            except (errors.Forbidden, errors.HTTPException):
                continue


def setup(bot: Smiffy):
    bot.add_cog(BotGuilds(bot))
