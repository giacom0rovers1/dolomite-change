#!/usr/bin/env python3
"""
Quota dello zero termico sulle Tofane, 1950-2025, da ERA5 su livelli di pressione.

Lo zero termico e' la quota a cui la temperatura libera attraversa 0 degC: sopra
puo' nevicare, sotto piove. E' la variabile che traduce il riscaldamento in una
grandezza che chiunque capisce, e si confronta direttamente con le quote dei
luoghi del trekking: Falzarego 2105 m, Lagazuoi 2752 m, Tofana di Rozes 3225 m.

Metodo: per ogni istante si interpola linearmente in altezza geopotenziale fra i
due livelli di pressione che racchiudono l'attraversamento dello zero, partendo
dal basso. Se il profilo e' sotto zero gia' a 850 hPa lo zero termico e' sotto il
dominio; se e' sopra zero fino a 500 hPa e' sopra.

Uso:
    python scripts/zero_termico.py --giorni 2005-07-05 2005-07-08
    python scripts/zero_termico.py --trend
    python scripts/zero_termico.py --soglie
"""
from __future__ import annotations

import argparse
import csv
import statistics
import sys
from pathlib import Path

try:
    import numpy as np
    import xarray as xr
except ImportError:
    sys.exit("xarray/numpy mancanti:  conda activate tofane")

DATA = Path(__file__).resolve().parent.parent / "data" / "era5"
G = 9.80665

QUOTE = {
    "Passo Falzarego": 2105,
    "Rifugio Lagazuoi": 2752,
    "Tofana di Rozes": 3225,
}


def carica(pattern: str = "era5_plev_*.nc") -> xr.Dataset:
    """Concatena i blocchi lungo il tempo.

    Niente open_mfdataset: richiederebbe dask per pochi MB di dati. Si scartano
    le coordinate accessorie (`expver`, `number`) che differiscono fra blocchi e
    farebbero fallire la concatenazione.
    """
    files = sorted(DATA.glob(pattern))
    if not files:
        sys.exit(f"Nessun file '{pattern}' in {DATA}. "
                 f"Lancia prima download_era5.py plev")
    pezzi = []
    for f in files:
        d = xr.open_dataset(f)
        # I nomi delle coordinate cambiano fra le versioni del CDS.
        for vecchio, nuovo in (("valid_time", "time"), ("level", "pressure_level")):
            if vecchio in d.dims or vecchio in d.coords:
                d = d.rename({vecchio: nuovo})
        pezzi.append(d.drop_vars([c for c in ("expver", "number") if c in d.coords]))
    ds = xr.concat(pezzi, dim="time") if len(pezzi) > 1 else pezzi[0]
    return ds.sortby("time")


def quota_zero(ds: xr.Dataset) -> xr.DataArray:
    """Quota dello zero termico in metri, media sui punti griglia del dominio."""
    t = ds["t"].mean(dim=[d for d in ("latitude", "longitude") if d in ds.dims])
    z = ds["z"].mean(dim=[d for d in ("latitude", "longitude") if d in ds.dims]) / G

    # Ordina dal livello piu' basso (pressione alta) al piu' alto.
    p = ds["pressure_level"]
    ordine = np.argsort(-p.values)
    tv = t.isel(pressure_level=ordine).values          # (tempo, livello)
    zv = z.isel(pressure_level=ordine).values
    tc = tv - 273.15 if np.nanmax(tv) > 100 else tv    # K o degC a seconda del file

    out = np.full(tc.shape[0], np.nan)
    sotto = sopra = 0
    for i in range(tc.shape[0]):
        Ti, Zi = tc[i], zv[i]
        for k in range(len(Ti) - 1):
            if Ti[k] >= 0 > Ti[k + 1]:                 # attraversamento dal basso
                frazione = Ti[k] / (Ti[k] - Ti[k + 1])
                out[i] = Zi[k] + frazione * (Zi[k + 1] - Zi[k])
                break
        else:
            # Nessun attraversamento dentro il dominio: il valore e' censurato.
            if Ti[0] < 0:
                out[i], sotto = Zi[0], sotto + 1        # gia' sotto zero a 850 hPa
            else:
                out[i], sopra = Zi[-1], sopra + 1       # sopra zero fino a 500 hPa
    n = len(out)
    if sotto or sopra:
        print(f"  valori censurati: {sotto} sotto 850 hPa ({100 * sotto / n:.1f}%), "
              f"{sopra} sopra 500 hPa ({100 * sopra / n:.1f}%) — "
              f"su questi la quota vera e' rispettivamente piu' bassa e piu' alta")
    return xr.DataArray(out, coords={"time": ds["time"]}, dims="time")


def ols(xs, ys):
    """Pendenza, errore standard e t. (nan, nan, nan) se il trend non e' definito:
    meno di tre punti, ascisse tutte uguali, o residui esattamente nulli."""
    n = len(xs)
    if n < 3:
        return float("nan"), float("nan"), float("nan")
    mx, my = statistics.fmean(xs), statistics.fmean(ys)
    sxx = sum((x - mx) ** 2 for x in xs)
    if sxx == 0:
        return float("nan"), float("nan"), float("nan")
    b = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sxx
    a = my - b * mx
    res = [y - (a + b * x) for x, y in zip(xs, ys)]
    se = (sum(r * r for r in res) / (n - 2) / sxx) ** 0.5
    return b, se, (b / se if se > 0 else float("nan"))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--giorni", nargs="+", metavar="AAAA-MM-GG")
    ap.add_argument("--pattern", default="era5_plev_*.nc",
                    help="quali file usare in data/era5 (es. _lug2005_orario.nc)")
    ap.add_argument("--trend", action="store_true")
    ap.add_argument("--soglie", action="store_true")
    ap.add_argument("--serie", action="store_true",
                    help="serie annuale di media, 5o percentile e minimo estivi")
    # I fiocchi impiegano qualche centinaio di metri a fondere, quindi la quota
    # della neve al suolo sta sotto lo zero termico. 300 m e' il valore d'uso
    # nei bollettini alpini; con --scarto-neve 0 si torna allo zero termico puro.
    ap.add_argument("--scarto-neve", type=int, default=300, metavar="M",
                    help="quanto sotto lo zero termico arriva la neve (default 300 m)")
    # Il tratto ERA5 precedente al 1979 e' la "back extension", con incertezza
    # maggiore: --da 1979 serve a verificare che i trend non dipendano da quello.
    ap.add_argument("--csv", action="store_true",
                    help="esporta la serie annuale in data/risultati/")
    ap.add_argument("--da", type=int, default=None, metavar="ANNO")
    ap.add_argument("--a", dest="fino", type=int, default=None, metavar="ANNO")
    a = ap.parse_args()

    ds = carica(a.pattern)
    if a.da or a.fino:
        y = ds["time"].dt.year
        ds = ds.where((y >= (a.da or -9999)) & (y <= (a.fino or 9999)), drop=True)
    zt = quota_zero(ds).load()
    anni = zt["time"].dt.year.values
    mesi = zt["time"].dt.month.values
    print(f"ERA5 livelli di pressione: {zt.sizes['time']} istanti, "
          f"{anni.min()}-{anni.max()}, mesi {sorted(int(m) for m in set(mesi))}")

    if a.giorni:
        print("\nQuota dello zero termico nei giorni chiave (m s.l.m.)")
        for g in a.giorni:
            sel = zt.sel(time=g)
            print(f"\n{g}")
            for t, v in zip(sel["time"].values, sel.values):
                ora = str(t)[11:16]
                dove = [n for n, q in QUOTE.items() if v < q]
                nota = ("  sotto: " + ", ".join(dove)) if dove else ""
                print(f"   {ora} UTC   {v:6.0f} m{nota}")

    if a.trend:
        print("\nZero termico medio di LUGLIO, per decennio (m)")
        lug = zt.where(xr.DataArray(mesi == 7, dims="time"), drop=True)
        ya = lug["time"].dt.year.values
        per_anno = {y: float(lug.values[ya == y].mean()) for y in sorted(set(ya))}
        xs = list(per_anno); ys = [per_anno[y] for y in xs]
        b, se, t = ols([float(x) for x in xs], ys)
        print(f"  trend {b * 10:+.0f} m/decennio  (se {se * 10:.0f}, t={t:+.1f})"
              f"{'  [significativo]' if abs(t) > 2 else ''}")
        for lo in range(1950, 2030, 10):
            sel = [v for y, v in per_anno.items() if lo <= y <= lo + 9]
            if sel:
                print(f"    {lo}-{min(lo + 9, xs[-1])}: {statistics.fmean(sel):6.0f} m")

    if a.serie:
        # La media dice dov'e' lo zero termico di solito; il minimo dice fin dove
        # scendeva nel momento piu' freddo dell'estate, ed e' quello che decide se
        # in un posto puo' ancora nevicare. Il 5o percentile sta in mezzo ed e'
        # meno sensibile al singolo istante.
        print("\nZero termico estivo (giu-ago): dove sta di solito e dove arriva")
        estate = zt.where(xr.DataArray(np.isin(mesi, [6, 7, 8]), dims="time"),
                          drop=True)
        ya = estate["time"].dt.year.values
        v = estate.values
        stat = {
            "media": lambda x: float(np.mean(x)),
            "p5": lambda x: float(np.percentile(x, 5)),
            "minimo": lambda x: float(np.min(x)),
        }
        anni_u = sorted(set(int(y) for y in ya))
        serie = {k: {y: f(v[ya == y]) for y in anni_u} for k, f in stat.items()}
        for k, per in serie.items():
            xs = [float(y) for y in anni_u]
            b, se, t = ols(xs, [per[y] for y in anni_u])
            d70 = statistics.fmean([per[y] for y in anni_u if 1970 <= y <= 1979])
            d20 = statistics.fmean([per[y] for y in anni_u if y >= 2020])
            print(f"  {k:7s} anni 70: {d70:5.0f} m  ->  2020-25: {d20:5.0f} m"
                  f"   trend {b * 10:+4.0f} m/decennio (t={t:+.1f})")
            # Quali luoghi del trekking sono stati scavalcati fra le due epoche.
            passati = [n for n, q in QUOTE.items() if d70 < q <= d20]
            if passati:
                print(f"          ha superato: {', '.join(passati)}")

        if a.csv:
            out = Path(__file__).resolve().parent.parent / "data" / "risultati"
            out.mkdir(parents=True, exist_ok=True)
            dest = out / "zero_termico_estivo.csv"
            with dest.open("w", encoding="utf8", newline="") as fh:
                w = csv.writer(fh)
                w.writerow(["anno", "media_m", "p5_m", "minimo_m"])
                for y in anni_u:
                    w.writerow([y] + [f"{serie[k][y]:.0f}" for k in stat])
            print(f"\ncsv -> {dest}")

    if a.soglie:
        s = a.scarto_neve
        print(f"\nGiorni estivi (giu-ago) in cui poteva NEVICARE alle quote del trekking")
        print(f"(quota neve = zero termico - {s} m; un giorno conta se almeno un "
              f"istante scende sotto)")
        estate = zt.where(xr.DataArray(np.isin(mesi, [6, 7, 8]), dims="time"),
                          drop=True)
        gg = estate.resample(time="1D").min().dropna(dim="time")
        ya = gg["time"].dt.year.values
        serie: dict[str, dict[int, int]] = {}
        for nome, q in QUOTE.items():
            print(f"\n  {nome} ({q} m)")
            per_anno = {y: int(((gg.values[ya == y] - s) < q).sum())
                        for y in sorted(set(ya))}
            xs = list(per_anno); ys = [float(per_anno[y]) for y in xs]
            b, se, t = ols([float(x) for x in xs], ys)
            print(f"    trend {b * 10:+.2f} giorni/decennio (t={t:+.1f})")
            for lo in range(1950, 2030, 10):
                sel = [v for y, v in per_anno.items() if lo <= y <= lo + 9]
                if sel:
                    print(f"      {lo}-{min(lo + 9, xs[-1])}: "
                          f"{statistics.fmean(sel):5.1f} giorni/estate")
            serie[nome] = per_anno

        if a.csv:
            out = Path(__file__).resolve().parent.parent / "data" / "risultati"
            out.mkdir(parents=True, exist_ok=True)
            dest = out / "giorni_neve_possibile_per_quota.csv"
            intestazione = ["anno"] + [f"{n.replace(' ', '_')}_{q}m"
                                       for n, q in QUOTE.items()]
            anni_tutti = sorted({y for d in serie.values() for y in d})
            with dest.open("w", encoding="utf8", newline="") as fh:
                w = csv.writer(fh)
                w.writerow(intestazione)
                for y in anni_tutti:
                    w.writerow([y] + [serie[n].get(y, "") for n in QUOTE])
            print(f"\ncsv -> {dest}")


if __name__ == "__main__":
    main()
