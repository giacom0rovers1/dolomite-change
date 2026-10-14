#!/usr/bin/env python3
"""
Scarica ERA5-Land (e opzionalmente ERA5 su livelli di pressione) per il
riquadro Falzarego-Lagazuoi-Tofane, Cortina d'Ampezzo.

Serve un account CDS gratuito e un file ~/.cdsapirc:

    url: https://cds.climate.copernicus.eu/api
    key: <IL-TUO-TOKEN>

Il token si ottiene da https://cds.climate.copernicus.eu/profile dopo aver
accettato le licenze dei dataset "ERA5-Land hourly" e "ERA5 hourly pressure
levels". Senza accettazione la richiesta fallisce con HTTP 403.

Sottocomandi
------------
  land   ERA5-Land orario: T2m, precipitazione, neve (9 km) - il cavallo di
         battaglia per temperatura e neve al suolo.
  plev   ERA5 su livelli di pressione: T e geopotenziale, per ricostruire la
         quota dello zero termico (31 km, ma la quota dello zero termico e'
         una grandezza di scala sinottica e regge bene la risoluzione).

Esempi
------
  python scripts/download_era5.py land --years 1950 2025 --months 6 7 8 9
  python scripts/download_era5.py land --years 2005 2005 --months 7 8 --daily
  python scripts/download_era5.py plev --years 1950 2025 --months 6 7 8 9
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Riquadro [Nord, Ovest, Sud, Est]. Copre Bai de Dones, Cinque Torri, Averau,
# Passo Falzarego, Lagazuoi, Tofane, Cortina e il gruppo di Fanis.
AREA = [46.65, 11.85, 46.40, 12.25]

# Punti di interesse per l'estrazione delle serie (lat, lon, quota m).
POI = {
    "Passo_Falzarego":  (46.5192, 12.0086, 2105),
    "Rifugio_Lagazuoi": (46.5236, 12.0025, 2752),
    "Tofana_di_Rozes":  (46.5397, 12.0333, 3225),
    "Rifugio_Giussani": (46.5439, 12.0289, 2580),
    "Cinque_Torri":     (46.5069, 12.0300, 2137),
    "Bai_de_Dones":     (46.5064, 12.0000, 1889),
    "Cortina":          (46.5369, 12.1358, 1224),
}

OUT = Path(__file__).resolve().parent.parent / "data" / "era5"

LAND_VARS = [
    "2m_temperature",
    "total_precipitation",
    "snowfall",
    "snow_depth_water_equivalent",
    "snow_cover",
    "snow_depth",
    "2m_dewpoint_temperature",
]

PLEV_VARS = ["temperature", "geopotential"]
PLEVS = ["850", "800", "750", "700", "650", "600", "550", "500"]


def _client():
    try:
        import cdsapi
    except ImportError:
        sys.exit("cdsapi non installato:  conda activate tofane")
    rc = Path.home() / ".cdsapirc"
    if not rc.exists():
        sys.exit(f"Manca {rc}. Vedi le istruzioni in testa a questo script.")
    return cdsapi.Client()


def _costs(legacy):
    """Client di stima costi, o None se non disponibile.

    Il CDS rifiuta con 403 'cost limits exceeded' le richieste sopra un tetto di
    dimensione (60000 al momento). Stimare prima evita di scoprirlo a valle di
    una coda, e permette di dimensionare i blocchi da soli.
    """
    try:
        import ecmwf.datastores as ed
        return ed.Client(url=legacy.url, key=legacy.key)
    except Exception:
        return None


def blocchi_ammessi(cc, collection: str, richiesta: dict, anni: list[int],
                    massimo: int = 10) -> list[list[int]]:
    """Spezza `anni` nei blocchi piu' grandi che stanno sotto il limite di costo."""
    if cc is None:
        return [[y] for y in anni]                    # senza stima, una alla volta

    def sta(blocco: list[int]) -> bool:
        try:
            e = cc.estimate_costs(collection,
                                  richiesta | {"year": [str(y) for y in blocco]})
            return e["cost"] <= e["limit"]
        except Exception:
            return len(blocco) == 1

    # Quanti anni ci stanno: la dimensione e' lineare negli anni, basta cercarlo una volta.
    n = 1
    while n < min(massimo, len(anni)) and sta(anni[:n + 1]):
        n += 1
    print(f"  blocchi da {n} anno/i per richiesta")
    return [anni[i:i + n] for i in range(0, len(anni), n)]


def _hours(daily: bool) -> list[str]:
    """Tutte le 24 ore se serve il ciclo diurno, altrimenti 6 istanti/giorno.

    Per medie mensili e anomalie stagionali 4 istanti bastano e riducono di
    ~4x il volume; per ricostruire Tmin/Tmax giornaliere servono tutte le ore.
    """
    step = 1 if daily else 4
    return [f"{h:02d}:00" for h in range(0, 24, step)]


def fetch_land(c, year: int, months: list[int], daily: bool) -> Path:
    OUT.mkdir(parents=True, exist_ok=True)
    tag = "hourly" if daily else "6h"
    dest = OUT / f"era5land_{tag}_{year}_{months[0]:02d}-{months[-1]:02d}.nc"
    if dest.exists():
        print(f"  [skip] {dest.name}")
        return dest
    print(f"  -> {dest.name}")
    c.retrieve(
        "reanalysis-era5-land",
        {
            "variable": LAND_VARS,
            "year": str(year),
            "month": [f"{m:02d}" for m in months],
            "day": [f"{d:02d}" for d in range(1, 32)],
            "time": _hours(daily),
            "area": AREA,
            "data_format": "netcdf",
            "download_format": "unarchived",
        },
        str(dest),
    )
    return dest


PLEV_COLL = "reanalysis-era5-pressure-levels"


def plev_request(months: list[int], times: list[int]) -> dict:
    """Parte della richiesta indipendente dagli anni (serve anche alla stima)."""
    return {
        "product_type": ["reanalysis"],
        "variable": PLEV_VARS,
        "pressure_level": PLEVS,
        "month": [f"{m:02d}" for m in months],
        "day": [f"{d:02d}" for d in range(1, 32)],
        "time": [f"{h:02d}:00" for h in times],
        "area": AREA,
        "data_format": "netcdf",
        "download_format": "unarchived",
    }


def fetch_plev(c, years: list[int], months: list[int],
               times: list[int]) -> Path:
    OUT.mkdir(parents=True, exist_ok=True)
    dest = OUT / (f"era5_plev_{years[0]}-{years[-1]}"
                  f"_{months[0]:02d}-{months[-1]:02d}.nc")
    if dest.exists():
        print(f"  [skip] {dest.name}")
        return dest
    print(f"  -> {dest.name}")
    c.retrieve(PLEV_COLL,
               plev_request(months, times) | {"year": [str(y) for y in years]},
               str(dest))
    return dest


def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("what", choices=["land", "plev"])
    ap.add_argument("--years", type=int, nargs=2, default=[1950, 2025],
                    metavar=("Y0", "Y1"))
    ap.add_argument("--months", type=int, nargs="+", default=[6, 7, 8, 9])
    ap.add_argument("--daily", action="store_true",
                    help="scarica tutte le 24 ore (serve per Tmin/Tmax giornaliere)")
    ap.add_argument("--times", type=int, nargs="+", default=[0, 6, 12, 18],
                    help="ore UTC per plev; meno ore = piu' anni per richiesta")
    args = ap.parse_args()

    c = _client()
    y0, y1 = args.years
    print(f"{args.what}: {y0}-{y1}, mesi {args.months}, area {AREA}")

    if args.what == "plev":
        cc = _costs(c)
        anni = list(range(y0, y1 + 1))
        for block in blocchi_ammessi(cc, PLEV_COLL,
                                     plev_request(args.months, args.times), anni):
            print(f"[{block[0]}-{block[-1]}]")
            try:
                fetch_plev(c, block, args.months, args.times)
            except Exception as exc:
                body = getattr(getattr(exc, "response", None), "text", "")
                print(f"  !! {block[0]}-{block[-1]}: {exc}{'  | ' + body[:200] if body else ''}")
        return

    for year in range(y0, y1 + 1):
        print(f"[{year}]")
        try:
            fetch_land(c, year, args.months, args.daily)
        except Exception as exc:                       # una richiesta fallita
            print(f"  !! {year}: {exc}")               # non deve fermare il resto


if __name__ == "__main__":
    main()
