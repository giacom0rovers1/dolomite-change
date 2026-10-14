#!/usr/bin/env python3
"""
Animazione del film: il momento piu' freddo
dell'estate (analysis.ipynb, sezione 3c).

Per ogni estate, la quota piu' bassa raggiunta dallo zero termico, 1950-2025. La
linea si disegna anno per anno, si ferma un istante sul 2005, e alla fine compare
il confronto fra le medie degli anni '70 (2003 m, sotto Passo Falzarego) e del
2020-25 (2555 m, sopra il passo).

Uso:
    python scripts/anim_zero_termico.py             # -> video/zero_termico.mp4
    python scripts/anim_zero_termico.py --frame 9   # solo il fotogramma a 9 s
"""
from __future__ import annotations

import argparse
import csv
import math
import statistics
from pathlib import Path

from anim_stile import (COL, VIDEO, RADICE, alpha, carica_font, esporta, figura,
                        intestazione, interpola, legenda, px, rampa,
                        uscita)

CSV = RADICE / "data" / "risultati" / "zero_termico_estivo.csv"
OUT = VIDEO / "zero_termico.mp4"

TESTI = {
    "titolo": "Il momento più freddo dell’estate",
    "sottotitolo": "Quota più bassa raggiunta dallo zero termico tra giugno e "
                   "agosto, zona Passo Falzarego–Tofane",
    "leg_anno": "ogni estate",
    "leg_dec": "media del decennio",
    "leg_clou": "2005, l’anno del trekking",
    "fonte": "Dati: ERA5, Copernicus Climate Change Service / ECMWF",
    "da_lab": "anni ’70",
    "a_lab": "2020–25",
}

# Secondi. DISEGNO: (tempo, anno raggiunto dalla linea); la coppia sul 2005 e'
# la pausa.
TEMPI = {
    "disegno": [(1.2, 1950.0), (5.4, 2005.0), (6.3, 2005.0), (8.2, 2025.0)],
    "confronto": 8.4,
    "fine": 13.0,
}

QUOTE = [(2105, "Passo Falzarego"), (2752, "Rifugio Lagazuoi"),
         (3225, "Tofana di Rozes")]
ANNO_CLOU = 2005


def leggi() -> tuple[list[int], list[float]]:
    righe = list(csv.DictReader(CSV.open(encoding="utf8")))
    return [int(r["anno"]) for r in righe], [float(r["minimo_m"]) for r in righe]


def media(anni, vals, lo, hi) -> float:
    return statistics.fmean(v for a, v in zip(anni, vals) if lo <= a <= hi)


def costruisci():
    anni, zmin = leggi()
    ultimo = anni[-1]
    # Gradini per decennio (x0, x1, valore); l'ultimo copre 2020-25
    dec = [(lo, min(lo + 10, ultimo + 1), media(anni, zmin, lo, lo + 9))
           for lo in range(1950, ultimo + 1, 10)]
    v_da, v_a = media(anni, zmin, 1970, 1979), media(anni, zmin, 2020, ultimo)
    v_clou = zmin[anni.index(ANNO_CLOU)]

    fig = figura()
    ax = fig.add_axes([0.165, 0.13, 0.66, 0.63], facecolor=COL["fondo"])
    ax.set_xlim(1949.5, ultimo + 0.5)
    ax.set_ylim(1100, 3350)
    for lato in ("top", "right", "left"):
        ax.spines[lato].set_visible(False)
    ax.spines["bottom"].set_color(COL["asse"])
    ax.spines["bottom"].set_linewidth(1.5)
    ax.set_yticks([])
    ax.set_xticks(range(1950, ultimo + 1, 10))
    ax.tick_params(axis="x", colors=COL["muto"], labelsize=px(24), length=0, pad=12)
    fisse = [ax.spines["bottom"]] + ax.get_xticklabels()

    # Le quote del trekking fanno da asse: linee tratteggiate, nome a sinistra
    for q, nome in QUOTE:
        ln, = ax.plot([1949.5, ultimo + 0.5], [q, q], color=COL["muto"], lw=1.5,
                      ls=(0, (4, 5)), zorder=1)
        kw = dict(xycoords=("axes fraction", "data"), textcoords="offset pixels",
                  ha="right")
        fisse += [ln,
                  ax.annotate(nome, (0, q), xytext=(-22, 6), va="bottom",
                              color=COL["testo"], fontsize=px(25),
                              fontweight="semibold", **kw),
                  ax.annotate(f"{q} m", (0, q), xytext=(-22, -6), va="top",
                              color=COL["muto"], fontsize=px(22), **kw)]

    fisse += intestazione(fig, TESTI["titolo"], TESTI["sottotitolo"], TESTI["fonte"])
    leg = legenda(fig, [(TESTI["leg_anno"], COL["serie"], "linea"),
                        (TESTI["leg_dec"], COL["serie_dec"], "linea_spessa"),
                        (TESTI["leg_clou"], COL["clou"], "punto")])
    anno_txt = fig.text(0.825, 0.858, "", color=COL["testo2"], fontsize=px(64),
                        fontweight="semibold", ha="right", va="baseline")

    l_anno, = ax.plot([], [], color=COL["serie"], lw=2.5, alpha=0.6,
                      solid_joinstyle="round", zorder=3)
    l_dec, = ax.plot([], [], color=COL["serie_dec"], lw=6, solid_capstyle="round",
                     solid_joinstyle="round", zorder=4)
    p_clou, = ax.plot([ANNO_CLOU], [v_clou], "o", color=COL["clou"], ms=0,
                      mec=COL["fondo"], mew=3, zorder=6)
    guida_clou, = ax.plot([ANNO_CLOU, ANNO_CLOU], [v_clou - 70, 1330],
                          color=COL["clou"], lw=1.5, alpha=0, zorder=5)
    t_clou = ax.text(ANNO_CLOU, 1270, f"{ANNO_CLOU}  ·  {v_clou:.0f} m",
                     color=COL["clou"], fontsize=px(25), fontweight="semibold",
                     ha="center", va="top", alpha=0, zorder=6)

    # Confronto finale nel margine destro: anni '70 contro 2020-25
    kw = dict(xycoords=("axes fraction", "data"), textcoords="offset pixels",
              ha="left", annotation_clip=False)
    diff = round((v_a - v_da) / 10) * 10
    finali = [
        ax.plot([1970, ultimo + 0.5], [v_da, v_da], color=COL["testo2"], lw=1.5,
                ls=(0, (1.5, 4)), alpha=0, zorder=2)[0],
        ax.annotate(f"{v_a:.0f} m", (1, v_a), xytext=(50, 0), va="center",
                    color=COL["serie_dec"], fontsize=px(36), fontweight="semibold",
                    **kw),
        ax.annotate(TESTI["a_lab"], (1, v_a), xytext=(50, -26), va="top",
                    color=COL["muto"], fontsize=px(21), **kw),
        ax.annotate(f"{v_da:.0f} m", (1, v_da), xytext=(50, 0), va="center",
                    color=COL["testo2"], fontsize=px(30), fontweight="semibold",
                    **kw),
        ax.annotate(TESTI["da_lab"], (1, v_da), xytext=(50, -22), va="top",
                    color=COL["muto"], fontsize=px(21), **kw),
        ax.annotate("", xy=(1, v_a - 45), xytext=(1, v_da + 45),
                    xycoords=("axes fraction", "data"), annotation_clip=False,
                    arrowprops=dict(arrowstyle="-|>,head_width=0.5,head_length=0.9",
                                    color=COL["testo"], lw=2.5, shrinkA=0,
                                    shrinkB=0)),
        ax.annotate(f"+{diff:.0f} m", (1, (v_a + v_da) / 2), xytext=(50, 0),
                    va="center", color=COL["testo"], fontsize=px(30),
                    fontweight="bold", **kw),
    ]

    t_pausa, t_conf = TEMPI["disegno"][1][0], TEMPI["confronto"]

    def stato(t: float) -> None:
        alpha(fisse, rampa(t, 0.0, 0.8))
        alpha(leg, rampa(t, 0.6, 0.6))

        y = interpola(t, TEMPI["disegno"])
        if t < TEMPI["disegno"][0][0]:
            l_anno.set_data([], [])
            l_dec.set_data([], [])
            anno_txt.set_text("")
        else:
            k = int(math.floor(y)) - anni[0]
            xs, ys = list(anni[: k + 1]), list(zmin[: k + 1])
            if k + 1 < len(anni):
                f = y - math.floor(y)
                xs.append(y)
                ys.append(zmin[k] + f * (zmin[k + 1] - zmin[k]))
            l_anno.set_data(xs, ys)
            # i gradini seguono la punta della linea annuale
            fine = min(y + 0.5, ultimo + 0.5)
            gx, gy = [], []
            for x0, x1, v in dec:
                if fine <= x0:
                    break
                gx += [x0, min(x1, fine)]
                gy += [v, v]
            l_dec.set_data(gx, gy)
            anno_txt.set_text(f"{int(math.floor(y + 1e-6))}")
        anno_txt.set_alpha(1 - rampa(t, t_conf, 0.6))

        # Il 2005 compare quando la linea ci arriva, con un piccolo rimbalzo
        r = rampa(t, t_pausa - 0.1, 0.35)
        rimbalzo = 1 + 0.35 * math.sin(math.pi * min(max((t - t_pausa + 0.1) / 0.45, 0), 1))
        p_clou.set_markersize(20 * r * rimbalzo if r < 1 else 20)
        guida_clou.set_alpha(0.8 * rampa(t, t_pausa + 0.1, 0.4))
        t_clou.set_alpha(rampa(t, t_pausa + 0.15, 0.4))

        # Finale: la serie annuale si attenua, compare il confronto
        l_anno.set_alpha(0.6 - 0.35 * rampa(t, t_conf, 0.8))
        for i, art in enumerate(finali):
            alpha([art], rampa(t, t_conf + 0.15 * i, 0.5))

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
