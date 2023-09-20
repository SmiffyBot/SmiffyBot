from __future__ import annotations

from typing import TYPE_CHECKING

from nextcord import Embed, Color, utils, slash_command, SlashOption
from geopy.geocoders import Nominatim

from utilities import CustomInteraction, CustomCog
from enums import Emojis

if TYPE_CHECKING:
    from utilities import Optional, ClientResponse
    from bot import Smiffy


class CommandWeather(CustomCog):
    def __init__(self, bot: Smiffy) -> None:
        super().__init__(bot=bot)

        self._base_url: str = (
            "https://api.open-meteo.com/v1/forecast?latitude={}&longitude={}&current_weather=true"
        )

    @slash_command(
        name="pogoda",
        description="Bot pokaże aktualną pogodę w dowolnym miejscu",
        dm_permission=False,
    )
    async def weather(
        self,
        interaction: CustomInteraction,
        place: str = SlashOption(name="miejsce", description="Podaj miejsce które chcesz sprawdzić"),
    ):
        await interaction.response.defer()

        geolocator = Nominatim(user_agent=f"SmiffyBot/v{self.bot.__version__}")
        location = geolocator.geocode(place)

        if not location:
            return await interaction.send_error_message(description=f"Nie odnaleziono miejsca: `{place}`")

        latitude, longitude = location.latitude, location.longitude  # pyright: ignore

        response: Optional[ClientResponse] = await self.bot.session.send_api_request(
            interaction=interaction,
            url=self._base_url.format(latitude, longitude),
            method="GET",
            default_headers=False,
        )

        if not response:
            return

        data: dict = await response.json()

        weather_data: dict = data["current_weather"]
        temperature: float = weather_data["temperature"]
        windspeed: float = weather_data["windspeed"]
        observation_time: str = str(utils.utcnow())[0:19]

        embed = Embed(
            title=f"Pogoda: {place}",
            color=Color.green(),
            timestamp=utils.utcnow(),
            description=f"- **Czas obserwacji:** `{observation_time}`",
        )
        embed.set_author(name=interaction.user, icon_url=interaction.user_avatar_url)
        embed.set_thumbnail(url=interaction.guild_icon_url)
        embed.add_field(name="`🔆` Temperatura", value=f"{Emojis.REPLY.value} **●** {temperature} C")
        embed.add_field(
            name="`💨` Prędkość wiatru", value=f"{Emojis.REPLY.value} **●** {windspeed} km/h", inline=False
        )
        await interaction.send(embed=embed)


def setup(bot: Smiffy):
    bot.add_cog(CommandWeather(bot))
