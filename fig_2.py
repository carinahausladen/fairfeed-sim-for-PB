"""
fig_2.py — regenerate the paper's Figure 2, the results figure.

This is the single source of the paper's Figure 2. The four panels are
(a) relevant vs browsed, (b) exposure coverage, (c) non-seed votes,
(d) top-20 quality. All data comes from the shared engine in simulation.py;
only the drawing lives here.

Writes output/fig_2.png, and copies it onto ../acm/fig_results.png when the
paper folder is present, so the figure in the submission is always the one this
script produced. (Zipped without ../acm/ for the ACM package, it just skips the
copy.) Supersedes PB in the field/muenchen/1_results_figures.py, which wrote to
the pre-rename acmart-primary-2/ path and drew an older version of panels (b),(c).

Every number panels (b),(c) are cited for in the text is labelled on the figure:
median e_j = 9 (paper §Results, "seen only nine times"), the 100/98/7-8% shares
clearing the visibility floor, the 39%/5% reaching the ≈97-view perfect-equality
benchmark, and the 67%/44% cast-any lines.

    python3 fig_2.py
"""
import shutil
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.transforms as _mt

import simulation as ff

plt.rcParams.update({"figure.dpi": 120, "font.size": 11,
                     "axes.spines.top": False, "axes.spines.right": False,
                     "axes.grid": True, "grid.alpha": 0.25,
                     "axes.titlesize": 11.5, "axes.titleweight": "bold"})

C = {"fair": "#1b8e3b", "mc": "#cc4c02", "muted": "#7e7e7e", "ink": "#1a1a1a"}
FEED_COL = {"Random": "#6baed6", "Newest": "#3182bd", "Most-commented": "#08519c", "FairFeed": C["fair"]}
FEEDS = ff.FEEDS
SHORT = {"Random": "Random", "Newest": "Newest", "Most-commented": "Most-\ncomm.", "FairFeed": "FairFeed"}
P = dict(title=11.0, lbl=9.3, tick=8.4, mean=9.0, note=7.4, leg=7.6, dot_floor=40, lw_ff=3.0, lw_oth=1.9)

# panel height / width. 1.0 = square; lower = flatter, so the figure eats less
# column height in the paper. The panel letter runs into the title (see
# build_compound) rather than sitting on its own line above it.
BOX_ASPECT = 0.70
FIGSIZE = (14.5, 3.4)


def lw_for(n):
    return P["lw_ff"] if n == "FairFeed" else P["lw_oth"]


def z_for(n):
    return 6 if n == "FairFeed" else 3


def axis_ticks(ax, items, axis, span, fs=None):
    fs = fs or P["mean"]
    items = sorted(items, key=lambda t: t[0]); fig = ax.figure
    vals = [t[0] for t in items]; labs = [t[1] for t in items]
    if axis == "x":
        ax.set_xticks(vals); ax.set_xticklabels(labs, fontsize=fs); tls = ax.get_xticklabels()
    else:
        ax.set_yticks(vals); ax.set_yticklabels(labs, fontsize=fs); tls = ax.get_yticklabels()
    for tl, (v, l, col, bold) in zip(tls, items):
        tl.set_color(col); tl.set_fontweight("bold" if bold else "normal")
    i = 0; sp = 7
    while i < len(vals):
        j = i
        while j + 1 < len(vals) and vals[j + 1] - vals[j] < 0.04 * span:
            j += 1
        if j > i:
            k = j - i + 1
            for idx in range(i, j + 1):
                off = (idx - i - (k - 1) / 2) * sp
                tls[idx].set_transform(_mt.offset_copy(
                    tls[idx].get_transform(), fig=fig,
                    x=off if axis == "x" else 0, y=off if axis == "y" else 0, units="points"))
        i = j + 1


# ─────────────────────────── run the simulations ────────────────────────────
print("building universe + running simulations…")
U = ff.build_universe()
R = {n: ff.simulate_table(U, n, 42) for n in FEEDS}              # fixed budget (cross-cutting)
ENDO = {n: ff.simulate_endo(U, n, 42 + 7) for n in FEEDS}        # endogenous browsing (panels a, b)
QF, Q20, FIELD_Q = ff.quality_bars(U)                            # top-20 quality (panel d)


# ───────────────────────────── panel builders ───────────────────────────────
def composition_panel(ax):
    from matplotlib.patches import Patch
    # density computed over the full range (cap), but the axis is cut at YCUT for a clearer bulk —
    # the sparse upper tail (mostly FairFeed, ~6% above 12) just runs off the top, no clip pile-up.
    cap, YCUT = 16, 12; edges = np.arange(0, cap + 2) - 0.5; centers = np.arange(0, cap + 1)
    smooth = lambda h: np.convolve(h, [0.25, 0.5, 0.25], mode="same")
    dens = {(n, k): smooth(np.histogram(np.clip(ENDO[n][k], 0, cap), bins=edges, density=True)[0])
            for n in FEEDS for k in ("rel_seen", "browsed")}
    W = 0.42 / max(h.max() for h in dens.values())
    for i, n in enumerate(FEEDS):
        ff_ = n == "FairFeed"
        hr, hb = dens[(n, "rel_seen")], dens[(n, "browsed")]
        ax.fill_betweenx(centers, i - hr * W, i, color=FEED_COL[n], alpha=0.75, lw=0, zorder=3)
        ax.fill_betweenx(centers, i, i + hb * W, facecolor=FEED_COL[n], alpha=0.28,
                         hatch="////", edgecolor=FEED_COL[n], lw=0, zorder=3)
        ax.plot([i, i], [0, YCUT], color="white", lw=0.8, zorder=4)
        mr, mb = ENDO[n]["rel_seen"].mean(), ENDO[n]["browsed"].mean()
        ax.hlines(mr, i - 0.36, i, color=C["ink"], lw=1.3, zorder=5)
        ax.hlines(mb, i, i + 0.36, color=C["ink"], lw=1.3, zorder=5)
        ax.text(i - 0.40, mr, f"{mr:.1f}", ha="right", va="center", fontsize=P["mean"],
                color=FEED_COL[n], fontweight="bold" if ff_ else "normal", zorder=6)
        ax.text(i + 0.40, mb, f"{mb:.1f}", ha="left", va="center", fontsize=P["mean"],
                color=FEED_COL[n], fontweight="bold" if ff_ else "normal", zorder=6)
    ax.set_xticks(range(4)); ax.set_xticklabels([SHORT[n] for n in FEEDS], fontsize=P["tick"])
    for n, lab in zip(FEEDS, ax.get_xticklabels()):   # each feed name in its own colour (no bold)
        lab.set_color(FEED_COL[n])
    ax.tick_params(labelsize=P["tick"]); ax.set_xlim(-0.7, 3.7); ax.set_ylim(0, YCUT)
    ax.legend(handles=[Patch(facecolor=C["muted"], alpha=0.75, label="relevant (left)"),
                       Patch(facecolor=C["muted"], alpha=0.3, hatch="////", label="browsed (right)")],
              loc="upper center", fontsize=P["leg"], framealpha=0.9, handlelength=1.2, ncol=1)
    ax.set_ylabel("proposals per citizen", fontsize=P["lbl"])
    ax.set_title("Relevant vs browsed", fontsize=P["title"], fontweight="bold")


def ccdf_panel(ax):
    emax = 150; levels = np.arange(0, emax + 1)
    for n in FEEDS:
        e = ENDO[n]["votes"]
        ax.plot(levels, [(e >= L).mean() * 100 for L in levels],
                color=FEED_COL[n], lw=2.1, zorder=z_for(n), label=n)
    floor = max(3.0, 0.5 * ENDO["FairFeed"]["votes"].mean())
    mu_ff = ENDO["FairFeed"]["votes"].mean()
    ax.axvline(floor, color=C["fair"], ls=":", lw=1.3, zorder=2)
    ax.plot([0, mu_ff, mu_ff], [100, 100, 0], color="#444", ls=(0, (4, 2)), lw=1.3, zorder=2)
    ax.text(mu_ff + 3, 56, "perfect\nequality", fontsize=P["note"], color="#444", ha="left", va="center")
    # Shares AT the perfect-equality benchmark — the 39% / 5% the text cites. Same grammar as the
    # floor (a dot on the curve), but labelled inline: the y-axis is already carrying 0/7/8 down
    # there. FairFeed's 39% sits in clear space so it is labelled at its dot; random's 5% lands in
    # the bunch where the three other curves converge, so its label is lifted clear of them and
    # tied back to the dot by colour.
    import matplotlib.patheffects as _pe
    _halo = [_pe.withStroke(linewidth=2.2, foreground="white")]
    for n, dy, va in [("FairFeed", 0.0, "center"), ("Random", 6.0, "bottom")]:
        s = (ENDO[n]["votes"] >= mu_ff).mean() * 100
        ax.scatter(mu_ff, s, color=FEED_COL[n], s=P["dot_floor"], ec="white", lw=0.5, zorder=9)
        ax.text(mu_ff + 4, s + dy, f"{s:.0f}%", fontsize=P["note"], color=FEED_COL[n],
                fontweight="bold", ha="left", va=va, zorder=9, path_effects=_halo)
    for n in FEEDS:
        share = (ENDO[n]["votes"] >= floor).mean() * 100
        ax.scatter(floor, share, color=FEED_COL[n], s=P["dot_floor"], ec="white", lw=0.5, zorder=8)
    # short vertical at the popularity sorts' median e_j (newest & most-commented both ≈9):
    # stops at their curves (y=50). This is the "seen only nine times" the text cites.
    med_pop = float(np.median(ENDO["Newest"]["votes"]))   # most-commented is the same
    MED_BLUE = FEED_COL["Most-commented"]   # the 9 belongs to the popularity sorts → one of their blues
    ax.plot([med_pop, med_pop], [0, 50], color=MED_BLUE, ls=(0, (2, 2)), lw=1.1, zorder=2)
    ax.set_xlim(0, emax); ax.set_ylim(0, 102); ax.tick_params(labelsize=P["tick"])
    axis_ticks(ax, [(0, "0", C["ink"], False), (med_pop, f"{med_pop:.0f}", MED_BLUE, False),
                    (floor, f"{floor:.0f}", C["fair"], False),
                    (mu_ff, f"{mu_ff:.0f}", "#444", False), (150, "150", C["ink"], False)], "x", 150)
    shares = [((ENDO[n]["votes"] >= floor).mean() * 100, f'{(ENDO[n]["votes"] >= floor).mean()*100:.0f}',
               FEED_COL[n], n == "FairFeed") for n in FEEDS] + [(0, "0", C["ink"], False), (50, "50", C["ink"], False)]
    axis_ticks(ax, shares, "y", 100, fs=P["mean"] - 1.2)
    ax.set_xlabel(r"times seen  $e_j$", fontsize=P["lbl"])
    ax.set_ylabel(r"proposals reaching $\geq e_j$  (%)", fontsize=P["lbl"])
    ax.set_title(r"Coverage $e_j$", fontsize=P["title"], fontweight="bold")


def crosscut_panel(ax):
    bins = [0, 1, 2, 3, 4, 99]; labels = ["0", "1", "2", "3", "4+"]
    x = np.arange(len(labels)); w = 0.18
    for k, n in enumerate(FEEDS):
        cc = R[n]["crosscut"]
        frac = np.array([((cc >= bins[b]) & (cc < bins[b + 1])).mean() for b in range(len(labels))]) * 100
        xx = x + (k - 1.5) * w
        ax.vlines(xx, 0, frac, color=FEED_COL[n], lw=1.9, alpha=0.9, zorder=z_for(n))
        ax.scatter(xx, frac, s=34, color=FEED_COL[n], ec="none", zorder=z_for(n) + 1)
    # average share of citizens casting ANY non-seed vote (>=1): FairFeed vs every other feed.
    # These are the 67% / 44% the text cites to this panel.
    any_ff = (R["FairFeed"]["crosscut"] >= 1).mean() * 100
    others = [n for n in FEEDS if n != "FairFeed"]
    any_oth = np.mean([(R[n]["crosscut"] >= 1).mean() * 100 for n in others])
    import matplotlib.patheffects as pe
    halo = [pe.withStroke(linewidth=2.2, foreground="white")]
    ax.axhline(any_ff, color=C["fair"], lw=1.6, ls="--", zorder=7)
    ax.axhline(any_oth, color=FEED_COL["Newest"], lw=1.6, ls="--", zorder=7)
    ax.text(len(labels) - 0.55, any_ff + 1.2, f"FairFeed: {any_ff:.0f}% cast any",
            ha="right", va="bottom", fontsize=P["note"], color=C["fair"],
            fontweight="bold", zorder=8, path_effects=halo)
    ax.text(len(labels) - 0.55, any_oth + 1.2, f"other feeds: {any_oth:.0f}%",
            ha="right", va="bottom", fontsize=P["note"], color=FEED_COL["Newest"],
            fontweight="bold", zorder=8, path_effects=halo)
    ax.set_xticks(x); ax.set_xticklabels(labels, fontsize=P["tick"]); ax.tick_params(labelsize=P["tick"])
    ax.set_xlim(-0.5, len(labels) - 0.5); ax.set_ylim(0, None)
    ax.set_xlabel("non-seed votes a citizen casts", fontsize=P["lbl"])
    ax.set_ylabel("share of citizens (%)", fontsize=P["lbl"])
    ax.set_title("Non-seed votes", fontsize=P["title"], fontweight="bold")


def quality_panel(ax):
    # 20 ballot-proposal dots + mean per condition, GROUPED so each feed gets ONE slot (like panel a):
    # Most-commented and FairFeed each hold two side-by-side conditions under a single feed name.
    cols = {"Random": FEED_COL["Random"], "Newest": FEED_COL["Newest"],
            "Most-commented": FEED_COL["Most-commented"], "MC flooded": C["mc"],
            "FairFeed": "#7cc096", "FairFeed + reject": C["fair"]}   # two FairFeed greens: approve vs +reject
    # (condition, x, jitter-halfwidth, bar-halfwidth)
    items = [("Random", 0.00, 0.17, 0.24), ("Newest", 1.00, 0.17, 0.24),
             ("Most-commented", 1.78, 0.11, 0.14), ("MC flooded", 2.22, 0.11, 0.14),
             ("FairFeed", 2.78, 0.11, 0.14), ("FairFeed + reject", 3.22, 0.11, 0.14)]
    POS = {n: x for n, x, _, _ in items}
    import matplotlib.patheffects as pe
    halo = [pe.withStroke(linewidth=2.4, foreground="white")]
    jr = np.random.default_rng(0)
    ax.axhline(FIELD_Q, color=C["muted"], ls="--", lw=1.2, zorder=1)
    ax.text(-0.28, FIELD_Q - 0.02, "random pick", fontsize=P["note"],
            color=C["muted"], ha="left", va="top", path_effects=halo, zorder=6)
    for n, x, jw, bw in items:
        qv = Q20[n]; mq = QF[n]
        ax.scatter(x + jr.uniform(-jw, jw, size=len(qv)), qv, s=15, color=cols[n],
                   alpha=0.72, ec="white", lw=0.3, zorder=3)            # exactly the 20 ballot proposals
        ax.plot([x - bw, x + bw], [mq, mq], color=cols[n], lw=2.6, zorder=5)   # mean (condition colour)
    # arrows WITHIN each group: flooding-drop (live→flooded), reject-lift (approve→+reject).
    # Ink, not condition colour: an orange arrow among orange dots vanished. The condition colour is
    # already carried by the dots, the mean bar and the tick tag, so the arrow only has to show motion.
    arrow = dict(arrowstyle="-|>", color=C["ink"], lw=1.1, mutation_scale=6.5,
                 shrinkA=0, shrinkB=0, path_effects=[pe.withStroke(linewidth=2.6, foreground="white")],
                 zorder=7)
    ax.annotate("", xy=(POS["MC flooded"] - 0.15, QF["MC flooded"]),
                xytext=(POS["Most-commented"] + 0.15, QF["Most-commented"]), arrowprops=arrow)
    ax.annotate("", xy=(POS["FairFeed + reject"] - 0.15, QF["FairFeed + reject"]),
                xytext=(POS["FairFeed"] + 0.15, QF["FairFeed"]), arrowprops=arrow)
    # major x-ticks = the four feed names (one slot each); minor = the within-group condition tags
    ax.set_xticks([0, 1, 2, 3])
    ax.set_xticklabels(["Random", "Newest", "Most-\ncomm.", "FairFeed"], fontsize=P["tick"])
    for col, lab in zip([cols["Random"], cols["Newest"], cols["Most-commented"], C["fair"]],
                        ax.get_xticklabels()):
        lab.set_color(col)
    # only the VARIANT halves get a tag (the base half is implied by the feed name); smaller font
    ax.set_xticks([2.22, 3.22], minor=True)
    ax.set_xticklabels(["flooded", "+reject"], minor=True, fontsize=P["tick"] - 2.6)
    for col, lab in zip([C["mc"], C["fair"]], ax.get_xticklabels(minor=True)):
        lab.set_color(col)
    ax.tick_params(axis="x", which="major", length=0, pad=16)
    ax.tick_params(axis="x", which="minor", length=0, pad=2)
    ax.set_ylim(0, 1.02); ax.set_xlim(-0.42, 3.66)
    # means become colour-keyed y-ticks — placed EXACTLY at their value (no offset, so each label sits on
    # its own tick mark / gridline and lines up with the mean bar it reads off)
    yt = [(0.0, "0", C["ink"]), (QF["MC flooded"], f'{QF["MC flooded"]:.2f}', C["mc"]),
          (FIELD_Q, f"{FIELD_Q:.2f}", C["muted"]),
          (QF["Most-commented"], f'{QF["Most-commented"]:.2f}', FEED_COL["Most-commented"]),
          (QF["FairFeed + reject"], f'{QF["FairFeed + reject"]:.2f}', C["fair"]),
          (0.6, "0.6", C["ink"]), (0.8, "0.8", C["ink"]), (1.0, "1.0", C["ink"])]
    ax.set_yticks([v for v, _, _ in yt])
    ax.set_yticklabels([l for _, l, _ in yt], fontsize=P["tick"] - 2.0)
    for lab, (v, l, c) in zip(ax.get_yticklabels(), yt):
        lab.set_color(c)
    ax.grid(axis="x", alpha=0)
    ax.set_ylabel("quality q", fontsize=P["lbl"])
    ax.set_title("Top-20 quality q", fontsize=P["title"], fontweight="bold")


def build_compound(figsize, suptitle=True, box_aspect=BOX_ASPECT):
    fig = plt.figure(figsize=figsize)
    gs = fig.add_gridspec(1, 4, wspace=0.32)
    cells = [gs[0, 0], gs[0, 1], gs[0, 2], gs[0, 3]]
    builders = [composition_panel, ccdf_panel, crosscut_panel, quality_panel]
    for cell, build_panel, letter in zip(cells, builders, "abcd"):
        ax = fig.add_subplot(cell); build_panel(ax); ax.set_box_aspect(box_aspect)
        head = ax.get_title()
        ax.set_title("")
        ax.set_title(f"({letter})  {head}", loc="left", fontsize=P["title"],
                     fontweight="bold", pad=4)
    # no shared legend: panel (a)'s colour-coded feed names are the colour key for (b),(c); the
    # panel-specific keys (relevant/browsed, perfect equality) live inside their own panels.
    if suptitle:
        fig.suptitle("FairFeed — Results, in one figure  (all feeds, shared seed; FairFeed in green)",
                     fontsize=13, fontweight="bold", y=1.04)
    return fig


HERE = Path(__file__).resolve().parent
OUT = HERE / "output" / "fig_2.png"
PAPER_PNG = HERE.parent / "acm" / "fig_results.png"   # the submission's copy; skipped if absent
OUT.parent.mkdir(exist_ok=True)
fig = build_compound((14.5, 4.4), suptitle=False)
fig.savefig(OUT, dpi=350, bbox_inches="tight", facecolor="white")
plt.close(fig)
print(f"wrote {OUT}")
if PAPER_PNG.parent.is_dir():
    shutil.copyfile(OUT, PAPER_PNG)
    print(f"wrote {PAPER_PNG}  (paper's Figure 2)")
else:
    print(f"skipped {PAPER_PNG} (no paper folder — standalone package)")
print("  panel-d quality: " + ", ".join(f"{n} {QF[n]:.2f}" for n in QF))
print(f"  panel-b cited: median e_j = {np.median(ENDO['Newest']['votes']):.0f}, "
      + ", ".join(f"{n} {(ENDO[n]['votes'] >= max(3.0, 0.5*ENDO['FairFeed']['votes'].mean())).mean()*100:.0f}%"
                  for n in FEEDS))
print(f"  panel-c cited: FairFeed {(R['FairFeed']['crosscut'] >= 1).mean()*100:.0f}% cast any, "
      f"other feeds {np.mean([(R[n]['crosscut'] >= 1).mean()*100 for n in FEEDS if n != 'FairFeed']):.0f}%")
