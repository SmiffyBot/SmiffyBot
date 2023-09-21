from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from nextcord import Member, SlashOption

from enums import Emojis
from typings import EconomyItemData, EconomyUserData
from utilities import CustomCog, CustomInteraction

from .__main__ import EconomyCog, EconomyManager

if TYPE_CHECKING:
    from bot import Smiffy


class CommandSell(CustomCog):
    @EconomyCog.main.subcommand(  # pylint: disable=no-member
        name="sprzedaj",
        description="Sprzedaje przedmiot za 50% ceny sklepu",
    )
    async def economy_buy(
        self,
        interaction: CustomInteraction,
        item_name: str = SlashOption(
            name="nazwa_predmiotu",
            description="Podaj nazwę przedmiotu którego chcesz sprzedać",
            max_length=32,
        ),
    ):
        assert isinstance(interaction.user, Member) and interaction.guild

        await interaction.response.defer()

        manager: EconomyManager = EconomyManager(bot=self.bot)

        if not await manager.get_guild_economy_status(interaction.guild):
            return await interaction.send_error_message(description="Ekonomia na serwerze jest wyłączona.")

        item_data: Optional[EconomyItemData] = await manager.get_guild_item(
            guild=interaction.guild,
            item_name=item_name,
        )
        if not item_data:
            return await interaction.send_error_message(description="Podany przedmiot nie istnieje.")

        user_data: EconomyUserData = await manager.get_user_data(interaction.user)
        user_items: list[str] = user_data["items"]
        item_id: str = item_data["item_id"]

        if item_id not in user_items:
            return await interaction.send_error_message(description="Nie posiadasz podanego przedmiotu.")

        user_items.remove(item_id)
        item_price: int = int(item_data["price"] / 2)

        await manager.add_user_money(
            interaction.user,
            {"money": item_price},
        )
        await manager.update_user_account(
            interaction.user,
            data={"items": user_items},
        )

        await interaction.send_success_message(
            title=f"Pomyślnie sprzedano {Emojis.GREENBUTTON.value}",
            description=f"{Emojis.REPLY.value} Pomyślnie sprzedano przedmiot: `{item_name}`",
        )

    @economy_buy.on_autocomplete("item_name")
    async def buy_autocomplete(
        self,
        interaction: CustomInteraction,
        query: Optional[str],
    ) -> Optional[list[str]]:
        assert interaction.guild and isinstance(interaction.user, Member)

        manager: EconomyManager = EconomyManager(bot=self.bot)

        if not await manager.get_guild_economy_status(interaction.guild):
            return None

        user_data: EconomyUserData = await manager.get_user_data(interaction.user)

        user_items_ids: list[str] = user_data["items"]
        if len(user_items_ids) == 0:
            return None

        items: list[str] = []
        for item_id in user_items_ids:
            item: Optional[EconomyItemData] = await manager.get_guild_item(interaction.guild, item_id=item_id)
            if item and item["name"] not in items:
                items.append(item["name"])

        if not query:
            return items

        get_near_item: list[str] = [
            item_name for item_name in items if item_name.lower().startswith(query.lower())
        ]
        return get_near_item


def setup(bot: Smiffy):
    bot.add_cog(CommandSell(bot))
