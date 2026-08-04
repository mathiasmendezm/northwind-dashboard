"""Reusable Plotly Figure builders for the small set of chart shapes that
repeat across pages (horizontal bars, overlaid horizontal bars, filled line
charts, vertical bars). Pages compute their own data (groupby, sort,
threshold colors) and hand it here already shaped — this module only knows
how to draw, never what the numbers mean.
"""

from __future__ import annotations

from collections.abc import Sequence

import plotly.graph_objects as go

from ui.theme import MUTE


def hbar(labels: Sequence, values: Sequence[float], *, colors=None, text=None,
         textfont_size: int = 11,
         height: int | None = None, margin: dict | None = None,
         xaxis_title: str = "", yaxis_title: str = "", reversed_yaxis: bool = False,
         xaxis_range: list | None = None, xaxis_ticksuffix: str = "",
         vline_x: float | None = None, vline_text: str = "",
         customdata=None, hovertemplate: str | None = None) -> go.Figure:
    fig = go.Figure(go.Bar(
        x=values, y=labels, orientation="h",
        marker=dict(color=colors) if colors is not None else None,
        text=text, textposition="outside" if text is not None else None,
        textfont=dict(size=textfont_size) if text is not None else None,
        customdata=customdata, hovertemplate=hovertemplate))
    if vline_x is not None:
        fig.add_vline(x=vline_x, line_dash="dot", line_color=MUTE,
                      annotation_text=vline_text, annotation_position="top left",
                      annotation_font=dict(size=10, color=MUTE))
    yaxis = dict(title=yaxis_title)
    if reversed_yaxis:
        yaxis["autorange"] = "reversed"
    fig.update_layout(
        height=height, margin=margin or dict(l=0, r=48, t=8, b=8),
        xaxis=dict(title=xaxis_title, range=xaxis_range, ticksuffix=xaxis_ticksuffix),
        yaxis=yaxis)
    return fig


def overlay_hbar(labels: Sequence, series: dict[str, Sequence[float]],
                  colors: dict[str, str], *, height: int | None = None,
                  xaxis_title: str = "") -> go.Figure:
    fig = go.Figure()
    for name, values in series.items():
        fig.add_bar(y=labels, x=values, orientation="h", name=name,
                    marker=dict(color=colors[name]))
    fig.update_layout(barmode="overlay", height=height,
                      margin=dict(l=0, r=20, t=8, b=8),
                      legend=dict(orientation="h", y=1.06, x=0),
                      xaxis=dict(title=xaxis_title), yaxis=dict(title=""))
    return fig


def line_area(x: Sequence, y: Sequence[float], *, color: str, name: str = "",
              height: int | None = None, yaxis_title: str = "",
              marker_size: int | None = None,
              vline_x=None, vline_text: str = "") -> go.Figure:
    marker = dict(size=marker_size) if marker_size is not None else {}
    fig = go.Figure(go.Scatter(
        x=x, y=y, mode="lines+markers", name=name,
        line=dict(color=color, width=3), marker=marker,
        fill="tozeroy", fillcolor="rgba(30,64,175,0.08)"))
    if vline_x is not None:
        fig.add_vline(x=vline_x, line_dash="dot", line_color=MUTE,
                      annotation_text=vline_text, annotation_position="top left",
                      annotation_font=dict(size=10, color=MUTE))
    fig.update_layout(height=height, margin=dict(l=0, r=10, t=8, b=8),
                      xaxis=dict(title=""), yaxis=dict(title=yaxis_title))
    return fig


def vbar(labels: Sequence, values: Sequence[float], colors: Sequence[str], *,
         height: int | None = None, yaxis_title: str = "") -> go.Figure:
    fig = go.Figure(go.Bar(
        x=labels, y=values, marker=dict(color=colors),
        text=values, textposition="outside"))
    fig.update_layout(height=height, margin=dict(l=0, r=0, t=8, b=8),
                      yaxis=dict(title=yaxis_title), xaxis=dict(title=""))
    return fig
