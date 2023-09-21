from __future__ import annotations

from typing import TYPE_CHECKING

from nextcord import Color, Embed, File, Guild, errors, utils, ui, ButtonStyle
from utilities import CustomCog, DiscordSupportButton

from enums import Emojis

if TYPE_CHECKING:
    from bot import Smiffy


class AddBotView(ui.View):

    def __init__(self, bot_id: int, permissions: int = 8):
        super().__init__(timeout=None)

        bot_invite: str = f"https://discord.com/api/oauth2/authorize?client_id={bot_id}" \
                          f"&permissions={permissions}&scope=bot%20applications.commands"

        self.add_item(
            ui.Button(
                style=ButtonStyle.link,
                url=bot_invite,
                label="Zaproś bota!",
            )
        )


class BotGuilds(CustomCog):
    @CustomCog.listener()
    async def on_guild_available(self, guild: Guild):
        assert self.bot.user

        if guild.me.guild_permissions.administrator:
            self.bot.dispatch("invite_update", guild)

        else:
            # Bot has not permission Administrator
            embed = Embed(
                title=f"{Emojis.REDBUTTON.value} Wystąpił błąd.",
                description=f"{Emojis.REPLY.value} Nie posiadam wymaganej permisji: `Administrator`."
                            f"\n\nJest ona wymagana to poprawnego działania. "
                            f"Dodaj mnie ponownie z zaproszenia poniżej i nie zmieniaj moich uprawnień.",
                color=Color.red(),
                timestamp=utils.utcnow()
            )
            embed.set_author(name=self.bot.user, icon_url=self.bot.avatar_url)
            embed.set_thumbnail(url=self.avatars.get_guild_icon(guild))

            for text_channel in guild.text_channels:
                try:
                    await text_channel.send(embed=embed, view=AddBotView(self.bot.user.id))
                    break
                except errors.Forbidden:
                    pass

            await guild.leave()

    @CustomCog.listener()
    async def on_guild_join(self, guild: Guild):
        if not guild.me.guild_permissions.administrator:
            self.bot.dispatch("guild_available", guild)
            
            return

        gif: File = File(
            "./Data/images/smiffy-help-2.gif",
            filename="bot.gif",
        )

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

        embed.set_author(
            name=self.bot.user,
            icon_url=self.bot.avatar_url,
        )

        embed.set_image(url="attachment://bot.gif")
        embed.set_footer(text=f"Serwery: {len(self.bot.guilds)}")

        for text_channel in guild.text_channels:
            try:
                await text_channel.send(
                    embed=embed,
                    file=gif,
                    view=DiscordSupportButton(),
                )
                break
            except errors.Forbidden:
                continue


def setup(bot: Smiffy):
    bot.add_cog(BotGuilds(bot))
