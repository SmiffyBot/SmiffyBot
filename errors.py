class SmiffyException(Exception):
    pass


class MissingBotToken(SmiffyException):
    def __init__(self) -> None:
        super().__init__("Fill the token in the configuration file.")


class InvalidServerData(SmiffyException):
    def __init__(self) -> None:
        super().__init__("Invalid the server data in the configuration file.")


class MissingSpotifyData(SmiffyException):
    def __init__(self) -> None:
        super().__init__("Fill the spotify data in the configuration file.")


class MissingMusicPermissions(SmiffyException):
    def __init__(self, text: str):
        super().__init__(text)


class ApplicationCommandIsGuildOnly(SmiffyException):
    def __init__(self, command: str):
        super().__init__(f"{command} is guild only.")
