from __future__ import annotations

from asyncio import sleep
from random import choice, randint
from typing import TYPE_CHECKING, Optional

from cooldowns import CallableOnCooldown, shared_cooldown
from nextcord import Color, Embed, File, Member, SlashOption, utils

from enums import Emojis
from utilities import CustomCog, CustomInteraction

from .__main__ import EconomyCog, EconomyManager

if TYPE_CHECKING:
    from bot import Smiffy
    from typings import DB_RESPONSE


class CommandCoinflip(CustomCog):
    @EconomyCog.main.subcommand(  # pylint: disable=no-member
        name="rzut_moneta", description="Rzut monetą o pieniądze"
    )
    @shared_cooldown("command_coinflip")
    async def economy_coinflip(
        self,
        interaction: CustomInteraction,
        bet: int = SlashOption(name="stawka", description="Podaj stawkę"),
        option: str = SlashOption(
            name="wybór",
            description="Wybierz orzeł czy reszka",
            choices=["orzeł", "reszka"],
        ),
    ):
        await interaction.response.defer()
        assert isinstance(interaction.user, Member) and interaction.guild

        manager: EconomyManager = EconomyManager(bot=self.bot)
        if not await manager.get_guild_economy_status(interaction.guild):
            return await interaction.send_error_message(description="Ekonomia na serwerze jest wyłączona.")

        if bet < 10:
            return await interaction.send_error_message(description="Stawka nie może być niższa niż: `10`")

        (
            money,
            bank_money,  # pylint: disable=unused-variable
        ) = await manager.get_user_balance(interaction.user)
        if bet > money:
            return await interaction.send_error_message(
                description="Nie posiadasz tylu pieniędzy w portfelu."
            )

        embed = Embed(
            title="Rzucanie monetą...",
            color=Color.light_grey(),
            timestamp=utils.utcnow(),
        )
        embed.set_author(name=interaction.user, icon_url=interaction.user_avatar_url)
        await interaction.send(embed=embed)

        await sleep(randint(2, 4))

        result: str = choice(["orzeł", "reszka"])
        image = File(f"./Data/images/{result.lower()}.png", filename="image.png")

        if result == option:
            embed = Embed(
                title="`🍀` Gratulacje! Wygrałeś/aś!",
                color=Color.green(),
                timestamp=utils.utcnow(),
                description=f"{Emojis.REPLY.value} Twoja wygrana to: **{int(bet * 1.5)}$**",
            )
            await manager.add_user_money(interaction.user, {"money": int(bet * 1.5)})
        else:
            embed = Embed(
                title="`💢` Niestety, przegrałeś/aś!",
                color=Color.red(),
                timestamp=utils.utcnow(),
                description=f"{Emojis.REPLY.value} Twoja przegrana to: **{int(bet * 2)}$**",
            )
            await manager.remove_user_money(interaction.user, int(bet * 2))

        embed.set_author(name=interaction.user, icon_url=interaction.user_avatar_url)
        embed.set_image(url="attachment://image.png")
        await interaction.edit_original_message(embed=embed, file=image)

    @economy_coinflip.error  # pyright: ignore
    async def economy_coinflip_error(self, interaction: CustomInteraction, error):
        assert interaction.guild

        error = getattr(error, "original", error)

        if isinstance(error, CallableOnCooldown):
            response: Optional[DB_RESPONSE] = await self.bot.db.execute_fetchone(
                "SELECT coin_flip_cooldown FROM economy_settings WHERE guild_id = ?",
                (interaction.guild.id,),
            )

            if not response or not response[0]:
                return await interaction.send_error_message(description="Wystąpił nieoczekiwany błąd.")

            waited_seconds: Optional[int] = EconomyManager.get_waited_seconds(interaction, "command_coinflip")
            if not waited_seconds:
                return await interaction.send_error_message(description="Spróbuj ponownie użyć komendy.")

            cooldown_seconds: int = response[0]

            remaining_seconds: int = int(cooldown_seconds - waited_seconds)

            await interaction.send_error_message(
                description=f"Tej komendy możesz użyć dopiero za: `{remaining_seconds}s`"
            )


def setup(bot: Smiffy):
    bot.add_cog(CommandCoinflip(bot))
