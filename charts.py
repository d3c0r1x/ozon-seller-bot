"""График выручки для /chart (PNG, тёмная тема)."""

from __future__ import annotations

import io
from datetime import date, timedelta

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

BG = "#0d1117"
TEXT = "#e6edf3"
MUTED = "#8b949e"
ACCENT = "#3fb950"
GRID = "#21262d"


def render_revenue(values: list[float], is_demo: bool = False) -> io.BytesIO:
    """Столбчатая диаграмма выручки по последним дням, даты — по дням назад."""
    days = len(values)
    labels = [
        (date.today() - timedelta(days=days - 1 - i)).strftime("%d.%m")
        for i in range(days)
    ]

    fig, ax = plt.subplots(figsize=(9, 4.6), dpi=120)
    fig.patch.set_facecolor(BG)
    ax.set_facecolor(BG)

    bars = ax.bar(labels, values, color=ACCENT, width=0.62, zorder=3)
    best = max(values)
    for bar, v in zip(bars, values):
        if v == best:
            bar.set_color("#56d364")

    ax.grid(axis="y", color=GRID, linewidth=0.8, zorder=0)
    ax.spines[["top", "right"]].set_visible(False)
    ax.spines[["left", "bottom"]].set_color(MUTED)
    ax.tick_params(colors=MUTED, labelsize=8.5)
    ax.set_title(
        "Выручка за 14 дней" + (" (демо-данные)" if is_demo else ""),
        color=TEXT, fontsize=13, loc="left", pad=12,
    )
    ax.yaxis.set_major_formatter(lambda x, _: f"{x:,.0f}".replace(",", " "))
    ax.margins(x=0.01)

    buf = io.BytesIO()
    fig.savefig(buf, format="png", facecolor=BG, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf
