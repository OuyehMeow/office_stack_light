"""Parametric envelope model of a 1S LiPo pouch cell with PCM and lead, exported as STEP.

There is no manufacturer STEP for generic pouch cells, so this models the space the
battery needs, not the real part. Name format: TTWWLL = thickness/width/length in
0.1 mm / mm / mm, e.g. 803040 = 8.0 x 30 x 40 mm.

    pip install cadquery
    python cad/scripts/make_lipo.py                      # 803040 default
    python cad/scripts/make_lipo.py --t 6 --w 34 --l 50  # 603450

Coordinates: cell centred on X/Y, underside at Z = 0, lead exits towards +Y.
"""

import argparse
from pathlib import Path

import cadquery as cq


def build(t: float, w: float, l: float, pcm_len: float, lead_len: float) -> cq.Assembly:
    # Cell body: pouch edges are soft, approximate with fillets on the long edges.
    body = (cq.Workplane("XY").box(w, l, t, centered=(True, True, False))
            .edges("|Y").fillet(min(1.0, t / 3)))

    # Folded seal + protection board (PCM) at the lead end. Real ones: 2-5 mm long.
    pcm = (cq.Workplane("XY").box(w - 4, pcm_len, t * 0.7, centered=(True, False, False))
           .translate((0, l / 2, t * 0.15)))

    # Two 26-28 AWG leads, 1.2 mm OD, then a JST-PH 2-pin cable housing (PHR-2 ~ 6.0 x 4.5 x 6.0 mm).
    y0 = l / 2 + pcm_len
    wire = lambda x: (cq.Workplane("XZ", origin=(x, y0, t / 2)).circle(0.6)  # noqa: E731
                      .extrude(-lead_len))  # XZ normal is -Y, so negative extrude goes +Y
    leads = wire(-1.0).union(wire(1.0))
    jst = cq.Workplane("XY").box(6.0, 6.0, 4.5).translate((0, y0 + lead_len + 3.0, t / 2))

    a = cq.Assembly(name=f"lipo_{round(t*10):02d}{round(w):02d}{round(l):02d}")
    a.add(body, name="cell", color=cq.Color(0.75, 0.75, 0.78))
    a.add(pcm, name="pcm_seal", color=cq.Color(0.15, 0.35, 0.15))
    a.add(leads, name="leads", color=cq.Color(0.8, 0.1, 0.1))
    a.add(jst, name="jst_ph_2p", color=cq.Color(0.95, 0.95, 0.9))
    return a


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--t", type=float, default=8.0, help="thickness mm")
    ap.add_argument("--w", type=float, default=30.0, help="width mm")
    ap.add_argument("--l", type=float, default=40.0, help="length mm (cell only)")
    ap.add_argument("--pcm", type=float, default=3.0, help="PCM / seal length mm")
    ap.add_argument("--lead", type=float, default=50.0, help="lead length mm")
    ap.add_argument("-o", "--out", type=Path)
    a = ap.parse_args()
    name = f"lipo-{round(a.t*10):02d}{round(a.w):02d}{round(a.l):02d}"
    out = a.out or Path(__file__).resolve().parents[1] / "vendor" / "generic-lipo" / f"{name}.step"
    out.parent.mkdir(parents=True, exist_ok=True)
    build(a.t, a.w, a.l, a.pcm, a.lead).export(str(out))
    print(out)


if __name__ == "__main__":
    main()
