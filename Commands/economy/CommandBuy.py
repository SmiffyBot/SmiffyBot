from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from nextcord import Color, Member, Role, SlashOption, errors

from enums import Emojis
from typings import EconomyItemData, EconomyUserData
from utilities import CustomCog, CustomInteraction

from .__main__ import EconomyCog, EconomyManager

if TYPE_CHECKING:
    from bot import Smiffy


class CommandBuy(CustomCog):
    @EconomyCog.main.subcommand(  # pylint: disable=no-member
        name="kup",
        description="Kupuje przedmiot ze sklepu",
    )
    async def economy_buy(
        self,
        interaction: CustomInteraction,
        item_name: str = SlashOption(
            name="nazwa_predmiotu",
            description="Podaj nazwę przedmiotu którego chcesz kupić",
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
        total_items: dict[str, int] = {}

        for __item in user_items:
            amount: int = total_items.get(__item, 0)
            amount += 1
            total_items[__item] = amount

        if len(total_items) >= 50:
            return await interaction.send_error_message(
                description="Osiągnięto limit `50` unikalnych przedmiotów w ekwipunku."
            )

        user_money: int = user_data["money"]
        if item_data["price"] > user_money:
            return await interaction.send_error_message(
                description="Nie posiadasz tylu pieniędzy w portfelu, aby zakupić ten przedmiot."
            )

        if item_data["required_role"]:
            role_id: int = item_data["required_role"]

            role: Optional[Role] = await self.bot.getch_role(interaction.guild, role_id=role_id)
            if role and role not in interaction.user.roles:
                return await interaction.send_error_message(
                    description=f"Nie posiadasz wymaganej roli: {role.mention}, aby zakupić ten przedmiot."
                )

        if item_data["given_role"]:
            role_id: int = item_data["given_role"]
            role: Optional[Role] = await self.bot.getch_role(interaction.guild, role_id=role_id)
            if role and role not in interaction.user.roles:
                try:
                    await interaction.user.add_roles(role)
                except (
                    errors.Forbidden,
                    errors.HTTPException,
                ):
                    pass

        user_money -= item_data["price"]
        user_items.append(item_data["item_id"])

        await manager.update_user_account(
            user=interaction.user,
            data={
                "money": user_money,
                "items": user_items,
            },
        )

        if not item_data["reply_message"]:
            description: str = f"{Emojis.REPLY.value} Przedmiot: `{item_name}` został pomyślnie zakupiony!"
        else:
            description: str = item_data["reply_message"]

        await interaction.send_success_message(
            title=f"Pomyślnie zakupiono {Emojis.GREENBUTTON.value}",
            description=description,
            color=Color.green(),
        )

    @economy_buy.on_autocomplete("item_name")
    async def buy_autocomplete(
        self,
        interaction: CustomInteraction,
        query: Optional[str],
    ) -> Optional[list[str]]:
        assert interaction.guild

        manager: EconomyManager = EconomyManager(bot=self.bot)

        items: list[EconomyItemData] = await manager.get_guild_shop(guild=interaction.guild)
        if not items:
            return None

        items_name: list[str] = [data["name"] for data in items]
        if not query:
            return items_name

        get_near_item: list[str] = [item for item in items_name if item.lower().startswith(query.lower())]
        return get_near_item


def setup(bot: Smiffy):
    bot.add_cog(CommandBuy(bot))
