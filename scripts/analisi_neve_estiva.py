#!/usr/bin/env python3
"""
Quanto e' diventata rara una nevicata di luglio sulle Tofane?

Statistiche annuali 1950-2025 da ERA5 (via archivio Open-Meteo) nei punti del
trekking: giorni di neve estiva, giorni di gelo, temperatura media estiva.
Il senso e' separare l'aneddoto dal trend: la settimana del luglio 2005 fu
davvero eccezionale, ma la domanda vera e' come si e' spostata la
distribuzione da cui quell'episodio e' stato estratto.

Uso:
    python scripts/analisi_neve_estiva.py --poi Passo_Falzarego Rifugio_Giussani
    python scripts/analisi_neve_estiva.py --poi Passo_Falzarego --csv
"""
from __future__ import annotations

import argparse
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fetch_openmeteo import POI, _rows, fetch  # noqa: E402

OUT = Path(__file__).resolve().parent.parent / "data" / "risultati"


def ols(xs: list[float], ys: list[float]) -> tuple[float, float, float]:
    """Regressione lineare: restituisce (pendenza, errore standard, t)."""
    n = len(xs)
    mx, my = statistics.fmean(xs), statistics.fmean(ys)
    sxx = sum((x - mx) ** 2 for x in xs)
    b = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sxx
    a = my - b * mx
    res = [y - (a + b * x) for x, y in zip(xs, ys)]
    se = (sum(r * r for r in res) / (n - 2) / sxx) ** 0.5
    return b, se, b / se


def stats_per_anno(poi: str, y0: int, y1: int) -> dict[int, dict]:
    """Aggrega le serie giornaliere ERA5 in indici estivi per anno."""
    d = fetch(poi, y0, y1, model="era5")
    acc: dict[int, dict] = {}
    for t, tmean, tmax, tmin, prec, rain, snow in _rows(d):
        year, month = int(t[:4]), int(t[5:7])
        if month not in (6, 7, 8):
            continue
        a = acc.setdefault(year, {"tmean": [], "neve_gg": 0, "neve_cm": 0.0,
                                  "gelo_gg": 0, "neve_lug_gg": 0})
        a["tmean"].append(tmean)
        if snow > 0:
            a["neve_gg"] += 1
            a["neve_cm"] += snow
            if month == 7:
                a["neve_lug_gg"] += 1
        if tmin <= 0:
            a["gelo_gg"] += 1
    # Scarta gli anni incompleti (ERA5 copre giugno-agosto per intero dal 1940).
    return {y: a for y, a in acc.items() if len(a["tmean"]) >= 88}


def report(poi: str, y0: int, y1: int, want_csv: bool) -> None:
    st = stats_per_anno(poi, y0, y1)
    years = sorted(st)
    quota = POI[poi][2]
    print(f"\n{'=' * 74}\n{poi}  —  {quota} m  —  ERA5, estati {years[0]}-{years[-1]}"
          f"\n{'=' * 74}")

    metriche = [
        ("T media estiva (degC)",      lambda a: statistics.fmean(a["tmean"]), "{:+.2f} degC/dec"),
        ("giorni di neve GIU-AGO",     lambda a: a["neve_gg"],                 "{:+.2f} gg/dec"),
        ("giorni di neve in LUGLIO",   lambda a: a["neve_lug_gg"],             "{:+.2f} gg/dec"),
        ("neve totale GIU-AGO (cm)",   lambda a: a["neve_cm"],                 "{:+.2f} cm/dec"),
        ("giorni di gelo GIU-AGO",     lambda a: a["gelo_gg"],                 "{:+.2f} gg/dec"),
    ]

    for nome, f, fmt in metriche:
        vals = [f(st[y]) for y in years]
        b, se, t = ols([float(y) for y in years], vals)
        print(f"\n{nome}")
        print(f"  trend {fmt.format(b * 10)}  (se {se * 10:.2f}, t={t:+.1f})"
              f"{'   [significativo al 5%]' if abs(t) > 2.0 else '   [non significativo]'}")
        for lo in range(1950, 2030, 10):
            hi = min(lo + 9, years[-1])
            sel = [f(st[y]) for y in years if lo <= y <= hi]
            if sel:
                print(f"    {lo}-{hi}: {statistics.fmean(sel):7.2f}   (n={len(sel)})")

    # Il 2005 nel suo contesto: e' l'episodio che il video racconta.
    if 2005 in st:
        print(f"\n--- 2005 nel contesto ---")
        for nome, f, _ in metriche:
            vals = sorted(f(st[y]) for y in years)
            v = f(st[2005])
            rank = vals.index(v) + 1
            print(f"  {nome:<28} {v:8.2f}   rango {rank}/{len(vals)} "
                  f"(1 = piu' basso)")

    if want_csv:
        OUT.mkdir(parents=True, exist_ok=True)
        dest = OUT / f"neve_estiva_{poi}.csv"
        with dest.open("w", encoding="utf8") as fh:
            fh.write("anno,t_media_jja,neve_gg_jja,neve_gg_lug,neve_cm_jja,gelo_gg_jja\n")
            for y in years:
                a = st[y]
                fh.write(f"{y},{statistics.fmean(a['tmean']):.2f},{a['neve_gg']},"
                         f"{a['neve_lug_gg']},{a['neve_cm']:.1f},{a['gelo_gg']}\n")
        print(f"\ncsv -> {dest}")


def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--poi", nargs="+", default=["Passo_Falzarego"],
                    choices=sorted(POI))
    ap.add_argument("--from", dest="y0", type=int, default=1950)
    ap.add_argument("--to", dest="y1", type=int, default=2025)
    ap.add_argument("--csv", action="store_true")
    a = ap.parse_args()
    for poi in a.poi:
        report(poi, a.y0, a.y1, a.csv)


if __name__ == "__main__":
    main()
