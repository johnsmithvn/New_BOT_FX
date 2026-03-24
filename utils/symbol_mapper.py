"""
utils/symbol_mapper.py

Map channel symbol aliases to broker symbols.
Validate mapping availability.
"""

from __future__ import annotations

# Default alias → broker symbol map.
# Extend via config or data file in future phases.
_DEFAULT_ALIASES: dict[str, str] = {
    # Metals
    "GOLD": "XAUUSD",
    "XAUUSD": "XAUUSD",
    "SILVER": "XAGUSD",
    "XAGUSD": "XAGUSD",
    # Major forex pairs
    "EURUSD": "EURUSD",
    "GBPUSD": "GBPUSD",
    "USDJPY": "USDJPY",
    "USDCHF": "USDCHF",
    "AUDUSD": "AUDUSD",
    "NZDUSD": "NZDUSD",
    "USDCAD": "USDCAD",
    # Cross pairs
    "EURJPY": "EURJPY",
    "GBPJPY": "GBPJPY",
    "EURGBP": "EURGBP",
    "AUDJPY": "AUDJPY",
    "CHFJPY": "CHFJPY",
    "CADJPY": "CADJPY",
    "EURAUD": "EURAUD",
    "GBPAUD": "GBPAUD",
    "EURNZD": "EURNZD",
    "GBPNZD": "GBPNZD",
    "AUDNZD": "AUDNZD",
    "AUDCAD": "AUDCAD",
    "GBPCAD": "GBPCAD",
    "EURCAD": "EURCAD",
    "NZDCAD": "NZDCAD",
    "NZDJPY": "NZDJPY",
    # Indices
    "US30": "US30",
    "US100": "US100",
    "US500": "US500",
    "NAS100": "NAS100",
    "NASDAQ": "NAS100",
    "DJ30": "US30",
    "SPX500": "US500",
    "DE30": "DE30",
    "GER40": "GER40",
    "UK100": "UK100",
    "JP225": "JP225",
    # Oil
    "USOIL": "USOIL",
    "UKOIL": "UKOIL",
    "WTI": "USOIL",
    "BRENT": "UKOIL",
    "CRUDEOIL": "USOIL",
    "CRUDE": "USOIL",
    # Crypto
    "BTCUSD": "BTCUSD",
    "ETHUSD": "ETHUSD",
    "BITCOIN": "BTCUSD",
    "ETHEREUM": "ETHUSD",
}


class SymbolMapper:
    """Resolve signal symbol aliases to broker-recognized symbols."""

    def __init__(
        self,
        custom_aliases: dict[str, str] | None = None,
        symbol_suffix: str = "",
    ) -> None:
        self._map: dict[str, str] = {**_DEFAULT_ALIASES}
        if custom_aliases:
            # custom overrides default
            self._map.update(
                {k.upper(): v.upper() for k, v in custom_aliases.items()}
            )
        self._suffix = symbol_suffix

    def resolve(self, alias: str) -> str | None:
        """Return broker symbol for a given alias, or None if unknown.

        If symbol_suffix is configured (e.g. 'm' for Exness), it is
        appended to the resolved symbol: XAUUSD → XAUUSDm.
        """
        base = self._map.get(alias.upper().strip())
        if base is None:
            return None
        return f"{base}{self._suffix}" if self._suffix else base

    def is_known(self, alias: str) -> bool:
        """Check if an alias is in the map."""
        return alias.upper().strip() in self._map

    @property
    def known_aliases(self) -> list[str]:
        """Return sorted list of all known aliases."""
        return sorted(self._map.keys())
