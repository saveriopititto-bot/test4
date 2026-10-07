"""Grafici Plotly per l'app."""
from __future__ import annotations

import math
from typing import Sequence

import numpy as np
import plotly.graph_objects as go

from core import Design, Stats

# palette 1a
DEEP = "#023047"        # deep space blue
ACCENT = "#219EBC"      # blue green
SKY = "#8ECAE6"         # sky blue light
AMBER = "#FFB703"       # amber flame
WARN = "#FB8500"        # princeton orange
MUTED = "#7C9FB2"
GRID = "#E2EEF4"
TICK = "#3A5F74"
NODE_BG = "#F2F8FB"

FRONTIER_COLORS = [DEEP, ACCENT, SKY, AMBER]


def _base_layout(fig: go.Figure, **kw) -> go.Figure:
    """Sfondo trasparente, font Archivo, griglia tenue e niente linee d'asse."""
    axis = dict(gridcolor=GRID, zeroline=False, showline=False, tickfont=dict(color=TICK, size=12),
                title_font=dict(color=TICK, size=12))
    fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                      font=dict(family="Archivo, sans-serif", color=DEEP),
                      hoverlabel=dict(bgcolor="#fff", bordercolor=GRID, font=dict(family="Archivo", color=DEEP)),
                      **kw)
    fig.update_xaxes(**axis)
    fig.update_yaxes(**axis)
    return fig


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
                             line=dict(color="rgba(33,158,188,0.45)", width=1.2)))
    for nodes, colour in (([v for v in range(design.k) if v in covered], DEEP),
                          ([v for v in range(design.k) if v not in covered], MUTED)):
        if not nodes:
            continue
        fig.add_trace(go.Scatter(
            x=[pos[v][0] for v in nodes], y=[pos[v][1] for v in nodes],
            mode="markers+text", text=[str(labels[v]) for v in nodes],
            textfont=dict(color="white", size=8 if big else 11),
            marker=dict(size=18 if big else 28, color=colour, line=dict(width=0)),
            hovertext=[f"numero {labels[v]}" for v in nodes], hoverinfo="text"))
    _base_layout(fig, showlegend=False, height=360, margin=dict(l=20, r=20, t=20, b=20))
    fig.update_layout(xaxis=dict(visible=False, scaleanchor="y"), yaxis=dict(visible=False))
    return fig


def pmf_figure(stats: Stats) -> go.Figure:
    j = [i for i, p in enumerate(stats.pmf) if i >= 1 and p > 0]
    fig = go.Figure(go.Bar(
        x=j, y=[stats.pmf[i] * 100 for i in j], marker_color=ACCENT, marker_cornerradius=6,
        hovertemplate="%{x} ambi vincenti<br>%{y:.5f}%<extra></extra>"))
    _base_layout(fig, height=300, margin=dict(l=0, r=0, t=10, b=0))
    fig.update_layout(
        xaxis=dict(title="Ambi vincenti nell'estrazione", dtick=1),
        yaxis=dict(title="Probabilità (%)", type="log"))
    return fig


def frontier_figure(series: dict[str, dict[str, list]], current: tuple[float, float] | None) -> go.Figure:
    fig = go.Figure()
    for i, (name, s) in enumerate(series.items()):
        disjoint = name.startswith("Coppie")
        fig.add_trace(go.Scatter(
            x=s["cost"], y=s["p"], mode="lines", name=name,
            customdata=np.column_stack([s["k"], s["edges"]]),
            hovertemplate=(name + "<br>k=%{customdata[0]} numeri, %{customdata[1]} ambi"
                           "<br>costo %{x:.2f} €<br>P(≥1 ambo) %{y:.3f}%<extra></extra>"),
            line=dict(width=2.5,
                      color=WARN if disjoint else FRONTIER_COLORS[i % len(FRONTIER_COLORS)],
                      dash="dash" if disjoint else "solid")))
    if current is not None:
        fig.add_trace(go.Scatter(x=[current[0]], y=[current[1]], mode="markers", name="Scelta attuale",
                                 marker=dict(symbol="circle", size=16, color=WARN,
                                             line=dict(width=3, color="white")),
                                 hoverinfo="skip"))
    _base_layout(fig, height=400, margin=dict(l=0, r=0, t=10, b=0))
    fig.update_layout(
        xaxis=dict(title="Costo (€, log)", type="log", showgrid=False),
        yaxis=dict(title="P(≥1 ambo) %", ticksuffix="%"),
        legend=dict(orientation="v", x=1.02, xanchor="left", y=1, bgcolor=NODE_BG, font=dict(size=13)))
    return fig


def bankroll_figure(net_path: np.ndarray, ev_per_draw: float) -> go.Figure:
    n = len(net_path)
    x = np.arange(1, n + 1)
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=x, y=np.cumsum(net_path), mode="lines", name="Saldo simulato",
                             line=dict(color=ACCENT, width=2)))
    fig.add_trace(go.Scatter(x=x, y=x * ev_per_draw, mode="lines", name="Tendenza attesa",
                             line=dict(color=WARN, dash="dash", width=2.5)))
    fig.add_hline(y=0, line=dict(color="#A5C2D1", width=1.5))
    _base_layout(fig, height=320, margin=dict(l=0, r=0, t=10, b=0))
    fig.update_layout(
        xaxis=dict(title="Estrazioni", showgrid=False), yaxis=dict(title="Saldo cumulato (€)", ticksuffix=" €"),
        legend=dict(orientation="h", x=0, y=1.12, font=dict(size=13)))
    return fig
