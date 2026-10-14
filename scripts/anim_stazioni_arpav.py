#!/usr/bin/env python3
"""
Animazione del film: vent'anni d'estate nelle stazioni ARPAV del Veneto
(analysis.ipynb, sezione 4c).

Ogni punto e' una stazione: in orizzontale il trend della temperatura media
estiva 2005-2024, in verticale la quota. I punti partono tutti dalla linea dello
zero ("nessun cambiamento") e scivolano verso destra fino al loro valore, dalla
pianura ai passi. Poi compaiono la mediana della rete e il Passo Falzarego, e
alla fine il conto: tutte le stazioni si sono scaldate.

La finestra e' quella dei nostri vent'anni, dall'estate del trekking all'ultima
in archivio, uguale per tutte le stazioni (scripts/edw_arpav.py --finestra).

Uso:
    python scripts/anim_stazioni_arpav.py              # -> video/stazioni_arpav.mp4
    python scripts/anim_stazioni_arpav.py --frame 12   # solo il fotogramma a 12 s
"""
from __future__ import annotations

import argparse
import csv
import statistics
from pathlib import Path

from anim_stile import (COL, RADICE, VIDEO, alpha, carica_font, esporta, figura,
                        intestazione, legenda, px, rampa, uscita)

FINESTRA = (2005, 2024)
CSV = (RADICE / "data" / "risultati"
       / f"trend_estivo_stazioni_arpav_{FINESTRA[0]}-{FINESTRA[1]}.csv")
OUT = VIDEO / "stazioni_arpav.mp4"

TESTI = {
    "titolo": "Vent’anni d’estate, stazione per stazione",
    "sottotitolo": "Tendenza della temperatura media estiva {a}–{b} nelle {n} "
                   "stazioni ARPAV del Veneto, per quota",
    "leg_punto": "una stazione",
    "leg_mediana": "mediana della rete",
    "fonte": "Dati: ARPAV, rete meteorologica del Veneto (CC BY 4.0) · "
             "trend lineare giugno–agosto, stazioni con almeno 18 estati "
             "complete su 20",
    "asse_x": "°C ogni dieci anni",
    "piu_freddo": "← più fresco",
    "piu_caldo": "più caldo →",
    "zero": "nessun cambiamento",
    "luogo": "Passo Falzarego",
    "conto": "{n} su {n}",
    "conta_sotto": "stazioni",
    "conto_sotto": "stazioni si sono scaldate",
    "mediana_sotto": "in media, ogni dieci anni",
}

# Secondi. "arrivo": (primo, ultimo) istante in cui una stazione parte dallo zero,
# dalla piu' bassa alla piu' alta; "scivola" e' quanto ci mette ad arrivare.
TEMPI = {
    "arrivo": (1.2, 3.8),
    "scivola": 1.3,
    "mediana": 5.6,
    "luogo": 7.2,
    "conto": 8.8,
    "fine": 14.0,
}

LUOGO = "Passo Falzarego"
XMIN, XMAX = -0.45, 1.6
YMAX = 2450


def leggi() -> list[dict]:
    return [dict(nome=r["nome"], quota=float(r["quota_m"]),
                 trend=float(r["trend_c_per_decennio"]))
            for r in csv.DictReader(CSV.open(encoding="utf8"))]


def cifra(v: float, segno: bool = True) -> str:
    """Due decimali con la virgola, come si scrive in italiano."""
    return f"{v:+.2f}".replace(".", ",") if segno else f"{v:.2f}".replace(".", ",")


def costruisci():
    st = sorted(leggi(), key=lambda x: x["quota"])
    n = len(st)
    med = statistics.median(x["trend"] for x in st)
    caldi = sum(x["trend"] > 0 for x in st)

    fig = figura()
    ax = fig.add_axes([0.105, 0.13, 0.62, 0.63], facecolor=COL["fondo"])
    ax.set_xlim(XMIN, XMAX)
    ax.set_ylim(-60, YMAX)
    for lato in ("top", "right", "left"):
        ax.spines[lato].set_visible(False)
    ax.spines["bottom"].set_color(COL["asse"])
    ax.spines["bottom"].set_linewidth(1.5)
    ax.set_xticks([0, 0.5, 1, 1.5], ["0", "+0,5", "+1", "+1,5"])
    ax.tick_params(axis="x", colors=COL["muto"], labelsize=px(24), length=0, pad=12)
    tacche = [0, 500, 1000, 1500, 2000]
    ax.set_yticks(tacche, [f"{q} m" if q == 2000 else f"{q}" for q in tacche])
    ax.tick_params(axis="y", colors=COL["muto"], labelsize=px(21), length=0, pad=10)
    griglia = [ax.axhline(q, color=COL["asse"], lw=1, zorder=0) for q in tacche[1:]]
    fisse = [ax.spines["bottom"]] + griglia + ax.get_xticklabels() + ax.get_yticklabels()
    fisse.append(fig.text(0.105 + 0.62, 0.065, TESTI["asse_x"], color=COL["muto"],
                          fontsize=px(21), ha="right", va="baseline"))

    # La linea dello zero e le due direzioni: si legge senza conoscere i trend
    fisse += [
        ax.axvline(0, color=COL["testo2"], lw=2, zorder=1),
        ax.text(0, YMAX, TESTI["zero"], color=COL["testo2"], fontsize=px(21),
                ha="center", va="bottom"),
        ax.text(-0.04, 2250, TESTI["piu_freddo"], color=COL["muto"], fontsize=px(21),
                ha="right", va="center"),
        ax.text(0.04, 2250, TESTI["piu_caldo"], color=COL["muto"], fontsize=px(21),
                ha="left", va="center"),
    ]

    fisse += intestazione(fig, TESTI["titolo"],
                          TESTI["sottotitolo"].format(a=FINESTRA[0], b=FINESTRA[1], n=n),
                          TESTI["fonte"])
    leg = legenda(fig, [(TESTI["leg_punto"], COL["serie"], "punto"),
                        (TESTI["leg_mediana"], COL["serie_dec"], "linea_spessa")])

    punti = ax.scatter([0] * n, [x["quota"] for x in st], s=110, color=COL["serie"],
                       lw=0, zorder=3)
    punti.set_alpha(None)

    # La mediana cresce dal basso verso l'alto
    l_med, = ax.plot([], [], color=COL["serie_dec"], lw=5, solid_capstyle="butt",
                     zorder=2)
    t_med = ax.text(med, YMAX, f"mediana {cifra(med)}", color=COL["serie_dec"],
                    fontsize=px(22), fontweight="semibold", ha="left", va="bottom",
                    alpha=0)

    # Il passo del trekking: anello bianco e nome
    lu = next(x for x in st if x["nome"] == LUOGO)
    anello, = ax.plot([lu["trend"]], [lu["quota"]], "o", ms=17, mfc="none",
                      mec=COL["testo"], mew=2.5, alpha=0, zorder=5)
    t_lu = [ax.annotate(TESTI["luogo"], (lu["trend"], lu["quota"]), xytext=(22, 12),
                        textcoords="offset pixels", color=COL["testo"],
                        fontsize=px(25), fontweight="semibold", va="bottom", alpha=0),
            ax.annotate(f"{lu['quota']:.0f} m · {cifra(lu['trend'])}",
                        (lu["trend"], lu["quota"]), xytext=(22, 8),
                        textcoords="offset pixels", color=COL["muto"],
                        fontsize=px(22), va="top", alpha=0)]

    # Nel margine destro: prima il contatore delle stazioni arrivate, poi nello
    # stesso punto il conto finale, che comincia con lo stesso numero
    xm = 0.105 + 0.62 + 0.04
    conta = [fig.text(xm, 0.56, "", color=COL["testo"], fontsize=px(64),
                      fontweight="semibold", va="baseline"),
             fig.text(xm, 0.515, TESTI["conta_sotto"], color=COL["testo2"],
                      fontsize=px(25), va="baseline")]
    finali = [
        fig.text(xm, 0.56, TESTI["conto"].format(n=caldi), color=COL["testo"],
                 fontsize=px(64), fontweight="semibold", va="baseline"),
        fig.text(xm, 0.515, TESTI["conto_sotto"], color=COL["testo2"],
                 fontsize=px(25), va="baseline"),
        fig.text(xm, 0.38, f"{cifra(med)} °C", color=COL["serie_dec"],
                 fontsize=px(48), fontweight="semibold", va="baseline"),
        fig.text(xm, 0.345, TESTI["mediana_sotto"], color=COL["muto"],
                 fontsize=px(21), va="baseline"),
    ]

    a0, a1 = TEMPI["arrivo"]
    partenze = [a0 + (a1 - a0) * i / max(n - 1, 1) for i in range(n)]
    colore = punti.get_facecolors()[0].copy()

    def stato(t: float) -> None:
        alpha(fisse, rampa(t, 0.0, 0.8))
        alpha(leg, rampa(t, 0.6, 0.6))

        xs, alfa = [], []
        for x, t0 in zip(st, partenze):
            xs.append(x["trend"] * rampa(t, t0, TEMPI["scivola"]))
            alfa.append(0.85 * rampa(t, t0 - 0.15, 0.3))
        punti.set_offsets(list(zip(xs, [x["quota"] for x in st])))
        punti.set_facecolors([(*colore[:3], a) for a in alfa])

        arrivati = sum(t >= t0 + TEMPI["scivola"] * 0.5 for t0 in partenze)
        conta[0].set_text(f"{arrivati}")
        alpha(conta, rampa(t, a0, 0.4) * (1 - rampa(t, TEMPI["conto"], 0.5)))

        r = rampa(t, TEMPI["mediana"], 1.0)
        l_med.set_data([med, med], [-60, -60 + (YMAX + 60) * r])
        t_med.set_alpha(rampa(t, TEMPI["mediana"] + 0.8, 0.4))

        a_lu = rampa(t, TEMPI["luogo"], 0.5)
        anello.set_alpha(a_lu)
        alpha(t_lu, rampa(t, TEMPI["luogo"] + 0.2, 0.5))

        for i, art in enumerate(finali):
            alpha([art], rampa(t, TEMPI["conto"] + 0.2 * i, 0.5))

    return fig, stato


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--out", default=str(OUT))
    p.add_argument("--frame", type=float, help="solo il fotogramma a questo tempo (s), in PNG")
    p.add_argument("--alfa", action="store_true",
                   help="fondo trasparente, ProRes 4444 (*_alfa.mov)")
    a = p.parse_args()
    famiglia = carica_font()
    fig, stato = costruisci()
    print(esporta(fig, stato, TEMPI["fine"], uscita(Path(a.out), a.alfa), a.frame, a.alfa),
          f"(font {famiglia})")


if __name__ == "__main__":
    main()
