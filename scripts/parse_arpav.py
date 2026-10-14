#!/usr/bin/env python3
"""
Parser per i bollettini mensili pluriennali ARPAV (open data CC-BY 4.0).

Ogni CSV di stazione e' un concatenamento di blocchi, uno per parametro:

    Stazione <nome>
    Coordinata X <...> Gauss-Boaga
    Coordinata Y <...>
    Quota della stazione <q> m s.l.m.
    Parametro <nome parametro>
    Valori dal ... al ...
    Anno;GEN;...;DIC;Somma|Media
    1994;...;...

Restituisce una struttura {parametro: {anno: [12 valori mensili]}} piu' i
metadati di stazione, e converte le coordinate Gauss-Boaga Ovest (EPSG:3003)
in lat/lon WGS84 per l'estrazione dei pixel ERA5-Land.

Uso:
    python scripts/parse_arpav.py --station Passo_Falzarego --list
    python scripts/parse_arpav.py --station Passo_Falzarego \
        --param "Temperatura aria a 2m" --anomaly 2005 --months 7 8
"""
from __future__ import annotations

import argparse
import csv
import math
import re
import statistics
import sys
from pathlib import Path

CSV_DIR = Path(__file__).resolve().parent.parent / "data" / "arpav" / "csv"
MONTHS = ["GEN", "FEB", "MAR", "APR", "MAG", "GIU",
          "LUG", "AGO", "SET", "OTT", "NOV", "DIC"]


# --------------------------------------------------------------------------
# Gauss-Boaga (Monte Mario / Italy zone 1 "Ovest", EPSG:3003) -> WGS84
# --------------------------------------------------------------------------
def gauss_boaga_to_wgs84(x: float, y: float) -> tuple[float, float]:
    """Inverse transverse Mercator on Hayford 1909 + datum shift to WGS84.

    Accurate to ~1-2 m, largely sufficient per selezionare un pixel ERA5-Land
    da 9 km. Zona Ovest: falso est 1_500_000, meridiano centrale 9 deg E.
    """
    a, f = 6378388.0, 1.0 / 297.0                     # Hayford / International 1924
    e2 = 2 * f - f * f
    k0, fe, lon0 = 0.9996, 1_500_000.0, math.radians(9.0)

    x = (x - fe) / k0
    m = y / k0

    e1 = (1 - math.sqrt(1 - e2)) / (1 + math.sqrt(1 - e2))
    mu = m / (a * (1 - e2 / 4 - 3 * e2**2 / 64 - 5 * e2**3 / 256))
    phi1 = (mu
            + (3 * e1 / 2 - 27 * e1**3 / 32) * math.sin(2 * mu)
            + (21 * e1**2 / 16 - 55 * e1**4 / 32) * math.sin(4 * mu)
            + (151 * e1**3 / 96) * math.sin(6 * mu)
            + (1097 * e1**4 / 512) * math.sin(8 * mu))

    ep2 = e2 / (1 - e2)
    c1 = ep2 * math.cos(phi1) ** 2
    t1 = math.tan(phi1) ** 2
    n1 = a / math.sqrt(1 - e2 * math.sin(phi1) ** 2)
    r1 = a * (1 - e2) / (1 - e2 * math.sin(phi1) ** 2) ** 1.5
    d = x / n1

    lat = phi1 - (n1 * math.tan(phi1) / r1) * (
        d**2 / 2
        - (5 + 3 * t1 + 10 * c1 - 4 * c1**2 - 9 * ep2) * d**4 / 24
        + (61 + 90 * t1 + 298 * c1 + 45 * t1**2 - 252 * ep2 - 3 * c1**2) * d**6 / 720)
    lon = lon0 + (
        d
        - (1 + 2 * t1 + c1) * d**3 / 6
        + (5 - 2 * c1 + 28 * t1 - 3 * c1**2 + 8 * ep2 + 24 * t1**2) * d**5 / 120
    ) / math.cos(phi1)

    lat, lon = math.degrees(lat), math.degrees(lon)
    # Datum shift Roma40 -> WGS84, parametri medi per l'Italia nord-orientale.
    return lat - 0.00113, lon - 0.00147


# --------------------------------------------------------------------------
# Parsing
# --------------------------------------------------------------------------
def _num(tok: str) -> float | None:
    """Converte una cella; '>>' e' il codice ARPAV per dato non disponibile."""
    tok = tok.strip().replace(",", ".")
    if not tok or tok.startswith(">>"):
        return None
    try:
        return float(tok)
    except ValueError:
        return None


def parse_station(path: Path) -> dict:
    """Legge un CSV di stazione e restituisce metadati, serie per parametro e,
    per ogni parametro, i giorni assenti di ogni mese.

    I giorni assenti contano: ARPAV pubblica il valore mensile anche quando la
    stazione ha misurato pochi giorni (il luglio 2018 della Marmolada e' la media
    di un giorno solo). Chi calcola trend deve scartare i mesi incompleti.
    """
    with path.open(encoding="latin-1", newline="") as fh:
        rows = [r for r in csv.reader(fh, delimiter=";")]

    meta: dict = {"file": path.name}
    data: dict[str, dict[int, list[float | None]]] = {}
    assenti: dict[str, dict[int, list[int | None]]] = {}
    param: str | None = None
    # Ogni blocco-parametro e' seguito da una "Tabella dei giorni assenti" con
    # le stesse annate: va letta a parte, altrimenti sovrascrive le misure.
    skipping = False

    for row in rows:
        first = (row[0] if row else "").strip()

        if first.startswith("Tabella dei giorni assenti"):
            skipping = True
            continue

        if param and skipping and re.fullmatch(r"(19|20)\d{2}", first):
            assenti.setdefault(param, {})[int(first)] = [
                None if (v := _num(t)) is None else int(v) for t in row[1:13]]
            continue

        if first.startswith("Stazione "):
            meta.setdefault("nome", first[len("Stazione "):].strip())
        elif first.startswith("Coordinata X"):
            if (v := re.search(r"(\d[\d.]*)", first)):
                meta.setdefault("gb_x", float(v.group(1)))
        elif first.startswith("Coordinata Y"):
            if (v := re.search(r"(\d[\d.]*)", first)):
                meta.setdefault("gb_y", float(v.group(1)))
        elif first.startswith("Quota della stazione"):
            if (v := re.search(r"(\d+)", first)):
                meta.setdefault("quota_m", int(v.group(1)))
        elif first.startswith("Parametro "):
            param = first[len("Parametro "):].strip()
            skipping = False
            data.setdefault(param, {})
        elif param and not skipping and re.fullmatch(r"(19|20)\d{2}", first):
            data[param][int(first)] = [_num(t) for t in row[1:13]]

    if "gb_x" in meta and "gb_y" in meta:
        meta["lat"], meta["lon"] = gauss_boaga_to_wgs84(meta["gb_x"], meta["gb_y"])
    return {"meta": meta, "data": data, "assenti": assenti}


def find_param(data: dict, needle: str) -> str:
    """Match case-insensitive parziale sul nome del parametro."""
    hits = [k for k in data if needle.lower() in k.lower()]
    if not hits:
        raise SystemExit(
            f"Parametro '{needle}' non trovato. Disponibili:\n  "
            + "\n  ".join(sorted(data)))
    return hits[0]


# --------------------------------------------------------------------------
# Anomalie
# --------------------------------------------------------------------------
def anomaly(series: dict[int, list], year: int, months: list[int],
            ref: tuple[int, int]) -> list[dict]:
    """Anomalia di `year` rispetto alla climatologia `ref`, mese per mese."""
    out = []
    for m in months:
        idx = m - 1
        clim = [v[idx] for y, v in series.items()
                if ref[0] <= y <= ref[1] and v[idx] is not None]
        val = series.get(year, [None] * 12)[idx]
        if val is None or len(clim) < 5:
            out.append({"mese": MONTHS[idx], "valore": val, "n_clim": len(clim)})
            continue
        mean = statistics.fmean(clim)
        sd = statistics.stdev(clim)
        # Rango 1 = anno piu' freddo/basso del periodo di riferimento.
        pool = clim if ref[0] <= year <= ref[1] else clim + [val]
        rank = sorted(pool).index(val) + 1
        out.append({
            "mese": MONTHS[idx],
            "valore": val,
            "clim": mean,
            "sd": sd,
            "anom": val - mean,
            "z": (val - mean) / sd if sd else float("nan"),
            "rank": rank,
            "n_clim": len(clim),
            "min": min(clim),
            "max": max(clim),
        })
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--station", default="Passo_Falzarego",
                    help="prefisso del nome file, es. Passo_Falzarego")
    ap.add_argument("--param", default="Temperatura aria a 2m")
    ap.add_argument("--anomaly", type=int, metavar="YEAR")
    ap.add_argument("--months", type=int, nargs="+", default=[7, 8])
    ap.add_argument("--ref", type=int, nargs=2, default=[1994, 2024],
                    metavar=("Y0", "Y1"))
    ap.add_argument("--list", action="store_true",
                    help="elenca i parametri disponibili ed esce")
    ap.add_argument("--stations", action="store_true",
                    help="elenca le stazioni disponibili ed esce")
    args = ap.parse_args()

    if args.stations:
        for p in sorted(CSV_DIR.glob("*.csv")):
            print(p.stem)
        return

    matches = sorted(CSV_DIR.glob(f"{args.station}*.csv"))
    if not matches:
        raise SystemExit(f"Nessuna stazione '{args.station}*' in {CSV_DIR}")
    st = parse_station(matches[0])
    m = st["meta"]

    print(f"{m.get('nome')}  |  {m.get('quota_m')} m s.l.m.  |  "
          f"{m.get('lat', float('nan')):.4f} N, {m.get('lon', float('nan')):.4f} E")
    print(f"file: {m['file']}")

    if args.list:
        print("\nParametri disponibili:")
        for k, v in st["data"].items():
            yrs = sorted(v)
            span = f"{yrs[0]}-{yrs[-1]} ({len(yrs)} anni)" if yrs else "vuoto"
            print(f"  - {k}   [{span}]")
        return

    key = find_param(st["data"], args.param)
    series = st["data"][key]
    print(f"parametro: {key}\n")

    if args.anomaly:
        print(f"Anomalie {args.anomaly} vs climatologia {args.ref[0]}-{args.ref[1]}")
        print(f"{'mese':<5}{'val':>8}{'clim':>8}{'anom':>8}{'z':>7}"
              f"{'rank':>7}{'min':>8}{'max':>8}")
        for r in anomaly(series, args.anomaly, args.months, tuple(args.ref)):
            if "anom" not in r:
                print(f"{r['mese']:<5}{'n/d':>8}")
                continue
            print(f"{r['mese']:<5}{r['valore']:>8.1f}{r['clim']:>8.1f}"
                  f"{r['anom']:>+8.1f}{r['z']:>+7.2f}"
                  f"{r["rank"]:>4}/{r["n_clim"]:<3}{r['min']:>8.1f}{r['max']:>8.1f}")
    else:
        for y in sorted(series):
            vals = " ".join(f"{v:6.1f}" if v is not None else "   n/d"
                            for v in series[y])
            print(f"{y}  {vals}")


if __name__ == "__main__":
    main()
