#!/usr/bin/env python3
"""
Diario meteo del trekking, 3-9 luglio 2005, giorno per giorno.

Itinerario confermato da Giacomo: partenza domenica 3 luglio, sei notti (due al
rifugio Scoiattoli, due al Lagazuoi, due al Giussani), discesa a Cortina il 9.
La temperatura viene letta alla quota dove il gruppo si trovava quel giorno;
precipitazione e neve vengono dalla cella ERA5 (~31 km) e sono quindi le stesse
per tutti i punti - vanno raccontate come "in zona", non come dato di quota.

Uso:
    python scripts/diario_2005.py
    python scripts/diario_2005.py --md      # tabella markdown
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fetch_openmeteo import POI, fetch  # noqa: E402

# (data, giorno, dove si stava, POI di riferimento, cosa successe)
ITINERARIO = [
    ("2005-07-03", 1, "Bai de Dones -> rif. Scoiattoli", "Rifugio_Scoiattoli",
     "partenza, zaini pieni"),
    ("2005-07-04", 2, "Averau, rientro agli Scoiattoli", "Rifugio_Scoiattoli",
     "salita all'Averau"),
    ("2005-07-05", 3, "Scoiattoli -> Falzarego -> Lagazuoi", "Rifugio_Lagazuoi",
     "diluvio al passo, neve in salita, funivia"),
    ("2005-07-06", 4, "Lagazuoi, Kaiserjaeger e gallerie", "Rifugio_Lagazuoi",
     "ferrate e gallerie della Grande Guerra"),
    ("2005-07-07", 5, "Lagazuoi -> rif. Giussani", "Rifugio_Giussani",
     "trasferimento sotto la pioggia"),
    ("2005-07-08", 6, "Giussani, Tofana annullata", "Rifugio_Giussani",
     "risveglio sommersi dalla neve, battaglia a palle di neve"),
    ("2005-07-09", 7, "discesa a Cortina", "Cortina",
     "fine del trekking, rientro a Ferrara"),
]


def carica() -> dict[str, dict]:
    """Serie ERA5 di luglio 2005 per ogni POI toccato dall'itinerario."""
    per_poi = {}
    for poi in {p for _, _, _, p, _ in ITINERARIO}:
        d = fetch(poi, 2005, 2005, model="era5")
        dd = d["daily"]
        per_poi[poi] = {
            t: {
                "tmax": dd["temperature_2m_max"][i],
                "tmin": dd["temperature_2m_min"][i],
                "prec": dd["precipitation_sum"][i],
                "neve": dd["snowfall_sum"][i],
            }
            for i, t in enumerate(dd["time"])
        }
    return per_poi


HOURLY = ["temperature_2m", "precipitation", "rain", "snowfall",
          "dew_point_2m", "relative_humidity_2m", "wind_speed_10m",
          "soil_temperature_0_to_7cm"]


def ore(giorno: str, span: int = 1) -> None:
    """Andamento orario attorno a un giorno, alla quota di quel giorno.

    Serve per i dettagli che la media giornaliera nasconde: a che ora ha
    piovuto, a che ora la temperatura ha attraversato lo zero, quando il suolo
    si e' raffreddato abbastanza da gelare la pioggia gia' caduta.
    """
    import datetime as dt

    import requests

    match = [r for r in ITINERARIO if r[0] == giorno]
    if not match:
        raise SystemExit(f"{giorno} non e' nell'itinerario.")
    _, g, dove, poi, nota = match[0]
    lat, lon, quota = POI[poi]

    d0 = dt.date.fromisoformat(giorno)
    r = requests.get(
        "https://archive-api.open-meteo.com/v1/archive",
        params={"latitude": lat, "longitude": lon, "elevation": quota,
                "start_date": str(d0 - dt.timedelta(days=span - 1)),
                "end_date": str(d0 + dt.timedelta(days=span)),
                "hourly": ",".join(HOURLY), "models": "era5",
                "timezone": "Europe/Rome"},
        timeout=180)
    if r.status_code != 200:
        raise SystemExit(f"Open-Meteo {r.status_code}: {r.text[:200]}")
    h = r.json()["hourly"]

    print(f"\nORARIO — giorno {g}, {giorno}: {dove}")
    print(f"{poi}, {quota} m — {nota}")
    print("ora locale (Europe/Rome), ERA5 corretto in quota\n")
    print(f"{'ora':<17}{'T2m':>7}{'Trug':>7}{'suolo':>7}"
          f"{'pioggia':>9}{'neve':>7}{'vento':>7}")
    prev = None
    for i, t in enumerate(h["time"]):
        v = {k: h[k][i] for k in HOURLY}
        if v["temperature_2m"] is None:
            continue
        T = v["temperature_2m"]
        # Segnala l'attraversamento dello zero: e' il momento del gelo.
        cross = ""
        if prev is not None and (prev > 0) != (T > 0):
            cross = "   <<< ATTRAVERSA LO ZERO"
        prev = T
        bagnato = "  pioggia" if (v["rain"] or 0) > 0 else ""
        nevica = "  NEVE" if (v["snowfall"] or 0) > 0 else ""
        print(f"{t.replace('T', '  '):<17}{T:>7.1f}{v['dew_point_2m']:>7.1f}"
              f"{v['soil_temperature_0_to_7cm']:>7.1f}"
              f"{(v['rain'] or 0):>9.1f}{(v['snowfall'] or 0):>7.1f}"
              f"{v['wind_speed_10m']:>7.1f}{bagnato}{nevica}{cross}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--md", action="store_true", help="output in markdown")
    ap.add_argument("--ore", metavar="AAAA-MM-GG",
                    help="andamento orario di un giorno dell'itinerario")
    args = ap.parse_args()

    if args.ore:
        ore(args.ore)
        return

    per_poi = carica()
    righe = []
    for data, giorno, dove, poi, nota in ITINERARIO:
        v = per_poi[poi][data]
        quota = POI[poi][2]
        righe.append((data, giorno, dove, quota, v, nota))

    if args.md:
        print("| giorno | data | dove | quota | T max | T min | prec. | **neve** |")
        print("|---|---|---|---:|---:|---:|---:|---:|")
        for data, g, dove, q, v, _ in righe:
            neve = f"**{v['neve']:.1f} cm**" if v["neve"] else "—"
            gg, mm = data[8:10], data[5:7]
            print(f"| {g} | {gg}/{mm} | {dove} | {q} m | {v['tmax']:.1f} °C | "
                  f"{v['tmin']:.1f} °C | {v['prec']:.1f} mm | {neve} |")
        print("\nT max e T min sono corrette alla quota indicata; precipitazione e "
              "neve vengono dalla cella ERA5 e valgono per la zona.")
        return

    print("\nDIARIO METEO — trekking CAI Alpinismo Giovanile, 3-9 luglio 2005")
    print("ERA5 (Copernicus/ECMWF), temperatura corretta alla quota del giorno\n")
    for data, g, dove, q, v, nota in righe:
        neve = f"   NEVE {v['neve']:.1f} cm" if v["neve"] else ""
        print(f"giorno {g} — {data}   {dove}  ({q} m)")
        print(f"           T {v['tmin']:+.1f} / {v['tmax']:+.1f} degC   "
              f"prec {v['prec']:5.1f} mm{neve}")
        print(f"           {nota}\n")

    tot_neve = sum(r[4]["neve"] for r in righe)
    notti_gelo = sum(1 for r in righe if r[4]["tmin"] <= 0)
    print(f"Totale settimana: {tot_neve:.1f} cm di neve, "
          f"{notti_gelo} notti con minima <= 0 degC.")


if __name__ == "__main__":
    main()
