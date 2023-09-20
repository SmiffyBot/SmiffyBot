# pylint: disable=unused-argument

from __future__ import annotations
from typing import TYPE_CHECKING, Optional

from nextcord import SlashOption, Color, Role

from utilities import CustomInteraction, CustomCog, PermissionHandler
from typings import EconomyItemData
from enums import Emojis

from .__main__ import EconomyCog, EconomyManager

if TYPE_CHECKING:
    from bot import Smiffy


class CommandEditItem(CustomCog):
    def __init__(self, bot: Smiffy):
        super().__init__(bot=bot)

        self.option_converter: dict[str, str] = {
            "nowa_nazwa": "name",
            "cena": "price",
            "opis": "description",
            "wiadomość_zwrotna": "reply_message",
            "wymagana_rola": "required_role",
            "nadawana_rola": "given_role",
        }

    @EconomyCog.main.subcommand(  # pylint: disable=no-member   # pyright: ignore
        name="edytuj_przedmiot", description="Edytuje opcję przedmiotu"
    )
    @PermissionHandler(manage_guild=True)
    async def economy_edititem(
        self,
        interaction: CustomInteraction,
        item_name: str = SlashOption(name="nazwa_przedmiotu", description="Podaj nazwę przedmiotu"),
        new_name: Optional[str] = SlashOption(
            name="nowa_nazwa", description="Podaj nową nazwę przedmiotu", max_length=64
        ),
        price: Optional[int] = SlashOption(name="cena", description="Podaj nową cene przedmiotu"),
        description: Optional[str] = SlashOption(
            name="opis", description="Podaj nowy opis przedmiotu", max_length=256
        ),
        reply_message: Optional[str] = SlashOption(
            name="wiadomość_zwrotna",
            description="Tekst który ma być widoczny po zakupie przedmiotu",
            max_length=256,
        ),
        required_role: Optional[Role] = SlashOption(
            name="wymagana_rola",
            description="Podaj wymaganą role do zakupu tego przedmiotu",
        ),
        given_role: Optional[Role] = SlashOption(
            name="nadawana_rola",
            description="Rola, która ma być nadawana po zakupie przedmiotu",
        ),
    ):
        assert interaction.guild

        await interaction.response.defer()
        new_item_data: dict[str, int | str | None] = {}

        manager: EconomyManager = EconomyManager(bot=self.bot)

        if not await manager.get_guild_economy_status(interaction.guild):
            return await interaction.send_error_message(description="Ekonomia na serwerze jest wyłączona.")

        if not await manager.get_guild_item(guild=interaction.guild, item_name=item_name):
            return await interaction.send_error_message(description="Podany przedmiot nie istnieje.")

        if given_role:
            if given_role.is_default():
                new_item_data["given_role"] = None

            if given_role.is_bot_managed() or given_role.is_premium_subscriber():
                return await interaction.send_error_message(
                    description="Podana rola nie może zostać użyta jako nadawana rola."
                )

            if given_role.position >= interaction.guild.me.top_role.position:
                return await interaction.send_error_message(
                    description=f"Rola bota jest zbyt nisko, aby nadać role: {given_role.mention} przy zakupie."
                )

        if required_role:
            if required_role.is_default():
                new_item_data["required_role"] = None

            if required_role.is_bot_managed() or required_role.is_premium_subscriber():
                return await interaction.send_error_message(
                    description="Podana rola nie może zostać użyta jako wymagana rola."
                )

        data: dict[str, list[dict]] = interaction.data["options"][0]  # pyright: ignore
        options: list[dict[str, str | int]] = data["options"]

        if len(options) <= 1:
            return await interaction.send_error_message(description="Nie wybrałeś/aś żadnej opcji do edycji.")

        for option_data in options[1:]:
            option_name: str = self.option_converter[str(option_data["name"])]
            if option_name not in new_item_data:
                new_item_data[option_name] = option_data["value"]

        await manager.edit_guild_item(interaction.guild, item_name, new_item_data)
        await interaction.send_success_message(
            title=f"Pomyślnie zaktualizowano {Emojis.GREENBUTTON.value}",
            description=f"{Emojis.REPLY.value} Przedmiot o nazwie: `{item_name}` został zaktualizowany.",
            color=Color.dark_theme(),
        )

    @economy_edititem.on_autocomplete("item_name")
    async def edititem_autocomplete(
        self, interaction: CustomInteraction, query: Optional[str]
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
    bot.add_cog(CommandEditItem(bot))
