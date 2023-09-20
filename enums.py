from enum import Enum
from nextcord import TextChannel, VoiceChannel, StageChannel, CategoryChannel


class Emojis(str, Enum):
    GREENBUTTON = "<a:greenbutton:919647666101694494>"
    REDBUTTON = "<a:redbutton:919647776885850182>"
    REPLY = "<:reply:1129168370642718833>"
    ARROW = "<a:arrow:951977750959366164>"
    A_GEARS = "<a:gears:1139620202607292580>"
    NEW_CHANNEL = "<:newchannel:992453719679586425>"


class GuildChannelTypes(Enum):
    text_channels = TextChannel
    voice_channels = VoiceChannel
    stage_channels = StageChannel
    categories = CategoryChannel
