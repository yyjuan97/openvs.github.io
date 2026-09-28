import os

import win32com.client

BASIC_STENCIL = "basic_u.vss"
CONNECTOR_STENCIL = "connec_u.vss"


def start_visio():
    """Start a new Visio application instance."""
    return win32com.client.DispatchEx("Visio.Application")


def open_stencils(visio):
    """Open basic shapes and connector stencils, return (basic_stencil, connector_stencil, masters, conn_master)."""
    basic_stencil = visio.Documents.OpenEx(BASIC_STENCIL, 64)  # visOpenRO
    connector_stencil = visio.Documents.OpenEx(CONNECTOR_STENCIL, 64)

    masters = {}
    for i in range(1, basic_stencil.Masters.Count + 1):
        m = basic_stencil.Masters(i)
        nameU = m.NameU
        if nameU == "Rectangle":
            masters["Rectangle"] = m
        elif nameU == "Diamond":
            masters["Diamond"] = m
        elif nameU == "Rounded Rectangle":
            masters["Rounded Rectangle"] = m
        elif nameU == "Ellipse":
            masters["Ellipse"] = m

    conn_master = connector_stencil.Masters.ItemU("Dynamic connector")

    return basic_stencil, connector_stencil, masters, conn_master


def close_visio(visio, doc=None, stencils=None, visible=False):
    """Close document, stencils, and quit Visio."""
    try:
        if doc:
            doc.Close()
    except Exception:
        pass
    if stencils:
        for stencil in stencils:
            try:
                stencil.Close()
            except Exception:
                pass
    if not visible:
        try:
            visio.Quit()
        except Exception:
            pass


def rgb_to_visio(rgb_color: int) -> str:
    """Convert RGB integer to Visio color formula."""
    r = rgb_color & 0xFF
    g = (rgb_color >> 8) & 0xFF
    b = (rgb_color >> 16) & 0xFF
    return f"RGB({r},{g},{b})"
