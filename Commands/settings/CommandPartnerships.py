from __future__ import annotations

from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Iterable, Optional

from cooldowns import CallableOnCooldown, SlashBucket, cooldown, reset_cooldown
from nextcord import (
    Color,
    Guild,
    Invite,
    Permissions,
    SlashOption,
    TextChannel,
    TextInputStyle,
    errors,
    slash_command,
    ui,
)

from enums import Emojis
from utilities import CustomCog, CustomInteraction, PermissionHandler

if TYPE_CHECKING:
    from nextcord.abc import GuildChannel

    from bot import Smiffy
    from typings import DB_RESPONSE
    from cache import CachedGuild


class PartnershipAdText(ui.Modal):
    def __init__(self, channel: TextChannel):
        super().__init__(title="Treść Reklamy")

        self.channel: TextChannel = channel

        self.ADText = ui.TextInput(
            label="Podaj treść reklamy",
            max_length=3000,
            min_length=10,
            style=TextInputStyle.paragraph,
            placeholder="Wiadomość, która ma być wysyłana na inne serwery",
        )

        self.add_item(self.ADText)

    async def callback(self, interaction: CustomInteraction):
        assert interaction.guild

        ad_content: Optional[str] = self.ADText.value
        bot: Smiffy = interaction.bot

        if not ad_content:
            return await interaction.send_error_message(description="Wystąpił nieoczekiwany błąd.")

        permissions: Permissions = self.channel.permissions_for(interaction.guild.default_role)
        if not permissions.read_messages or not permissions.read_message_history:
            return await interaction.send_error_message(
                description=f"Domyślna rola: {interaction.guild.default_role} nie ma permisji do czytania wiadomości / "
                f"historii wiadomości na kanale: `{self.channel}`"
            )

        response: Optional[DB_RESPONSE] = await bot.db.execute_fetchone(
            "SELECT * FROM partnerships WHERE guild_id = ?",
            (interaction.guild.id,),
        )
        if response:
            return await interaction.send_error_message(description="Na serwerze już są włączone partnerstwa")

        await bot.db.execute_fetchone(
            "INSERT INTO partnerships(guild_id, channel_id, ad_text) VALUES(?,?,?)",
            (
                interaction.guild.id,
                self.channel.id,
                ad_content,
            ),
        )
        command_mention: str = interaction.get_command_mention(
            command_name="partnerstwa",
            sub_command="bump",
        )

        return await interaction.send_success_message(
            title=f"Pomyślnie włączono partnerstwa {Emojis.GREENBUTTON.value}",
            color=Color.green(),
            description=f"{Emojis.REPLY.value} Kanał: {self.channel.mention}\n\n> Użyj: {command_mention}, aby wysłać.",
        )


class CommandPartnerships(CustomCog):
    @slash_command(name="partnerstwa", dm_permission=False)
    async def partnerships(self, interaction: CustomInteraction):  # pylint: disable=unused-argument
        ...

    async def send_ad_to_all_servers(
        self,
        ad_message: str,
        inter: CustomInteraction,
    ):
        assert inter.guild and self.bot.user

        response: Iterable[DB_RESPONSE] = await self.bot.db.execute_fetchall("SELECT * FROM partnerships")
        cached_main_guild: Optional[CachedGuild] = await self.bot.cache.get_guild(inter.guild.id)
        main_guild: Optional[Guild] = cached_main_guild.guild if cached_main_guild else None

        for partnership_data in response:
            guild_id: int = partnership_data[0]
            channel_id: int = partnership_data[1]

            if partnership_data[0] == inter.guild.id:
                cached_guild: Optional[CachedGuild] = await self.bot.cache.get_guild(guild_id)
                guild: Optional[Guild] = cached_guild.guild if cached_guild else None

                if not guild:
                    continue

                channel: Optional[GuildChannel] = await self.bot.cache.get_channel(guild.id, channel_id)
                if not isinstance(channel, TextChannel):
                    continue

                if main_guild:
                    date: datetime = datetime.utcnow() + timedelta(hours=-23)
                    guild_invites: list[Invite] = await main_guild.invites()
                    if guild_invites:
                        async for message in channel.history(after=date):
                            if message.author.bot and message.author.id == self.bot.user.id:
                                for invite in guild_invites:
                                    if invite.code and invite.code in message.content:
                                        await inter.send_error_message(
                                            "Wygląda na to że reklama twojego serwera już została wysłana w ciągu "
                                            "ostatnich 24h "
                                        )
                                        return True

                try:
                    permissions: Permissions = channel.permissions_for(guild.default_role)
                    if not permissions.read_messages or not permissions.read_message_history:
                        await channel.set_permissions(
                            target=guild.default_role,
                            read_messages=True,
                        )
                        await channel.set_permissions(
                            target=guild.default_role,
                            read_message_history=True,
                        )

                    try:
                        await channel.send(ad_message)
                    except (
                        errors.HTTPException,
                        errors.Forbidden,
                    ):
                        self.bot.logger.warning(f"Failed to send PartnerShip AD: {channel} | {guild}")

                except (
                    errors.HTTPException,
                    errors.Forbidden,
                ):
                    pass

    @partnerships.subcommand(
        name="bump",
        description="Wysyła reklame serwera na wszystkie serwery z partnerstwami.",
    )
    @cooldown(
        1,
        86400,
        bucket=SlashBucket.guild,
        cooldown_id="partnership_bump",
    )
    async def partnerships_bump(self, interaction: CustomInteraction):
        assert interaction.guild

        await interaction.response.defer()

        response: Optional[DB_RESPONSE] = await self.bot.db.execute_fetchone(
            "SELECT * FROM partnerships WHERE guild_id = ?",
            (interaction.guild.id,),
        )

        if not response:
            reset_cooldown("partnership_bump")
            return await interaction.send_error_message(
                description="Na serwerze nie ma włączonych partnerstw"
            )

        ad_message: str = response[2]

        if not await self.send_ad_to_all_servers(ad_message, interaction):
            return await interaction.send_success_message(
                title=f"Pomyślnie wysłano reklame {Emojis.GREENBUTTON.value}",
                description=f"{Emojis.REPLY.value} Twoja reklama została wysłana do wszystkich serwerów, "
                f"które mają włączone partnerstwa!\n\n"
                f"**Komendy można używać co 24h! Omijanie tej zasady grozi blokadą bota na serwrze.**",
                color=Color.green(),
            )

    @partnerships_bump.error  # pyright: ignore
    async def partnership_bump_error(
        self,
        interaction: CustomInteraction,
        error,
    ):
        error = getattr(error, "original", error)

        if isinstance(error, CallableOnCooldown):
            return await interaction.send_error_message(
                description=f"Tej komendy możesz użyć dopiero za `{int(error.retry_after / 60)}` minut."
            )

    @partnerships.subcommand(  # pyright: ignore
        name="włącz",
        description="Włącza system partnerstw na serwerze.",
    )
    @PermissionHandler(manage_guild=True)
    async def partnerships_on(
        self,
        interaction: CustomInteraction,
        channel: TextChannel = SlashOption(
            name="kanał",
            description="Podaj kanał do partnerstw",
        ),
    ):
        modal = PartnershipAdText(channel)
        await interaction.response.send_modal(modal)

    @partnerships.subcommand(  # pyright: ignore
        name="wyłącz",
        description="Wyłącza system partnerstw na serwerze.",
    )
    @PermissionHandler(manage_guild=True)
    async def partnerships_off(self, interaction: CustomInteraction):
        assert interaction.guild

        await interaction.response.defer()

        response: Optional[DB_RESPONSE] = await self.bot.db.execute_fetchone(
            "SELECT * FROM partnerships WHERE guild_id = ?",
            (interaction.guild.id,),
        )
        if not response:
            return await interaction.send_error_message(
                description="Na serwerze nie ma włączonych partnerstw."
            )

        await self.bot.db.execute_fetchone(
            "DELETE FROM partnerships WHERE guild_id = ?",
            (interaction.guild.id,),
        )

        return await interaction.send_success_message(
            title=f"Pomyślnie wyłączono partnerstwa {Emojis.GREENBUTTON.value}",
            color=Color.dark_theme(),
            description=f"{Emojis.REPLY.value} Partnerstwa zostały wyłączone.",
        )


def setup(bot: Smiffy):
    bot.add_cog(CommandPartnerships(bot))
