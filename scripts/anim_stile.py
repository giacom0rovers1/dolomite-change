#!/usr/bin/env python3
"""
Stile comune alle animazioni del video: formato, palette, font, easing, export.

Formato: 1920x1080 a 23,976 fps (24000/1001, come la timeline del montaggio), in
due versioni: H.264 su fondo scuro (.mp4), oppure ProRes 4444 con canale alfa
(_alfa.mov) da appoggiare in montaggio sopra un fondo o sopra il girato. La
palette e' scura, un solo blu per i dati e arancio solo per il 2005. Le figure di
analysis.ipynb sono l'ultimo fotogramma delle animazioni, cosi' film e archivio
mostrano lo stesso oggetto.

Serve matplotlib, e ffmpeg nel PATH. Il font e' Inter: i tre pesi usati sono in
scripts/fonts/ (licenza OFL, LICENSE.txt), cosi' il risultato e' lo stesso su
ogni macchina. Se mancassero si ripiega su DejaVu Sans.

Ogni script anim_*.py ha in testa due dizionari, TESTI e TEMPI: le parole a
schermo e i secondi in cui succedono le cose. Quando il parlato e' registrato si
rifa' il timing cambiando solo TEMPI.
"""
from __future__ import annotations

import math
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402
from matplotlib import font_manager  # noqa: E402
from matplotlib.animation import FFMpegWriter  # noqa: E402

RADICE = Path(__file__).resolve().parent.parent
VIDEO = RADICE / "video"

W, H, DPI = 1920, 1080, 100
FPS, FPS_FFMPEG = 24000 / 1001, "24000/1001"

COL = {
    "fondo": "#0d0d0d",
    "testo": "#ffffff",
    "testo2": "#c3c2b7",
    "muto": "#898781",
    "asse": "#383835",
    "serie": "#3987e5",
    "serie_dec": "#6da7ec",
    "clou": "#d95926",
}


def px(n: float) -> float:
    """Dimensione in pixel convertita in punti tipografici."""
    return n * 72 / DPI


def carica_font() -> str:
    cartelle = [RADICE / "scripts" / "fonts", Path.home() / ".fonts",
                Path.home() / ".local" / "share" / "fonts"]
    for c in cartelle:
        for f in c.glob("**/Inter-*.ttf"):
            font_manager.fontManager.addfont(str(f))
    nomi = {f.name for f in font_manager.fontManager.ttflist}
    famiglia = "Inter" if "Inter" in nomi else "DejaVu Sans"
    matplotlib.rcParams["font.family"] = famiglia
    return famiglia


def ease(x: float) -> float:
    """Ease-in-out sinusoidale su [0, 1]."""
    x = min(max(x, 0.0), 1.0)
    return 0.5 - 0.5 * math.cos(math.pi * x)


def rampa(t: float, t0: float, durata: float) -> float:
    """0 prima di t0, 1 dopo t0 + durata, raccordo morbido in mezzo."""
    return ease((t - t0) / durata)


def interpola(t: float, chiavi: list[tuple[float, float]]) -> float:
    """Valore al tempo t da una lista di (tempo, valore), easing per tratto."""
    if t <= chiavi[0][0]:
        return chiavi[0][1]
    for (t0, v0), (t1, v1) in zip(chiavi, chiavi[1:]):
        if t <= t1:
            return v0 + (v1 - v0) * ease((t - t0) / (t1 - t0))
    return chiavi[-1][1]


def figura():
    return plt.figure(figsize=(W / DPI, H / DPI), dpi=DPI, facecolor=COL["fondo"])


def intestazione(fig, titolo: str, sottotitolo: str, fonte: str) -> list:
    """Titolo e sottotitolo in alto a sinistra, fonte in basso: dentro il 5 %
    di margine di sicurezza del formato 16:9."""
    return [
        fig.text(0.05, 0.905, titolo, color=COL["testo"], fontsize=px(48),
                 fontweight="semibold", va="baseline"),
        fig.text(0.05, 0.858, sottotitolo, color=COL["testo2"], fontsize=px(25),
                 va="baseline"),
        fig.text(0.05, 0.04, fonte, color=COL["muto"], fontsize=px(18)),
    ]


def legenda(fig, voci: list[tuple[str, str, str]], y: float = 0.808) -> list:
    """voci: (testo, colore, forma) con forma fra 'linea', 'linea_spessa',
    'punto', 'barra'. Le larghezze vengono misurate, non stimate."""
    artisti, x = [], 0.05
    for testo, colore, forma in voci:
        if forma == "punto":
            m = plt.Line2D([x + 0.009], [y + 0.006], marker="o", ms=13,
                           color=colore, lw=0)
        elif forma == "barra":
            m = plt.Rectangle((x + 0.005, y - 0.002), 0.012, 0.022, color=colore,
                              transform=fig.transFigure)
        else:
            m = plt.Line2D([x, x + 0.022], [y + 0.006] * 2, color=colore,
                           lw=6 if forma == "linea_spessa" else 2.5,
                           solid_capstyle="round")
        fig.add_artist(m)
        t = fig.text(x + 0.03, y, testo, color=COL["testo2"], fontsize=px(21),
                     va="baseline")
        artisti += [m, t]
        x += 0.03 + t.get_window_extent(fig.canvas.get_renderer()).width / W + 0.035
    return artisti


def alpha(artisti, a: float) -> None:
    """Imposta la trasparenza anche sulla freccia delle annotazioni."""
    for art in artisti:
        art.set_alpha(a)
        if getattr(art, "arrow_patch", None) is not None:
            art.arrow_patch.set_alpha(a)


def uscita(out: Path, alfa: bool) -> Path:
    """Nome del file per la versione trasparente: neve_5luglio_alfa.mov."""
    return out.with_name(f"{out.stem}_alfa.mov") if alfa else out


def esporta(fig, stato, durata: float, out: Path, frame: float | None = None,
            alfa: bool = False) -> Path:
    """Scrive il video, oppure con frame=t solo il PNG del fotogramma a t secondi.

    Con alfa=True il fondo della figura e degli assi diventa trasparente e il video
    esce in ProRes 4444 con canale alfa, che leggono Premiere, DaVinci Resolve e
    Final Cut. Tutto il resto (versante, griglia, testi) resta identico.
    """
    out.parent.mkdir(parents=True, exist_ok=True)
    fondo = "none" if alfa else COL["fondo"]
    if alfa:
        fig.patch.set_alpha(0)
        for ax in fig.axes:
            ax.patch.set_alpha(0)
    if frame is not None:
        stato(frame)
        png = out.with_name(f"{out.stem}_{frame:05.2f}s.png")
        fig.savefig(png, dpi=DPI, facecolor=fondo)
        return png
    # Da RGB a YUV con la matrice BT.709, dichiarata nel file (setparams: le opzioni
    # -color_primaries e -color_trc da sole ffmpeg le perde). Senza, ffmpeg usa la
    # BT.601 e i programmi di montaggio leggono l'HD come Rec.709: il blu dei dati
    # si sposta di 9 livelli su 255 e l'arancio di 11, e il video non combacia piu'
    # con i cartelli e con i fotogrammi finali in PNG.
    def rec709(pix_fmt: str) -> list[str]:
        return ["-vf", f"scale=out_color_matrix=bt709:out_range=tv,format={pix_fmt},"
                       "setparams=color_primaries=bt709:color_trc=bt709:"
                       "colorspace=bt709:range=tv",
                "-pix_fmt", pix_fmt]

    if alfa:
        writer = FFMpegWriter(fps=FPS, codec="prores_ks", bitrate=-1,
                              extra_args=["-r", FPS_FFMPEG, "-profile:v", "4444",
                                          *rec709("yuva444p10le"), "-vendor", "apl0"])
    else:
        writer = FFMpegWriter(fps=FPS, codec="libx264", bitrate=-1,
                              extra_args=["-r", FPS_FFMPEG, *rec709("yuv420p"), "-crf", "16",
                                          "-preset", "slow", "-tune", "animation"])
    with writer.saving(fig, str(out), DPI):
        for i in range(int(round(durata * FPS))):
            stato(i / FPS)
            writer.grab_frame(facecolor=fondo)
    return out
