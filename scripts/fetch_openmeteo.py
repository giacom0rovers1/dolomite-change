#!/usr/bin/env python3
"""
Serie giornaliere ERA5-Land dai POI del trekking, via archivio Open-Meteo.

Open-Meteo ridistribuisce ERA5 / ERA5-Land dal 1940 a oggi senza chiave API,
applicando una correzione di quota basata su un DEM ad alta risoluzione: utile
in Dolomiti, dove la cella ERA5-Land da 9 km appiattisce 1500 m di dislivello.
La correzione va comunque verificata contro le stazioni ARPAV (comando
`validate`), perche' la downscalatura corregge la temperatura ma non
ricostruisce l'orografia reale.

Sottocomandi
------------
  fetch     scarica e mette in cache le serie giornaliere di un POI
  hunt      cerca gli episodi di neve estivi in un anno (per datare il trekking)
  validate  confronta le medie mensili ERA5-Land con quelle ARPAV osservate

Esempi
------
  python scripts/fetch_openmeteo.py hunt --year 2005
  python scripts/fetch_openmeteo.py fetch --poi Passo_Falzarego --from 1950 --to 2025
  python scripts/fetch_openmeteo.py validate --poi Passo_Falzarego
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from pathlib import Path

try:
    import requests
except ImportError:
    sys.exit("requests non installato:  conda activate tofane")

sys.path.insert(0, str(Path(__file__).resolve().parent))
from parse_arpav import CSV_DIR, find_param, parse_station  # noqa: E402

API = "https://archive-api.open-meteo.com/v1/archive"
CACHE = Path(__file__).resolve().parent.parent / "data" / "openmeteo"

# (lat, lon, quota reale in m). Le quote servono per la correzione di Open-Meteo
# e per il confronto con le stazioni.
POI = {
    "Passo_Falzarego":  (46.5192, 12.0086, 2105),
    "Rifugio_Lagazuoi": (46.5236, 12.0025, 2752),
    "Tofana_di_Rozes":  (46.5397, 12.0333, 3225),
    "Rifugio_Giussani": (46.5439, 12.0289, 2580),
    "Rifugio_Scoiattoli": (46.5117, 12.0300, 2255),
    "Cinque_Torri":     (46.5069, 12.0300, 2137),
    "Bai_de_Dones":     (46.5064, 12.0000, 1889),
    "Cortina":          (46.5369, 12.1358, 1224),
    "Faloria":          (46.5253, 12.1622, 2235),
}

DAILY = [
    "temperature_2m_mean", "temperature_2m_max", "temperature_2m_min",
    "precipitation_sum", "rain_sum", "snowfall_sum",
]


def _chunk(poi: str, y0: int, y1: int, model: str, refresh: bool) -> dict:
    """Un blocco di anni, con cache su file e retry sul rate limit di Open-Meteo."""
    lat, lon, elev = POI[poi]
    dest = CACHE / f"_chunk_{poi}_{model}_{y0}-{y1}.json"
    if dest.exists() and not refresh:
        return json.loads(dest.read_text())

    params = {
        "latitude": lat, "longitude": lon, "elevation": elev,
        "start_date": f"{y0}-01-01", "end_date": f"{y1}-12-31",
        "daily": ",".join(DAILY), "models": model, "timezone": "UTC",
    }
    for attempt in range(6):
        print(f"  {poi} {model} {y0}-{y1} ...", flush=True)
        r = requests.get(API, params=params, timeout=300)
        if r.status_code == 200:
            j = r.json()
            dest.write_text(json.dumps(j))
            return j
        if r.status_code == 429:
            wait = 65 * (attempt + 1)      # il limite di Open-Meteo e' al minuto
            print(f"    rate limit, attendo {wait}s", flush=True)
            time.sleep(wait)
            continue
        raise SystemExit(f"Open-Meteo {r.status_code}: {r.text[:300]}")
    raise SystemExit("Open-Meteo: rate limit persistente, riprova piu' tardi.")


def fetch(poi: str, y0: int, y1: int, model: str = "era5_land",
          refresh: bool = False) -> dict:
    """Serie giornaliera per un POI. Ogni decennio e' messo in cache a parte,
    cosi' un'interruzione non costringe a riscaricare tutto."""
    CACHE.mkdir(parents=True, exist_ok=True)
    out: dict[str, list] = {"time": []} | {v: [] for v in DAILY}
    meta: dict = {}
    for c0 in range(y0, y1 + 1, 10):
        j = _chunk(poi, c0, min(c0 + 9, y1), model, refresh)
        meta = {k: j.get(k) for k in
                ("latitude", "longitude", "elevation", "utc_offset_seconds")}
        for k in out:
            out[k].extend(j["daily"][k])
        time.sleep(12)                     # sotto il limite al minuto
    return {"poi": poi, "model": model, "quota_richiesta_m": POI[poi][2],
            "meta": meta, "daily": out}


def _rows(d: dict):
    """Itera (data, tmean, tmax, tmin, prec, rain, snow).

    Richiede solo la terna di temperatura: ERA5-Land nell'archivio Open-Meteo
    non serve la precipitazione, che resta None e va gestita dal chiamante.
    """
    dd = d["daily"]
    for i, t in enumerate(dd["time"]):
        vals = [dd[v][i] for v in DAILY]
        if any(v is None for v in vals[:3]):
            continue
        yield (t, *vals)


def hunt(year: int, poi: str, model: str = "era5_land") -> None:
    """Elenca gli episodi di neve estivi: serve a datare la settimana del trek."""
    d = fetch(poi, year, year, model)
    print(f"\nEpisodi di neve e giorni freddi — {poi} "
          f"({d['quota_richiesta_m']} m), {year}")
    print(f"{'data':<12}{'Tmed':>7}{'Tmin':>7}{'Tmax':>7}"
          f"{'prec':>8}{'neve':>8}")
    hits = 0
    for t, tmean, tmax, tmin, prec, rain, snow in _rows(d):
        month = int(t[5:7])
        if month not in (6, 7, 8, 9):
            continue
        snow, prec = snow or 0.0, prec or 0.0
        if snow > 0 or tmin <= 0 or prec >= 25:
            flag = "  NEVE" if snow > 0 else ("  gelo" if tmin <= 0 else "  pioggia")
            print(f"{t:<12}{tmean:>7.1f}{tmin:>7.1f}{tmax:>7.1f}"
                  f"{prec:>8.1f}{snow:>8.1f}{flag}")
            hits += 1
    if not hits:
        print("  nessun episodio.")


def validate(poi: str, station: str, model: str = "era5_land") -> None:
    """Medie mensili ERA5-Land vs ARPAV osservato, stesso punto, 1994-2024."""
    d = fetch(poi, 1994, 2024, model)
    monthly: dict[tuple[int, int], list[float]] = {}
    for t, tmean, *_ in _rows(d):
        monthly.setdefault((int(t[:4]), int(t[5:7])), []).append(tmean)

    st = parse_station(CSV_DIR / f"{station}.csv")
    obs = st["data"][find_param(st["data"], "media delle medie")]

    print(f"\nValidazione {poi} (ERA5-Land, quota modello "
          f"{d['meta'].get('elevation')} m) vs {st['meta']['nome']} "
          f"({st['meta']['quota_m']} m osservato)")
    print(f"{'mese':<6}{'ERA5L':>8}{'ARPAV':>8}{'bias':>8}{'n':>5}")
    allbias = []
    for m in range(1, 13):
        pairs = [(statistics.fmean(monthly[(y, m)]), obs[y][m - 1])
                 for y in sorted(obs)
                 if (y, m) in monthly and obs[y][m - 1] is not None]
        if len(pairs) < 5:
            continue
        e = statistics.fmean(p[0] for p in pairs)
        o = statistics.fmean(p[1] for p in pairs)
        allbias += [a - b for a, b in pairs]
        print(f"{m:<6}{e:>8.1f}{o:>8.1f}{e - o:>+8.1f}{len(pairs):>5}")
    if allbias:
        print(f"\nbias medio annuo: {statistics.fmean(allbias):+.2f} degC  "
              f"(sd {statistics.stdev(allbias):.2f})")
        print("Un bias sistematico si sottrae; conta che sia stabile nel tempo,\n"
              "perche' le anomalie e i trend restano validi anche con bias.")


def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    # ERA5-Land (9 km) ha la temperatura ma non la precipitazione nell'archivio
    # Open-Meteo; per neve e pioggia serve ERA5 (31 km).
    for p in (sub.add_parser("fetch"), sub.add_parser("hunt"),
              sub.add_parser("validate")):
        p.add_argument("--poi", default="Passo_Falzarego", choices=sorted(POI))
        p.add_argument("--model", default="era5_land",
                       choices=["era5_land", "era5"])

    f, h, v = sub.choices["fetch"], sub.choices["hunt"], sub.choices["validate"]
    f.add_argument("--from", dest="y0", type=int, default=1950)
    f.add_argument("--to", dest="y1", type=int, default=2025)
    f.add_argument("--refresh", action="store_true")
    h.add_argument("--year", type=int, default=2005)
    v.add_argument("--station", default="Passo_Falzarego")

    a = ap.parse_args()
    if a.cmd == "fetch":
        fetch(a.poi, a.y0, a.y1, a.model, refresh=a.refresh)
    elif a.cmd == "hunt":
        hunt(a.year, a.poi, a.model)
    else:
        validate(a.poi, a.station, a.model)


if __name__ == "__main__":
    main()
