from aiogram.utils.i18n import lazy_gettext


class MimbusException(Exception):
    pass


class UserException(MimbusException):
    MESSAGE = lazy_gettext(
        'General mimbus exception. Please contact the bot administrator.'
    )


class RetryException(UserException):
    MESSAGE = lazy_gettext(
        'Failed to connect to the proxy server. '
        'Try again later or contact the bot administrator.'
    )


class APIException(UserException):
    MESSAGE = lazy_gettext(
        'Mimbus returned not OK status for your request. '
        'Check the correctness of the operation and try again.\n'
        'Try /relogin if you are sure that operation is correct.'
    )


class SteamException(MimbusException):
    pass
