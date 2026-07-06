"""§3.1 universe loading + ticker metadata (CODE_BLUEPRINT.md pipeline/universe.py)."""
from sqlalchemy import text
from sqlalchemy.engine import Engine

from app.config import Config


def load_universe(cfg: Config) -> list[str]:
    return cfg.get("universe")


def refresh_ticker_meta(engine: Engine, symbols: list[str], in_universe: bool = True) -> None:
    """Upsert symbol -> tickers row so prices/scan_results FKs resolve.

    Sector/industry enrichment via yfinance is best-effort: a lookup
    failure never blocks the scan, and never overwrites previously-known
    metadata with NULL -- COALESCE keeps the existing value on failure.
    """
    import yfinance as yf

    with engine.begin() as conn:
        for symbol in symbols:
            name = sector = industry = None
            try:
                info = yf.Ticker(symbol).info
                name = info.get("shortName")
                sector = info.get("sector")
                industry = info.get("industry")
            except Exception:
                pass
            conn.execute(
                text("""
                    INSERT INTO tickers (symbol, name, sector, industry, in_universe)
                    VALUES (:symbol, :name, :sector, :industry, :in_universe)
                    ON CONFLICT(symbol) DO UPDATE SET
                        name=COALESCE(excluded.name, tickers.name),
                        sector=COALESCE(excluded.sector, tickers.sector),
                        industry=COALESCE(excluded.industry, tickers.industry),
                        in_universe=excluded.in_universe
                """),
                {"symbol": symbol, "name": name, "sector": sector,
                 "industry": industry, "in_universe": int(in_universe)},
            )
