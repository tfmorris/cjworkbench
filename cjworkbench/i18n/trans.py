from bs4 import BeautifulSoup
from django.utils.functional import lazy
from django.utils.html import escape
from django.utils.translation import get_language
from cjworkbench.i18n import default_locale, supported_locales
from cjworkbench.i18n.catalogs import load_catalog
from cjworkbench.i18n.catalogs.util import find_string
from string import Formatter
from cjworkbench.i18n.exceptions import UnsupportedLocaleError, BadCatalogsError
from icu import Formattable, Locale, MessageFormat, ICUError
from babel.messages.catalog import Catalog, Message
from babel.messages.pofile import read_po, PoFileError
from typing import Dict, Union, Optional
import logging
from cjwstate.models.module_registry import MODULE_REGISTRY
from cjwstate.modules.types import ModuleZipfile
from weakref import WeakKeyDictionary, WeakValueDictionary
import threading
from io import BytesIO

_translators = {}


logger = logging.getLogger(__name__)


_TagAttributes = Dict[str, str]
""" Each attribute name is mapped to its value
"""
_Tag = Dict[str, Union[str, _TagAttributes]]
""" Has two keys: 'name': str, and 'attrs': _TagAttributes. 'attrs' is optional
"""
# We can define `_Tag` more precisely in python 3.8 used a `TypedDict`
_TagMapping = Dict[str, _Tag]
""" Maps each tag to its data
"""

_MessageArguments = Dict[str, Union[int, float, str]]


def trans(message_id: str, *, default: str, arguments: _MessageArguments = {}) -> str:
    """Mark a message for translation and localize it to the current locale.

    `default` is only considered when parsing code for message extraction.
    If the message is not found in the catalog for the current or the default locale, return `None`,
    raise `KeyError`.
    
    For code parsing reasons, respect the following order when passing keyword arguments:
        `message_id` and then `default` and then everything else
    """
    return localize(get_language(), message_id, arguments=arguments)


trans_lazy = lazy(trans)
"""Mark a string for translation, but actually localize it when it has to be used.
   See the documentation of `trans` for more details on the function and its arguments.
"""


def localize(locale_id: str, message_id: str, arguments: _MessageArguments = {}) -> str:
    """Localize the given message ID to the given locale.

    Raise `KeyError` if the message is not found (neither in the catalogs of the given and of the default locale).
    Raise `ICUError` if the message in the default locale is incorrectly formatted.
    """
    return MESSAGE_LOCALIZER_REGISTRY.for_application().localize(
        locale_id, message_id, arguments=arguments
    )


def localize_html(
    locale_id: str,
    message_id: str,
    context: Optional[str] = None,
    arguments: _MessageArguments = {},
    tags: _TagMapping = {},
) -> str:
    """Localize the given message ID to the given locale, escaping HTML.
    
    Raise `KeyError` if the message is not found (neither in the catalogs of the given and of the default locale).
    Raise `ICUError` if the message in the default locale is incorrectly formatted.
    
    HTML is escaped in the message, as well as in arguments and tag attributes.
    """
    return MESSAGE_LOCALIZER_REGISTRY.for_application().localize_html(
        locale_id, message_id, arguments=arguments, tags=tags, context=context
    )


class MessageCatalogsRegistry:
    def __init__(self, catalogs: Dict[str, Catalog]):
        self.catalogs = catalogs

    def find_message(
        self, locale_id: str, message_id: str, context: Optional[str] = None
    ) -> str:
        """Find the message with the given id in the given locale.
        
        Raise `KeyError` if the locale has no catalog or the catalog has no such message.
        """
        message = find_string(self.catalogs[locale_id], message_id, context=context)
        if message:
            return message
        else:
            raise KeyError(message_id)

    @classmethod
    def for_application(cls):
        return cls(
            {locale_id: load_catalog(locale_id) for locale_id in supported_locales}
        )

    @classmethod
    def for_module_zipfile(cls, module_zipfile: ModuleZipfile):
        catalogs = {}
        for locale_id in supported_locales:
            try:
                catalogs[locale_id] = read_po(
                    BytesIO(module_zip.read_messages_po_for_locale(locale_id)),
                    abort_invalid=True,
                )
            except PoFileError as err:
                logger.exception(
                    f"Invalid po file for module {module_zipfile.module_id_and_version} in locale {locale_id}: {err}"
                )
                catalogs[locale_id] = Catalog()
        return cls(catalogs)


class MessageLocalizer:
    def __init__(self, registry: MessageCatalogsRegistry):
        self.catalogs_registry = registry

    def localize(
        self, locale_id: str, message_id: str, arguments: _MessageArguments = {}
    ) -> str:
        if locale_id != default_locale:
            try:
                message = self.catalogs_registry.find_message(locale_id, message_id)
                return icu_format_message(locale_id, message, arguments=arguments)
            except ICUError as err:
                logger.exception(
                    f"Error in po file for locale {locale_id} and message {message_id}: {err}"
                )
            except KeyError as err:
                pass
        message = self.catalogs_registry.find_message(default_locale, message_id)
        return icu_format_message(default_locale, message, arguments=arguments)

    def localize_html(
        self,
        locale_id: str,
        message_id: str,
        *,
        context: Optional[str],
        arguments: _MessageArguments,
        tags: _TagMapping,
    ) -> str:
        if locale_id != default_locale:
            try:
                message = self.catalogs_registry.find_message(
                    locale_id, message_id, context=context
                )
                return icu_format_html_message(
                    locale_id, message, arguments=arguments, tags=tags
                )
            except ICUError as err:
                logger.exception(
                    f"Error in po file for locale {locale_id} and message {message_id}: {err}"
                )
            except KeyError as err:
                pass
        message = self.catalogs_registry.find_message(
            default_locale, message_id, context=context
        )
        return icu_format_html_message(
            default_locale, message, arguments=arguments, tags=tags
        )

    @classmethod
    def for_application(cls):
        """Return a `MessageLocalizer` for the application internal messages.
        """
        return cls(MessageCatalogsRegistry.for_application())

    @classmethod
    def for_module_zipfile(cls, module_zipfile: ModuleZipfile):
        """Return a `MessageLocalizer` for the messages of the given module.
        """
        return cls(MessageCatalogsRegistry.for_module_zipfile(module_zipfile))


class MessageLocalizerRegistry:
    def __init__(self):
        self._supported_modules = WeakValueDictionary()
        self._module_localizers = WeakKeyDictionary()
        self._module_localizers_lock = threading.Lock()
        self._app_localizer = MessageLocalizer.for_application()

    def for_module_id(self, module_id: str) -> MessageLocalizer:
        with self._module_localizers_lock:
            return self._module_localizers[self._supported_modules[module_id]]

    def for_application(self):
        return self._app_localizer

    def update_supported_modules(self):
        with self._module_localizers_lock:
            for module_id, module_zipfile in MODULE_REGISTRY.all_latest().items():
                if module_zipfile not in self._module_localizers:
                    self._supported_modules[module_id] = module_zipfile
                    self._module_localizers[
                        module_zipfile
                    ] = MessageLocalizer.for_module_zipfile(module_zipfile)

    def clear(self):
        self._supported_modules.clear()
        self._module_localizers.clear()
        self._app_localizer = MessageLocalizer.for_application()


MESSAGE_LOCALIZER_REGISTRY = MessageLocalizerRegistry()


def restore_tags(message: str, tag_mapping: _TagMapping) -> str:
    """Replace the HTML tags and attributes in a message.
    
    `tag_mapping` is a dict that for each tag name contains a new name `name` and new attributes `attrs`
    
    For each non-nested HTML tag found, searches `tag_mapping` for a replacement for its name and attributes.
    If found, replaces with the ones found.
    If not found, removes the tag but keeps the (escaped) contents.
    
    Nested HTML tags are removed, with their (escaped) contents kept
    
    Returns the new message
    """
    soup = BeautifulSoup(message, "html.parser")
    bad = []
    for child in soup.children:
        if child.name:  # i.e. child is a tag
            if child.name in tag_mapping:
                child.attrs = tag_mapping[child.name].get("attrs", {})
                child.name = tag_mapping[child.name]["tag"]
                child.string = "".join(child.strings)
            else:
                bad.append(child)
    for child in bad:
        child.string = escape("".join(child.strings))
        child.unwrap()
    return str(soup)


def icu_format_message(
    locale_id: str, message: str, arguments: _MessageArguments = {}
) -> str:
    """Substitute arguments into ICU-style message.
    You can have variable substitution, plurals, selects and nested messages.
    
    Raises `ICUError` in case of incorrectly formatted message.
    
    The arguments must be a dict
    """
    return MessageFormat(message, Locale.createFromName(locale_id)).format(
        list(arguments.keys()), [Formattable(x) for x in arguments.values()]
    )


def icu_format_html_message(
    locale_id: str,
    message: str,
    arguments: _MessageArguments = {},
    tags: _TagMapping = {},
) -> str:
    """Substitute arguments into ICU-style HTML message.
    You can have variable substitution, plurals, selects and nested messages.
    You can also replace HTML tag placeholders.
    
    Raises `ICUError` in case of incorrectly formatted message.
    """
    return MessageFormat(
        restore_tags(message, tags), Locale.createFromName(locale_id)
    ).format(
        list(arguments.keys()),
        [
            Formattable(escape(x) if isinstance(x, str) else x)
            for x in arguments.values()
        ],
    )
