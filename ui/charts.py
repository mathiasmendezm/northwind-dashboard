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
              vline_x=None, vline_text: str = "",
              hline_y: float | None = None, hline_text: str = "",
              yaxis_range: list | None = None, yaxis_ticksuffix: str = "",
              fill: bool = True) -> go.Figure:
    marker = dict(size=marker_size) if marker_size is not None else {}
    fig = go.Figure(go.Scatter(
        x=x, y=y, mode="lines+markers", name=name,
        line=dict(color=color, width=3), marker=marker,
        fill="tozeroy" if fill else None, fillcolor="rgba(30,64,175,0.08)"))
    if vline_x is not None:
        fig.add_vline(x=vline_x, line_dash="dot", line_color=MUTE,
                      annotation_text=vline_text, annotation_position="top left",
                      annotation_font=dict(size=10, color=MUTE))
    if hline_y is not None:
        fig.add_hline(y=hline_y, line_dash="dot", line_color=MUTE,
                      annotation_text=hline_text, annotation_position="top left",
                      annotation_font=dict(size=10, color=MUTE))
    fig.update_layout(height=height, margin=dict(l=0, r=10, t=8, b=8),
                      xaxis=dict(title=""),
                      yaxis=dict(title=yaxis_title, range=yaxis_range,
                                 ticksuffix=yaxis_ticksuffix))
    return fig


def stacked_hbar(labels: Sequence, series: dict[str, Sequence[float]],
                 colors: dict[str, str], *, height: int | None = None,
                 xaxis_title: str = "", vline_x: float | None = None,
                 vline_text: str = "", hovertemplate: str | None = None) -> go.Figure:
    fig = go.Figure()
    for name, values in series.items():
        fig.add_bar(y=labels, x=values, orientation="h", name=name,
                    marker=dict(color=colors[name]), hovertemplate=hovertemplate)
    if vline_x is not None:
        fig.add_vline(x=vline_x, line_dash="dot", line_color=MUTE,
                      annotation_text=vline_text, annotation_position="top left",
                      annotation_font=dict(size=10, color=MUTE))
    fig.update_layout(barmode="stack", height=height,
                      margin=dict(l=0, r=20, t=8, b=8),
                      legend=dict(orientation="h", y=1.08, x=0, traceorder="normal"),
                      xaxis=dict(title=xaxis_title), yaxis=dict(title=""))
    return fig


def waterfall(steps: Sequence[tuple[str, float]], *, total_color: str, leak_color: str,
              height: int | None = None) -> go.Figure:
    """First step is the starting total, last is the ending total, the rest are leaks."""
    labels = [s[0] for s in steps]
    values = [s[1] for s in steps]
    measure = ["absolute"] + ["relative"] * (len(steps) - 2) + ["total"]
    text = [f"${abs(v) / 1000:,.0f}K" if m != "relative" else f"−${abs(v) / 1000:,.1f}K"
            for v, m in zip(values, measure, strict=True)]
    fig = go.Figure(go.Waterfall(
        x=labels, y=values, measure=measure, text=text, textposition="outside",
        connector=dict(line=dict(color="#CBD5E1", width=1)),
        decreasing=dict(marker=dict(color=leak_color)),
        increasing=dict(marker=dict(color=total_color)),
        totals=dict(marker=dict(color=total_color)),
        hovertemplate="%{x}: $%{y:,.0f}<extra></extra>"))
    top = values[0] * 1.08
    fig.update_layout(height=height, margin=dict(l=0, r=0, t=16, b=8), showlegend=False,
                      yaxis=dict(title="Monthly rent ($)", range=[0, top]),
                      xaxis=dict(title=""))
    return fig


def vbar(labels: Sequence, values: Sequence[float], colors: Sequence[str], *,
         height: int | None = None, yaxis_title: str = "") -> go.Figure:
    fig = go.Figure(go.Bar(
        x=labels, y=values, marker=dict(color=colors),
        text=values, textposition="outside"))
    fig.update_layout(height=height, margin=dict(l=0, r=0, t=8, b=8),
                      yaxis=dict(title=yaxis_title), xaxis=dict(title=""))
    return fig
