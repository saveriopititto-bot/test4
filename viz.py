"""Grafici Plotly per l'app."""
from __future__ import annotations

import math
from typing import Sequence

import numpy as np
import plotly.graph_objects as go

from core import Design, Stats

ACCENT = "#2E6FD8"
MUTED = "#9AA3AF"
WARN = "#D9534F"


def _layout_nodes(design: Design) -> dict[int, tuple[float, float]]:
    """Posizioni dei nodi: una circonferenza per clique (griglia), isolati in fila sotto."""
    sizes = design.clique_sizes()
    pos: dict[int, tuple[float, float]] = {}
    if sizes is None:
        for i in range(design.k):
            ang = 2 * math.pi * i / max(design.k, 1)
            pos[i] = (math.cos(ang), math.sin(ang))
        return pos

    # ricostruisce le componenti dal grafo (sizes e' solo l'elenco delle taglie)
    adj: dict[int, set[int]] = {}
    for a, b in design.edges:
        adj.setdefault(a, set()).add(b)
        adj.setdefault(b, set()).add(a)
    seen: set[int] = set()
    comps: list[list[int]] = []
    for v in sorted(adj):
        if v in seen:
            continue
        comp = sorted(adj[v] | {v})
        seen.update(comp)
        comps.append(comp)
    comps.sort(key=len, reverse=True)

    radii = [0.25 + 0.06 * len(c) for c in comps]
    cell = 2 * (max(radii) if radii else 0.5) + 0.5
    ncols = max(1, math.ceil(math.sqrt(len(comps))))
    for idx, comp in enumerate(comps):
        cx, cy = (idx % ncols) * cell, -(idx // ncols) * cell
        for i, v in enumerate(comp):
            ang = 2 * math.pi * i / len(comp) + math.pi / 2
            pos[v] = (cx + radii[idx] * math.cos(ang), cy + radii[idx] * math.sin(ang))
    isolated = [v for v in range(design.k) if v not in seen]
    nrows = math.ceil(len(comps) / ncols) if comps else 0
    for i, v in enumerate(isolated):
        pos[v] = (i * 0.6, -nrows * cell)
    return pos


def graph_figure(design: Design, labels: Sequence[int]) -> go.Figure:
    pos = _layout_nodes(design)
    ex: list[float | None] = []
    ey: list[float | None] = []
    for a, b in design.edges:
        ex += [pos[a][0], pos[b][0], None]
        ey += [pos[a][1], pos[b][1], None]
    covered = {v for e in design.edges for v in e}
    big = design.k > 24
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=ex, y=ey, mode="lines", hoverinfo="skip",
                             line=dict(color="rgba(46,111,216,0.35)", width=1)))
    for nodes, colour in (([v for v in range(design.k) if v in covered], ACCENT),
                          ([v for v in range(design.k) if v not in covered], MUTED)):
        if not nodes:
            continue
        fig.add_trace(go.Scatter(
            x=[pos[v][0] for v in nodes], y=[pos[v][1] for v in nodes],
            mode="markers+text", text=[str(labels[v]) for v in nodes],
            textfont=dict(color="white", size=8 if big else 11),
            marker=dict(size=15 if big else 26, color=colour),
            hovertext=[f"numero {labels[v]}" for v in nodes], hoverinfo="text"))
    fig.update_layout(
        showlegend=False, height=420, margin=dict(l=0, r=0, t=10, b=0),
        xaxis=dict(visible=False, scaleanchor="y"), yaxis=dict(visible=False),
        plot_bgcolor="rgba(0,0,0,0)")
    return fig


def pmf_figure(stats: Stats) -> go.Figure:
    j = [i for i, p in enumerate(stats.pmf) if i >= 1 and p > 0]
    fig = go.Figure(go.Bar(
        x=j, y=[stats.pmf[i] * 100 for i in j], marker_color=ACCENT,
        hovertemplate="%{x} ambi vincenti<br>%{y:.5f}%<extra></extra>"))
    fig.update_layout(
        height=300, margin=dict(l=0, r=0, t=10, b=0),
        xaxis=dict(title="Ambi vincenti nell'estrazione", dtick=1),
        yaxis=dict(title="Probabilità (%)", type="log"))
    return fig


def frontier_figure(series: dict[str, dict[str, list]], current: tuple[float, float] | None) -> go.Figure:
    fig = go.Figure()
    for name, s in series.items():
        fig.add_trace(go.Scatter(
            x=s["cost"], y=s["p"], mode="lines+markers", name=name,
            customdata=np.column_stack([s["k"], s["edges"]]),
            hovertemplate=(name + "<br>k=%{customdata[0]} numeri, %{customdata[1]} ambi"
                           "<br>costo %{x:.2f} €<br>P(≥1 ambo) %{y:.3f}%<extra></extra>"),
            line=dict(dash="dot" if name.startswith("Coppie") else "solid")))
    if current is not None:
        fig.add_trace(go.Scatter(x=[current[0]], y=[current[1]], mode="markers", name="Scelta attuale",
                                 marker=dict(symbol="star", size=16, color=WARN,
                                             line=dict(width=1, color="white")),
                                 hoverinfo="skip"))
    fig.update_layout(
        height=420, margin=dict(l=0, r=0, t=10, b=0),
        xaxis=dict(title="Costo (€)", type="log"),
        yaxis=dict(title="P(vincere almeno un ambo) (%)"),
        legend=dict(orientation="h", y=-0.25))
    return fig


def bankroll_figure(net_path: np.ndarray, ev_per_draw: float) -> go.Figure:
    n = len(net_path)
    x = np.arange(1, n + 1)
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=x, y=np.cumsum(net_path), mode="lines", name="Saldo simulato",
                             line=dict(color=ACCENT, width=1.5)))
    fig.add_trace(go.Scatter(x=x, y=x * ev_per_draw, mode="lines", name="Tendenza attesa",
                             line=dict(color=WARN, dash="dash")))
    fig.update_layout(
        height=320, margin=dict(l=0, r=0, t=10, b=0),
        xaxis=dict(title="Estrazioni"), yaxis=dict(title="Saldo cumulato (€)"),
        legend=dict(orientation="h", y=-0.3))
    return fig
