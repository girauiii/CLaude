"""Análisis y figuras de la discusión de resultados de la práctica BC.

Lee la hoja de cálculo del grupo (v3009_v1.xlsx), recalcula las rectas de
Wilson con los 10 puntos de cada serie, compara con Sieder-Tate, calcula Rf
y genera las figuras 2-6 de la discusión, además de un resumen numérico.

Uso:
    python analisis_BC.py ruta/a/v3009_v1.xlsx [carpeta_salida]

Requisitos: openpyxl, numpy, matplotlib.

Decisiones de cálculo (las mismas que en el texto):
- La recta de Wilson del INT 1 con agua fría a 150 L/h usa los 10 puntos
  (filas 14-23). La hoja v3009_v1 usa solo las filas 16-23; ese ajuste se
  conserva como prueba de sensibilidad ("INT1 f150 8p").
- UA se calcula con el calor cedido por el corriente caliente (Q̇c), como en
  la hoja. La variante con la media de Q̇c y Q̇f es solo una prueba de
  sensibilidad.
- hᵢ de Sieder-Tate se toma tal cual de la hoja (columna AK), sin la
  corrección (μ/μw)^0,14.
"""

import json
import sys
import textwrap
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import openpyxl  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402
from matplotlib.ticker import FuncFormatter, MultipleLocator  # noqa: E402

# Geometría (protocolo; celdas C44-C47 del INT 1 e I39-I42 del INT 2)
AI = {"INT 1": np.pi * 0.008 * 4, "INT 2": 5 * np.pi * 0.006 * 1}
AO = {"INT 1": np.pi * 0.010 * 4, "INT 2": 5 * np.pi * 0.008 * 1}

# Series: (hoja, filas, etiqueta, color, marcador)
SERIES = {
    "INT1 f200": ("INT 1", range(3, 13), "INT 1, fría 200", "#2a78d6", "o"),
    "INT1 f150": ("INT 1", range(14, 24), "INT 1, fría 150", "#eb6834", "o"),
    "INT2 f150": ("INT 2", range(3, 13), "INT 2, fría 150", "#1baf7a", "s"),
    "INT2 f200": ("INT 2", range(14, 24), "INT 2, fría 200", "#4a3aa7", "s"),
}
ORDER = ["INT1 f200", "INT1 f150", "INT2 f150", "INT2 f200"]

# Colores de texto y de ejes
INK = "#0b0b0b"
INK2 = "#52514e"
MUTED = "#898781"
GRID = "#e1e0d9"
BASE = "#c3c2b7"
BAND = "#efeee9"
SURFACE = "#ffffff"

COLS = {
    "Vf": "B", "Vc": "C", "Tce": "D", "Tcs": "E", "Tfs": "F", "Tfe": "G",
    "Qc": "P", "Qf": "Q", "delta": "R", "dTml": "S", "UA": "T", "mu": "U",
    "v": "V", "Re": "W", "k": "AG", "Pr13": "AI", "hST": "AK", "Uo": "AM",
    "eps": "AO", "Jc": "J", "Kc": "K", "Mf": "M", "Nf": "N",
}


def load(path):
    wb = openpyxl.load_workbook(path, data_only=True)
    data = {}
    for key, (sheet, rows, *_rest) in SERIES.items():
        ws = wb[sheet]
        s = {name: np.array([ws[f"{col}{r}"].value for r in rows], dtype=float)
             for name, col in COLS.items()}
        s["exp"] = [str(ws[f"A{r}"].value) for r in rows]
        s["Qc"] /= 3600.0  # J/h -> W
        s["Qf"] /= 3600.0
        s["Cc"] = s["Jc"] * s["Kc"] / 3600.0  # W/K
        s["Cf"] = s["Mf"] * s["Nf"] / 3600.0
        s["Y"] = 1.0 / s["UA"]
        s["Z"] = s["Re"] ** -0.8
        s["ex"] = sheet
        data[key] = s
    return data


def linfit(x, y):
    n = len(x)
    m, b = np.polyfit(x, y, 1)
    yhat = m * x + b
    ss_res = float(((y - yhat) ** 2).sum())
    r2 = 1 - ss_res / float(((y - y.mean()) ** 2).sum())
    se_m = np.sqrt(ss_res / (n - 2) / float(((x - x.mean()) ** 2).sum()))
    return dict(m=float(m), C2=float(b), R2=float(r2), se_m=float(se_m), n=n)


def wilson(data):
    res = {}
    for key in ORDER:
        s = data[key]
        f = linfit(s["Z"], s["Y"])
        f["C1"] = 1 / f["m"]
        res[key] = f
    s = data["INT1 f150"]
    keep = slice(2, 10)  # filas 16-23: sin 111 ni 112a
    f = linfit(s["Z"][keep], s["Y"][keep])
    f["C1"] = 1 / f["m"]
    res["INT1 f150 8p"] = f
    return res


def derived(data, fits):
    out = {}
    for key in ORDER:
        s, f = data[key], fits[key]
        ex = s["ex"]
        hW = f["C1"] / AI[ex] * s["Re"] ** 0.8
        d = dict(
            hW=hW,
            ratio=hW / s["hST"],
            Rf=1 / hW - 1 / s["hST"],
            frac_in=f["m"] * s["Z"] / s["Y"],
            ho_eq=1 / (f["C2"] * AO[ex]),
        )
        Cmin = np.minimum(s["Cc"], s["Cf"])
        d["NTU"] = s["UA"] / Cmin
        d["Cmin_is_hot"] = s["Cc"] < s["Cf"]
        out[key] = d
    s, f = data["INT1 f150"], fits["INT1 f150 8p"]
    hW = f["C1"] / AI["INT 1"] * s["Re"] ** 0.8
    out["INT1 f150 8p"] = dict(hW=hW, ratio=hW / s["hST"], Rf=1 / hW - 1 / s["hST"])
    return out


def sensitivity_Qmean(data):
    """Recta de Wilson con UA calculado con la media de Q̇c y Q̇f."""
    res = {}
    for key in ORDER:
        s = data[key]
        UA = (s["Qc"] + s["Qf"]) / 2 / s["dTml"]
        f = linfit(s["Z"], 1 / UA)
        f["C1"] = 1 / f["m"]
        hW = f["C1"] / AI[s["ex"]] * s["Re"] ** 0.8
        f["ratio_min"] = float((hW / s["hST"]).min())
        f["ratio_max"] = float((hW / s["hST"]).max())
        Rf = 1 / hW - 1 / s["hST"]
        f["Rf_min"], f["Rf_max"] = float(Rf.min()), float(Rf.max())
        res[key] = f
    return res


# ---------------------------------------------------------------- figuras

def fmt_es(decimals=0, thousands=True):
    def _f(x, _pos=None):
        s = f"{x:,.{decimals}f}"
        s = s.replace(",", " ").replace(".", ",")
        s = s.replace(" ", "." if thousands else "")
        return s.replace("-", "−")
    return FuncFormatter(_f)


def style_axes(ax):
    ax.set_facecolor(SURFACE)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(BASE)
    ax.spines["bottom"].set_linewidth(1.0)
    ax.grid(axis="y", color=GRID, linewidth=0.8, linestyle="-")
    ax.set_axisbelow(True)
    ax.tick_params(axis="both", colors=MUTED, labelsize=9, length=0, pad=5)
    ax.xaxis.label.set_color(INK2)
    ax.yaxis.label.set_color(INK2)


def series_handles(keys, extra=()):
    hs = []
    for key in keys:
        _, _, label, color, marker = SERIES[key]
        hs.append(Line2D([0], [0], color=color, lw=1.8, marker=marker, ms=6.5,
                         mfc=color, mec=SURFACE, mew=1.2, label=label))
    return hs + list(extra)


def header(fig, ax, title, handles, ncol=4, y_title=0.985, y_leg=0.915):
    fig.text(0.5, y_title, title, ha="center", va="top", fontsize=11.5,
             fontweight="bold", color=INK)
    leg = fig.legend(handles=handles, loc="upper center", ncol=ncol,
                     bbox_to_anchor=(0.5, y_leg), frameon=False, fontsize=9,
                     handlelength=2.2, columnspacing=1.6, handletextpad=0.6)
    for t in leg.get_texts():
        t.set_color(INK2)
    return leg


def note(fig, text, y=0.02, width=112):
    fig.text(0.012, y, textwrap.fill(text, width), ha="left", va="bottom",
             fontsize=8, color=MUTED, linespacing=1.35)


def plot_series(ax, x, y, key, lw=1.8, ms=6.5, ls="-", hollow=False, z=3):
    _, _, label, color, marker = SERIES[key]
    ax.plot(x, y, color=color, lw=lw, ls=ls, zorder=z, solid_capstyle="round",
            solid_joinstyle="round")
    ax.plot(x, y, ls="none", marker=marker, ms=ms,
            mfc=(SURFACE if hollow else color), mec=(color if hollow else SURFACE),
            mew=(1.3 if hollow else 1.2), zorder=z + 1)


def fig_balance(data, out):
    fig, ax = plt.subplots(figsize=(6.7, 3.9), dpi=220)
    fig.subplots_adjust(left=0.115, right=0.93, top=0.80, bottom=0.21)
    style_axes(ax)
    for yref in (-10, 10):
        ax.axhline(yref, color=BASE, lw=0.9, zorder=1)
        ax.text(1.01, yref, f"{'+' if yref > 0 else '−'}10 %", va="center",
                ha="left", fontsize=8.5, color=MUTED,
                transform=ax.get_yaxis_transform(), clip_on=False)
    ax.axhline(0, color="#a9a79e", lw=1.0, zorder=1)
    for key in ORDER:
        s = data[key]
        plot_series(ax, s["Vc"], s["delta"], key)
    ax.set_xlim(135, 615)
    ax.set_ylim(-15, 15)
    ax.xaxis.set_major_locator(MultipleLocator(50))
    ax.set_xticks(np.arange(150, 601, 50))
    ax.yaxis.set_major_locator(MultipleLocator(5))
    ax.yaxis.set_major_formatter(FuncFormatter(
        lambda v, p: f"{v:+.0f} %".replace("-", "−") if v else "0 %"))
    ax.set_xlabel("Caudal caliente (L/h)", fontsize=9.5)
    ax.set_ylabel("Desviación δ (%)", fontsize=9.5)
    header(fig, ax, "Desviación del balance de energía", series_handles(ORDER))
    note(fig, "δ = (Q̇c − Q̇f)/Q̇c (Ec. 3). δ < 0: el agua fría gana más calor "
              "del que cede el corriente caliente. Caudal de agua fría en L/h.")
    fig.savefig(out / "fig2_balance.png", facecolor=SURFACE)
    plt.close(fig)


def fig_Uo(data, out):
    fig, ax = plt.subplots(figsize=(6.7, 3.9), dpi=220)
    fig.subplots_adjust(left=0.115, right=0.975, top=0.80, bottom=0.21)
    style_axes(ax)
    ax.axhspan(850, 1700, color=BAND, zorder=0, lw=0)
    ax.text(150, 1655, "Rango típico agua-agua (protocolo)", fontsize=8.5,
            color=MUTED, va="top", ha="left")
    for key in ORDER:
        s = data[key]
        plot_series(ax, s["Vc"], s["Uo"], key)
    ax.set_xlim(135, 615)
    ax.set_ylim(0, 1800)
    ax.set_xticks(np.arange(150, 601, 50))
    ax.yaxis.set_major_locator(MultipleLocator(300))
    ax.yaxis.set_major_formatter(fmt_es(0))
    ax.set_xlabel("Caudal caliente (L/h)", fontsize=9.5)
    ax.set_ylabel(r"$U_\mathrm{o}$ (W/(m$^2$·K))", fontsize=9.5)
    header(fig, ax, "Coeficiente global referido al área exterior",
           series_handles(ORDER))
    note(fig, "Uₒ = UA/Aₒ, con Aₒ = 0,1257 m² en ambos equipos. Franja: "
              "850–1.700 W/(m²·K), rango típico agua-agua según el protocolo.")
    fig.savefig(out / "fig3_Uo.png", facecolor=SURFACE)
    plt.close(fig)


def fig_wilson(data, fits, out):
    fig, axes = plt.subplots(2, 1, figsize=(6.7, 8.0), dpi=220)
    fig.subplots_adjust(left=0.115, right=0.975, top=0.915, bottom=0.12,
                        hspace=0.78)
    panels = [("INT 1 (doble tubo)", ["INT1 f200", "INT1 f150"], (4.8, 7.5)),
              ("INT 2 (carcasa y tubos)", ["INT2 f150", "INT2 f200"], (4.0, 15.0))]
    for ax, (title, keys, ylim) in zip(axes, panels):
        style_axes(ax)
        xs_all = np.concatenate([data[k]["Z"] for k in keys]) * 1e4
        xgrid = np.linspace(xs_all.min() * 0.97, xs_all.max() * 1.02, 50)
        eqs = []
        extra = []
        for key in keys:
            s, f = data[key], fits[key]
            _, _, label, color, marker = SERIES[key]
            ax.plot(xgrid, (f["m"] * xgrid / 1e4 + f["C2"]) * 1e3, color=color,
                    lw=1.6, zorder=2)
            ax.plot(s["Z"] * 1e4, s["Y"] * 1e3, ls="none", marker=marker, ms=6.5,
                    mfc=color, mec=SURFACE, mew=1.2, zorder=4)
            eqs.append(f"{label.split(', ')[1].capitalize()} L/h: y = "
                       f"{f['m'] / 10:.3f}x + {f['C2'] * 1e3:.2f} (R² = {f['R2']:.2f})"
                       .replace(".", ","))
        lines = ["   ".join(eqs)]
        if keys[1] == "INT1 f150":
            s, f = data["INT1 f150"], fits["INT1 f150 8p"]
            color = SERIES["INT1 f150"][3]
            x8 = s["Z"][2:] * 1e4
            xg8 = np.linspace(x8.min() * 0.97, x8.max() * 1.03, 20)
            ax.plot(xg8, (f["m"] * xg8 / 1e4 + f["C2"]) * 1e3, color=color,
                    lw=1.2, ls=(0, (4, 3)), zorder=2)
            for i, offset in ((0, (-10, -15)), (1, (-10, 7))):
                ax.plot(s["Z"][i] * 1e4, s["Y"][i] * 1e3, ls="none", marker="o",
                        ms=11, mfc="none", mec=INK2, mew=0.9, zorder=5)
                ax.annotate(s["exp"][i], (s["Z"][i] * 1e4, s["Y"][i] * 1e3),
                            xytext=offset, textcoords="offset points",
                            fontsize=8, color=INK2, ha="right")
            extra = [Line2D([0], [0], color=color, lw=1.2, ls=(0, (4, 3)),
                            label="Fría 150 sin 111 ni 112a (8 puntos)")]
            lines.append(f"Fría 150 L/h sin 111 ni 112a: y = {f['m'] / 10:.3f}x + "
                         f"{f['C2'] * 1e3:.2f} (R² = {f['R2']:.2f})".replace(".", ","))
        ax.set_ylim(*ylim)
        ax.xaxis.set_major_formatter(fmt_es(0))
        ax.yaxis.set_major_formatter(fmt_es(1))
        ax.set_xlabel(r"$\mathrm{Re}^{-0{,}8}\times 10^{4}$", fontsize=9.5)
        ax.set_ylabel(r"$1/UA\times 10^{3}$ (K/W)", fontsize=9.5)
        ax.set_title(title, fontsize=11, fontweight="bold", color=INK, pad=26)
        leg = ax.legend(handles=series_handles(keys, extra), loc="lower center",
                        bbox_to_anchor=(0.5, 1.0), ncol=3, frameon=False,
                        fontsize=8.8, handlelength=2.2, columnspacing=1.4)
        for t in leg.get_texts():
            t.set_color(INK2)
        ax.text(0.0, -0.22, "\n".join(lines), transform=ax.transAxes,
                fontsize=7.9, color=MUTED, ha="left", va="top", linespacing=1.4)
    fig.savefig(out / "fig4_wilson.png", facecolor=SURFACE)
    plt.close(fig)


def fig_hi_rf(data, der, out):
    fig, axes = plt.subplots(2, 1, figsize=(6.7, 8.4), dpi=220)
    fig.subplots_adjust(left=0.13, right=0.975, top=0.885, bottom=0.125,
                        hspace=0.70)
    c150 = SERIES["INT1 f150"][3]
    # (a) paridad hW frente a hST
    ax = axes[0]
    style_axes(ax)
    ax.grid(axis="x", color=GRID, linewidth=0.8)
    lims = np.array([1500, 30000])
    ax.plot(lims, lims, color="#a9a79e", lw=1.0, zorder=1)
    ax.plot(lims, 0.5 * lims, color=BASE, lw=0.9, zorder=1)
    ax.text(1600, 3000, r"$h_i^{\mathrm{W}} = h_{i,\mathrm{ST}}$", fontsize=8.8,
            color=MUTED, ha="left", va="bottom")
    ax.text(29000, 9000, r"$h_i^{\mathrm{W}} = 0{,}5\,h_{i,\mathrm{ST}}$",
            fontsize=8.8, color=MUTED, ha="right", va="top")
    for key in ORDER:
        s, d = data[key], der[key]
        _, _, label, color, marker = SERIES[key]
        ax.plot(s["hST"], d["hW"], ls="none", marker=marker, ms=6.5, mfc=color,
                mec=SURFACE, mew=1.2, zorder=4)
    s, d = data["INT1 f150"], der["INT1 f150 8p"]
    ax.plot(s["hST"], d["hW"], ls="none", marker="o", ms=6.2, mfc=SURFACE,
            mec=c150, mew=1.3, zorder=3)
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlim(*lims)
    ax.set_ylim(900, 30000)
    ticks = [1000, 2000, 5000, 10000, 20000]
    ax.set_xticks(ticks[1:])
    ax.set_yticks(ticks)
    ax.xaxis.set_major_formatter(fmt_es(0))
    ax.yaxis.set_major_formatter(fmt_es(0))
    ax.xaxis.set_minor_formatter(FuncFormatter(lambda v, p: ""))
    ax.yaxis.set_minor_formatter(FuncFormatter(lambda v, p: ""))
    ax.tick_params(which="minor", length=0)
    ax.set_xlabel(r"$h_{i,\mathrm{ST}}$ Sieder-Tate (W/(m$^2$·K))", fontsize=9.5)
    ax.set_ylabel(r"$h_i^{\mathrm{W}}$ Wilson (W/(m$^2$·K))", fontsize=9.5)
    ax.set_title("(a) Coeficiente individual: Wilson frente a Sieder-Tate",
                 fontsize=10.5, fontweight="bold", color=INK, pad=40)
    extra = [Line2D([0], [0], ls="none", marker="o", ms=6.2, mfc=SURFACE,
                    mec=c150, mew=1.3, label="INT 1, fría 150 (8 puntos)")]
    leg = ax.legend(handles=series_handles(ORDER, extra), loc="lower center",
                    bbox_to_anchor=(0.5, 1.0), ncol=3, frameon=False, fontsize=8.6,
                    handlelength=2.0, columnspacing=1.2)
    for t in leg.get_texts():
        t.set_color(INK2)
    # (b) Rf frente al caudal caliente
    ax = axes[1]
    style_axes(ax)
    ax.axhspan(1, 10, color=BAND, zorder=0, lw=0)
    ax.text(603, 4.38, "Valores típicos del protocolo: 1–10 × 10⁻⁴", fontsize=8.3,
            color=MUTED, va="top", ha="right")
    ax.axhline(0, color="#a9a79e", lw=1.0, zorder=1)
    for key in ORDER:
        s, d = data[key], der[key]
        plot_series(ax, s["Vc"], d["Rf"] * 1e4, key)
    s, d = data["INT1 f150"], der["INT1 f150 8p"]
    plot_series(ax, s["Vc"], d["Rf"] * 1e4, "INT1 f150", lw=1.1,
                ls=(0, (4, 3)), hollow=True, ms=6.0, z=2)
    ax.set_xlim(135, 615)
    ax.set_ylim(-1.5, 4.5)
    ax.set_xticks(np.arange(150, 601, 50))
    ax.yaxis.set_major_locator(MultipleLocator(1))
    ax.yaxis.set_major_formatter(fmt_es(0))
    ax.set_xlabel("Caudal caliente (L/h)", fontsize=9.5)
    ax.set_ylabel(r"$R_f\times 10^{4}$ (m$^2$·K/W)", fontsize=9.5)
    ax.set_title("(b) Factor de ensuciamiento aparente (Ec. 11)", fontsize=10.5,
                 fontweight="bold", color=INK, pad=40)
    extra = [Line2D([0], [0], color=c150, lw=1.1, ls=(0, (4, 3)), marker="o",
                    ms=6.0, mfc=SURFACE, mec=c150, mew=1.3,
                    label="INT 1, fría 150 (8 puntos)")]
    leg = ax.legend(handles=series_handles(ORDER, extra), loc="lower center",
                    bbox_to_anchor=(0.5, 1.0), ncol=3, frameon=False, fontsize=8.6,
                    handlelength=2.2, columnspacing=1.2)
    for t in leg.get_texts():
        t.set_color(INK2)
    note(fig, "Marcadores vacíos: recta de Wilson del INT 1 (fría 150 L/h) sin los "
              "puntos 111 y 112a, como en la hoja v3009_v1. Los puntos de las dos "
              "series del INT 2 casi se superponen. El salto a 550 L/h en el INT 2 "
              "se debe al cambio de C (0,023 → 0,027) en Re = 10⁴.", y=0.008,
         width=118)
    fig.savefig(out / "fig5_hi_Rf.png", facecolor=SURFACE)
    plt.close(fig)


def fig_eps(data, out):
    fig, ax = plt.subplots(figsize=(6.7, 3.9), dpi=220)
    fig.subplots_adjust(left=0.10, right=0.975, top=0.80, bottom=0.19)
    style_axes(ax)
    for key in ORDER:
        s = data[key]
        plot_series(ax, s["Vc"], s["eps"], key)
    ax.set_xlim(135, 615)
    ax.set_ylim(0, 0.7)
    ax.set_xticks(np.arange(150, 601, 50))
    ax.yaxis.set_major_locator(MultipleLocator(0.1))
    ax.yaxis.set_major_formatter(fmt_es(1))
    ax.set_xlabel("Caudal caliente (L/h)", fontsize=9.5)
    ax.set_ylabel("Eficiencia ε", fontsize=9.5)
    header(fig, ax, "Eficiencia de los intercambiadores", series_handles(ORDER))
    note(fig, "ε = Q̇c/[Cmín·(Tc,e − Tf,e)] (Ec. 12). Caudal de agua fría en L/h.")
    fig.savefig(out / "fig6_eficiencia.png", facecolor=SURFACE)
    plt.close(fig)


# ---------------------------------------------------------------- resumen

def rng(a, fmt="{:.0f}"):
    return [fmt.format(float(np.min(a))), fmt.format(float(np.max(a)))]


def summary(data, fits, der, sens):
    out = {"wilson": fits, "sens_Qmedia": sens, "series": {}}
    for key in ORDER:
        s, d = data[key], der[key]
        out["series"][key] = dict(
            delta=rng(s["delta"], "{:.2f}"), delta_mean=float(s["delta"].mean()),
            Uo=rng(s["Uo"]), Re=rng(s["Re"]), v=rng(s["v"], "{:.2f}"),
            hST=rng(s["hST"]), hW=rng(d["hW"]), ratio=rng(d["ratio"], "{:.3f}"),
            Rf=rng(d["Rf"], "{:.3e}"), frac_in=rng(d["frac_in"] * 100, "{:.1f}"),
            ho_eq=float(d["ho_eq"]), eps=rng(s["eps"], "{:.3f}"),
            NTU=rng(d["NTU"], "{:.2f}"), Qc=rng(s["Qc"]), k=rng(s["k"], "{:.3f}"),
            Pr=rng(s["Pr13"] ** 3, "{:.2f}"),
        )
    d8 = der["INT1 f150 8p"]
    out["series"]["INT1 f150 8p"] = dict(hW=rng(d8["hW"]),
                                         ratio=rng(d8["ratio"], "{:.3f}"),
                                         Rf=rng(d8["Rf"], "{:.3e}"))
    return out


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    xlsx = Path(sys.argv[1])
    out = Path(sys.argv[2]) if len(sys.argv) > 2 else Path(__file__).resolve().parents[1] / "figuras"
    out.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update({"font.family": "DejaVu Sans",
                         "mathtext.fontset": "dejavusans",
                         "axes.unicode_minus": True})
    data = load(xlsx)
    fits = wilson(data)
    der = derived(data, fits)
    sens = sensitivity_Qmean(data)
    fig_balance(data, out)
    fig_Uo(data, out)
    fig_wilson(data, fits, out)
    fig_hi_rf(data, der, out)
    fig_eps(data, out)
    res = summary(data, fits, der, sens)
    (out / "resumen_numerico.json").write_text(json.dumps(res, indent=2, ensure_ascii=False))
    print(json.dumps(res, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
