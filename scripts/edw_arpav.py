#!/usr/bin/env python3
"""
Il riscaldamento estivo cresce con la quota? Test sull'intera rete ARPAV.

L'elevation-dependent warming (EDW) e' un fatto documentato in letteratura su
scala alpina e su finestre lunghe. La domanda qui e' piu' stretta: la rete ARPAV,
31 anni e circa 160 stazioni fra 0 e 2235 m, e' abbastanza per *misurarlo*?

Risposta breve: no, e va detto. Il gradiente che si vede scegliendo quattro
stazioni lungo un profilo di quota non sopravvive all'intera rete. Ne' sopravvive
la stazione piu' alta, Marmolada - Punta Rocca (3250 m): contando solo i mesi
misurati per intero le restano 7 estati su 31, e quelle 7 hanno salti di 2-3 °C
rispetto ai passi vicini.

Cio' che invece la rete dimostra benissimo e' l'unanimita': ogni singola stazione
del Veneto si sta scaldando d'estate, su qualunque finestra.

Un'estate conta solo se tutti e tre i mesi hanno al massimo MAX_ASSENTI giorni
senza dati: ARPAV pubblica il valore mensile anche quando i giorni misurati sono
pochissimi (vedi parse_arpav.parse_station).

Uso:
    python scripts/edw_arpav.py                              # ogni stazione sulla sua serie
    python scripts/edw_arpav.py --csv
    python scripts/edw_arpav.py --finestra 2005 2024 --csv   # tutte sugli stessi anni
"""
from __future__ import annotations

import argparse
import csv
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from parse_arpav import CSV_DIR, parse_station  # noqa: E402
from zero_termico import ols  # noqa: E402

MESI_ESTIVI = (6, 7, 8)
MIN_ESTATI = 20
# Piu' di 5 giorni assenti e il mese non e' piu' rappresentativo: e' la soglia
# della regola "3/5" dell'OMM, senza la parte sui giorni consecutivi, che con
# i soli totali mensili non si puo' verificare.
MAX_ASSENTI = 5
# Con una finestra fissa, quante estati incomplete puo' avere una stazione e
# restare dentro: 2 su 20 e' il 90 % di copertura. Esigerle tutte toglie un
# terzo della rete (basta un mese con 6 giorni assenti) e non cambia i numeri.
MAX_BUCHI = 2
# Sotto questa quota il segnale e' dominato da citta', irrigazione e dal
# recupero di radiazione della Pianura Padana: non e' terreno di confronto
# pulito con l'alta quota.
QUOTA_MONTAGNA = 500

# Le stazioni del profilo del trekking. La Marmolada non passa il filtro dei
# mesi completi, ma resta qui per il confronto.
PROFILO = ("Cortina d'Ampezzo - Gilardon", "Passo Falzarego", "Faloria",
           "Marmolada - Punta Rocca")


def estati(s: dict, param: str) -> dict[int, float]:
    """Media giugno-agosto degli anni con tutti e tre i mesi completi."""
    ass = s["assenti"].get(param, {})
    out = {}
    for y, v in sorted(s["data"][param].items()):
        a = ass.get(y, [0] * 12)
        if all(v[m - 1] is not None and (a[m - 1] or 0) <= MAX_ASSENTI
               for m in MESI_ESTIVI):
            out[y] = statistics.fmean(v[m - 1] for m in MESI_ESTIVI)
    return out


def stazioni(finestra: tuple[int, int] | None = None) -> list[dict]:
    """Trend estivo di ogni stazione.

    Senza finestra: le stazioni con almeno MIN_ESTATI estati complete, ognuna
    sulla sua serie. Con finestra (a, b): solo le stazioni a cui mancano al
    massimo MAX_BUCHI estati fra a e b, e il trend calcolato su quegli anni.
    """
    out = []
    for p in sorted(CSV_DIR.glob("*.csv")):
        s = parse_station(p)
        quota = s["meta"].get("quota_m")
        param = next((k for k in s["data"] if "media delle medie" in k.lower()), None)
        if quota is None or param is None:
            continue
        serie = estati(s, param)
        if finestra:
            anni = range(finestra[0], finestra[1] + 1)
            serie = {y: serie[y] for y in anni if y in serie}
            if len(anni) - len(serie) > MAX_BUCHI:
                continue
        elif len(serie) < MIN_ESTATI:
            continue
        b, se, t = ols([float(y) for y in serie], list(serie.values()))
        out.append({
            "nome": s["meta"]["nome"], "quota": quota, "n": len(serie),
            "primo": min(serie), "ultimo": max(serie),
            "trend": b * 10, "se": se * 10, "t": t,
            "tmedia": statistics.fmean(serie.values()),
        })
    return out


def gradiente(sel: list[dict]) -> tuple[float, float, float]:
    """Regressione del trend sulla quota: gradi/decennio per 1000 m di quota."""
    if len(sel) < 3:
        return float("nan"), float("nan"), float("nan")
    b, se, t = ols([float(x["quota"]) for x in sel], [x["trend"] for x in sel])
    return b * 1000, se * 1000, t


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--csv", action="store_true",
                    help="esporta la tabella per stazione in data/risultati/")
    ap.add_argument("--finestra", type=int, nargs=2, metavar=("DA", "A"),
                    help="calcola tutti i trend sugli stessi anni, es. 2005 2024")
    a = ap.parse_args()
    finestra = tuple(a.finestra) if a.finestra else None

    st = stazioni(finestra)
    tr = [x["trend"] for x in st]
    signif = [x for x in st if abs(x["t"]) > 2]
    if finestra:
        print(f"Stazioni ARPAV con le estati {finestra[0]}-{finestra[1]} complete "
              f"(al massimo {MAX_BUCHI} mancanti): {len(st)}")
    else:
        print(f"Stazioni ARPAV con almeno {MIN_ESTATI} estati complete: {len(st)}")
    print(f"(estate completa: giugno, luglio e agosto con al massimo {MAX_ASSENTI} "
          f"giorni assenti ciascuno)")
    print(f"Quote da {min(x['quota'] for x in st)} a {max(x['quota'] for x in st)} m\n")

    print("1. IL RISCALDAMENTO ESTIVO E' UNANIME")
    print(f"   trend positivo in {sum(1 for v in tr if v > 0)} stazioni su {len(st)}")
    print(f"   significativo (|t|>2) in {len(signif)}")
    q = statistics.quantiles(tr, n=4)
    print(f"   mediana {statistics.median(tr):+.2f} °C/decennio "
          f"(quartili {q[0]:+.2f} / {q[2]:+.2f}, "
          f"estremi {min(tr):+.2f} / {max(tr):+.2f})")

    print("\n2. IL GRADIENTE CON LA QUOTA")
    prove = [
        ("tutte le stazioni", st),
        (f"solo quota >= {QUOTA_MONTAGNA} m", [x for x in st if x["quota"] >= QUOTA_MONTAGNA]),
        ("solo quota >= 1000 m", [x for x in st if x["quota"] >= 1000]),
    ]
    if not finestra:
        prove.append(("solo serie di almeno 28 estati", [x for x in st if x["n"] >= 28]))
    for etichetta, sel in prove:
        b, se, t = gradiente(sel)
        verdetto = "significativo" if abs(t) > 2 else "non significativo"
        print(f"   {etichetta:38s} n={len(sel):3d}  "
              f"{b:+.3f} °C/dec ogni 1000 m  (t={t:+.2f}, {verdetto})")

    if not finestra:
        print("\n   Perche' cambia segno: le serie corte partono piu' tardi, quindi")
        print("   coprono una finestra piu' recente e piu' calda.")
        for lo, hi in ((20, 24), (25, 27), (28, 30), (31, 31)):
            sel = [x for x in st if lo <= x["n"] <= hi]
            if sel:
                print(f"     {len(sel):3d} stazioni con {lo}-{hi} estati: primo anno mediano "
                      f"{statistics.median([x['primo'] for x in sel]):.0f}, "
                      f"trend medio {statistics.fmean([x['trend'] for x in sel]):+.2f}")

    print("\n3. LE STAZIONI DEL PROFILO DEL TREKKING")
    for nome in PROFILO:
        x = next((y for y in st if y["nome"] == nome), None)
        if x:
            print(f"   {x['nome']:32s} {x['quota']:5d} m  "
                  f"{x['trend']:+.2f} ± {x['se']:.2f} °C/dec  "
                  f"n={x['n']} ({x['primo']}-{x['ultimo']})")
        else:
            print(f"   {nome:32s} esclusa: troppe estati incomplete")

    print("\n4. TREND PER FASCIA DI QUOTA")
    fasce: dict[int, list[float]] = {}
    for x in st:
        fasce.setdefault(min((x["quota"] // 500) * 500, 3000), []).append(x["trend"])
    for k in sorted(fasce):
        v = fasce[k]
        print(f"   {k:4d}-{k + 499:4d} m  n={len(v):3d}  "
              f"media {statistics.fmean(v):+.2f}  mediana {statistics.median(v):+.2f}")

    print("\nCONCLUSIONE. La rete ARPAV dimostra che il Veneto si scalda d'estate")
    print("ovunque e senza eccezioni, ma non e' in grado di risolvere l'EDW: troppe")
    print("poche stazioni in quota, nessuna sopra i 2235 m con una serie utilizzabile,")
    print("e in pianura un forcing suo (aerosol in calo, uso del suolo) che spinge i")
    print("trend verso l'alto. L'EDW resta valido come risultato di letteratura,")
    print("non come misura ricavata da questi dati.")

    if a.csv:
        dest = Path(__file__).resolve().parent.parent / "data" / "risultati"
        dest.mkdir(parents=True, exist_ok=True)
        coda = f"_{finestra[0]}-{finestra[1]}" if finestra else ""
        f = dest / f"trend_estivo_stazioni_arpav{coda}.csv"
        with f.open("w", encoding="utf8", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["nome", "quota_m", "n_estati", "primo_anno", "ultimo_anno",
                        "trend_c_per_decennio", "se", "t", "t_media_estiva"])
            for x in sorted(st, key=lambda y: y["quota"]):
                w.writerow([x["nome"], x["quota"], x["n"], x["primo"], x["ultimo"],
                            f"{x['trend']:.4f}", f"{x['se']:.4f}", f"{x['t']:.2f}",
                            f"{x['tmedia']:.2f}"])
        print(f"\ncsv -> {f}")


if __name__ == "__main__":
    main()
