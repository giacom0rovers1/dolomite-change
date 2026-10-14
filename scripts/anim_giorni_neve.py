#!/usr/bin/env python3
"""
Animazione del film: quanti giorni d'estate puo' ancora nevicare alle tre
quote del trekking (analysis.ipynb, sezione 3b).

Tre pannelli, impilati per quota: la Tofana in alto, il Falzarego in basso, ognuno
con la sua scala. Le tre serie si disegnano insieme, 1950-2025, con una pausa sul
2005 e lo stesso ritmo di zero_termico.mp4, che nel film viene subito prima. Poi
il Lagazuoi e la Tofana si spengono, il pannello del Passo Falzarego si allarga a
tutta altezza, e nel margine destro compare il confronto anni '70 / 2020-25, solo
per il passo, come il confronto finale di zero_termico.mp4.

I tempi in TEMPI seguono la voce del film: per un'altra voce si spostano
"zoom", "anni70" e "oggi".

Uso:
    python scripts/anim_giorni_neve.py              # -> video/giorni_neve.mp4
    python scripts/anim_giorni_neve.py --frame 12   # solo il fotogramma a 12 s
"""
from __future__ import annotations

import argparse
import csv
import math
import statistics
from pathlib import Path

from anim_stile import (COL, RADICE, VIDEO, W, alpha, carica_font, esporta, figura,
                        intestazione, interpola, legenda, px, rampa,
                        uscita)

CSV = RADICE / "data" / "risultati" / "giorni_neve_possibile_per_quota.csv"
OUT = VIDEO / "giorni_neve.mp4"

TESTI = {
    "titolo": "Quanti giorni d’estate può ancora nevicare",
    "sottotitolo": "Giorni tra giugno e agosto in cui la quota della neve scende "
                   "sotto ciascun luogo",
    "leg_anno": "ogni estate",
    "leg_dec": "media del decennio",
    "leg_clou": "2005, l’anno del trekking",
    "fonte": "Dati: ERA5, Copernicus Climate Change Service / ECMWF · "
             "quota della neve = zero termico − 300 m",
    "da_lab": "anni ’70",
    "a_lab": "2020–25",
}

# Secondi. "disegno": (tempo, anno raggiunto), la coppia sul 2005 e' la pausa,
# uguale a zero_termico.mp4. "zoom": gli altri luoghi si spengono e il passo si
# allarga; "anni70" e "oggi": quando compaiono i due valori del passo.
TEMPI = {
    "disegno": [(1.2, 1950.0), (5.4, 2005.0), (6.3, 2005.0), (8.2, 2025.0)],
    "zoom": 8.8,
    "anni70": 10.6,
    "oggi": 12.4,
    "fine": 15.7,
}
SPEGNI, ALLARGA = 0.6, 1.2   # durate, in secondi, delle due fasi dello zoom

# Dal basso verso l'alto. (colonna, nome, quota, limite asse y, tacche). Il primo,
# il passo, e' quello che resta e si allarga.
PANNELLI = [
    ("Passo_Falzarego_2105m", "Passo Falzarego", "2105 m", 16, (0, 5, 10, 15)),
    ("Rifugio_Lagazuoi_2752m", "Rifugio Lagazuoi", "2752 m", 44, (0, 20, 40)),
    ("Tofana_di_Rozes_3225m", "Tofana di Rozes", "3225 m", 82, (0, 40, 80)),
]
ANNO_CLOU = 2005

# Geometria in frazioni di figura. Dopo lo zoom il passo occupa l'altezza dei tre
# pannelli, e il suo titolo prende il posto di quello della Tofana.
X0, LARG = 0.085, 0.71
Y0, H_PAN, SPAZIO = 0.115, 0.148, 0.07
H_ZOOM = 2 * (H_PAN + SPAZIO) + H_PAN


def leggi() -> tuple[list[int], dict[str, list[int]]]:
    righe = list(csv.DictReader(CSV.open(encoding="utf8")))
    anni = [int(r["anno"]) for r in righe]
    return anni, {c: [int(r[c]) for r in righe] for c, *_ in PANNELLI}


def media(anni, vals, lo, hi) -> float:
    return statistics.fmean(v for a, v in zip(anni, vals) if lo <= a <= hi)


def cifra(v: float) -> str:
    """Un decimale, con la virgola. Arrotondare 0,2 a 0 direbbe "mai", ma nel
    2024 un giorno c'e' stato (si vede la barra, e la voce dice "un giorno
    solo")."""
    return f"{v:.1f}".replace(".", ",")


def costruisci():
    anni, serie = leggi()
    ultimo = anni[-1]
    fig = figura()
    fisse = intestazione(fig, TESTI["titolo"], TESTI["sottotitolo"], TESTI["fonte"])
    leg = legenda(fig, [(TESTI["leg_anno"], COL["serie"], "barra"),
                        (TESTI["leg_dec"], COL["serie_dec"], "linea_spessa"),
                        (TESTI["leg_clou"], COL["clou"], "barra")])
    anno_txt = fig.text(X0 + LARG, 0.858, "", color=COL["testo2"], fontsize=px(64),
                        fontweight="semibold", ha="right", va="baseline")

    pan = []
    for i, (col, nome, quota, ymax, tacche) in enumerate(PANNELLI):
        vals = serie[col]
        y0 = Y0 + i * (H_PAN + SPAZIO)
        ax = fig.add_axes([X0, y0, LARG, H_PAN], facecolor=COL["fondo"])
        ax.set_xlim(1949.5, ultimo + 0.5)
        ax.set_ylim(0, ymax)
        for lato in ("top", "right", "left"):
            ax.spines[lato].set_visible(False)
        ax.spines["bottom"].set_color(COL["asse"])
        ax.spines["bottom"].set_linewidth(1.5)
        ax.set_yticks(tacche)
        ax.tick_params(axis="y", colors=COL["muto"], labelsize=px(19), length=0, pad=10)
        ax.set_xticks(range(1950, ultimo + 1, 10) if i == 0 else [])
        ax.tick_params(axis="x", colors=COL["muto"], labelsize=px(24), length=0, pad=12)
        griglia = [ax.axhline(v, color=COL["asse"], lw=1, zorder=0) for v in tacche[1:]]
        testi = ax.get_yticklabels() + ax.get_xticklabels()
        tit = [fig.text(X0, y0 + H_PAN + 0.014, nome, color=COL["testo"],
                        fontsize=px(25), fontweight="semibold", va="baseline")]
        larg = tit[0].get_window_extent(fig.canvas.get_renderer()).width / W
        tit.append(fig.text(X0 + larg + 0.008, y0 + H_PAN + 0.014, quota,
                            color=COL["muto"], fontsize=px(22), va="baseline"))

        barre = ax.bar(anni, [0] * len(anni), width=0.72, zorder=2,
                       color=[COL["clou"] if a == ANNO_CLOU else COL["serie"]
                              for a in anni]).patches
        gradino, = ax.plot([], [], color=COL["serie_dec"], lw=4.5, zorder=3,
                           solid_capstyle="butt", solid_joinstyle="miter")
        dec = [(lo - 0.5, min(lo + 9, ultimo) + 0.5, media(anni, vals, lo, lo + 9))
               for lo in range(1950, ultimo + 1, 10)]
        # Il 2005 nella riga degli anni, sotto le tre barre arancioni: distanza
        # dall'asse in pixel, cosi' resta al suo posto anche con lo zoom
        lab05 = ax.annotate(str(ANNO_CLOU) if i == 0 else "", (ANNO_CLOU, 0),
                            xycoords=("data", "axes fraction"), xytext=(0, -17),
                            textcoords="offset pixels", color=COL["clou"],
                            fontsize=px(22), fontweight="semibold", ha="center",
                            va="top", alpha=0, annotation_clip=False)
        pan.append(dict(ax=ax, vals=vals, barre=barre, gradino=gradino, dec=dec,
                        tit=tit, cornice=[ax.spines["bottom"]] + griglia + testi + tit,
                        lab05=lab05))

    # Il confronto, solo per il passo: i due gradini in evidenza e, nel margine
    # destro, i due valori all'altezza giusta con la freccia, come in
    # zero_termico.mp4. Le coordinate seguono l'asse, quindi anche lo zoom.
    passo = pan[0]
    ax = passo["ax"]
    v_da = media(anni, passo["vals"], 1970, 1979)
    v_a = media(anni, passo["vals"], 2020, ultimo)
    ev_da, = ax.plot([1969.5, 1979.5], [v_da, v_da], color=COL["testo"], lw=5,
                     alpha=0, zorder=4, solid_capstyle="butt")
    ev_a, = ax.plot([2019.5, ultimo + 0.5], [v_a, v_a], color=COL["testo"], lw=5,
                    alpha=0, zorder=4, solid_capstyle="butt")
    kw = dict(xycoords=("axes fraction", "data"), textcoords="offset pixels",
              ha="left", annotation_clip=False)
    n_da = [ax.annotate(cifra(v_da), (1, v_da), xytext=(50, 0), va="center",
                        color=COL["testo2"], fontsize=px(30), fontweight="semibold",
                        alpha=0, **kw),
            ax.annotate(TESTI["da_lab"], (1, v_da), xytext=(50, -22), va="top",
                        color=COL["muto"], fontsize=px(21), alpha=0, **kw)]
    # La freccia scende dal valore degli anni '70 a quello di oggi: 0,9 giorni di
    # margine sono circa 35 px a zoom finito
    n_a = [ax.annotate("", xy=(1, v_a + 0.9), xytext=(1, v_da - 0.9),
                       xycoords=("axes fraction", "data"), annotation_clip=False,
                       arrowprops=dict(arrowstyle="-|>,head_width=0.5,head_length=0.9",
                                       color=COL["testo"], lw=2.5, shrinkA=0,
                                       shrinkB=0)),
           ax.annotate(cifra(v_a), (1, v_a), xytext=(50, 6), va="bottom",
                       color=COL["serie_dec"], fontsize=px(36), fontweight="semibold",
                       alpha=0, **kw),
           ax.annotate(TESTI["a_lab"], (1, v_a), xytext=(50, 0), va="top",
                       color=COL["muto"], fontsize=px(21), alpha=0, **kw)]

    t_pausa = TEMPI["disegno"][1][0]

    def stato(t: float) -> None:
        alpha(fisse, rampa(t, 0.0, 0.8))
        alpha(leg, rampa(t, 0.6, 0.6))
        y = interpola(t, TEMPI["disegno"])
        disegna = t >= TEMPI["disegno"][0][0]
        anno_txt.set_text(f"{int(math.floor(y + 1e-6))}" if disegna else "")
        anno_txt.set_alpha(1 - rampa(t, TEMPI["disegno"][-1][0] + 0.2, 0.4))

        # Zoom: prima gli altri due luoghi si spengono, poi il passo si allarga
        spento = rampa(t, TEMPI["zoom"], SPEGNI)
        largo = rampa(t, TEMPI["zoom"] + 0.8 * SPEGNI, ALLARGA)
        h = H_PAN + (H_ZOOM - H_PAN) * largo
        passo["ax"].set_position([X0, Y0, LARG, h])
        for tx in passo["tit"]:
            tx.set_y(Y0 + h + 0.014)

        for i, p in enumerate(pan):
            a_pan = 1.0 if i == 0 else 1 - spento
            # Spenti, gli altri assi spariscono del tutto: il loro sfondo, opaco,
            # coprirebbe a fasce il passo che si allarga sotto
            p["ax"].set_visible(a_pan > 0)
            for a, v, b in zip(anni, p["vals"], p["barre"]):
                b.set_height(v * ease_barra(y - a) if disegna else 0)
                b.set_alpha(a_pan)
            fine = min(y + 0.5, anni[-1] + 0.5)
            gx, gy = [], []
            for x0, x1, v in p["dec"]:
                if not disegna or fine <= x0:
                    break
                gx += [x0, min(x1, fine)]
                gy += [v, v]
            p["gradino"].set_data(gx, gy)
            p["gradino"].set_alpha(a_pan)
            alpha(p["cornice"], rampa(t, 0.0, 0.8) * a_pan)
            p["lab05"].set_alpha(rampa(t, t_pausa, 0.4) * a_pan)

        a_da, a_a = rampa(t, TEMPI["anni70"], 0.5), rampa(t, TEMPI["oggi"], 0.5)
        ev_da.set_alpha(0.9 * a_da)
        ev_a.set_alpha(0.9 * a_a)
        alpha(n_da, a_da)
        alpha(n_a, a_a)

    return fig, stato


def ease_barra(d: float) -> float:
    """La barra cresce nell'anno che precede la punta: quando la punta arriva
    sull'anno (e nella pausa sul 2005) la barra e' gia' alta del tutto."""
    x = min(max(d + 1.0, 0.0), 1.0)
    return 0.5 - 0.5 * math.cos(math.pi * x)


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
