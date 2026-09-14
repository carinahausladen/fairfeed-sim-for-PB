/* worker.js — recomputes the paper's results panels off the main thread.
 * The page posts the current settings; the worker answers stage by stage, so
 * charts fill in progressively. A newer request cancels an older one. */
importScripts("sim.js");

let U = null, current = 0;
const pause = () => new Promise((r) => setTimeout(r, 0));
const avg = (a) => a.reduce((x, y) => x + y, 0) / a.length;

const SEEDS_AB = [1, 2], SEEDS_C = [1, 2];
const SEEDS_D = Array.from({ length: 12 }, (_, i) => 101 + i);
const LEVELS = 150;

onmessage = (e) => {
  const m = e.data;
  if (m.type === "init") { U = FF.loadUniverse(m.universe); return; }
  if (m.type === "run") {
    current = m.id;
    compute(m.id, m.settings).catch((err) => postMessage({ id: m.id, stage: "error", data: String(err) }));
  }
};

async function compute(id, S) {
  const variants = FF.QUALITY_VARIANTS.filter((v) => !(v.flood && !S.nFlood) && !(v.reject && !S.reject));
  const total = FF.FEEDS.length * (SEEDS_AB.length + SEEDS_C.length)
    + variants.length * SEEDS_D.length;
  let done = 0;
  const tick = async () => {
    done++;
    postMessage({ id, stage: "progress", data: done / total });
    await pause();
    return id === current;
  };

  // (a), (b): browsing responds to relevance
  const D = {};
  for (const f of FF.FEEDS) {
    D[f] = [];
    for (const s of SEEDS_AB) { D[f].push(FF.discovery(U, f, S, s)); if (!(await tick())) return; }
  }
  const mu = avg(D.fair.map((d) => FF.mean(d.votes))), floor = Math.max(3, mu / 2);
  const disc = { mu, floor, feeds: {} };
  for (const f of FF.FEEDS) {
    const ccdf = new Array(LEVELS + 1).fill(0);
    for (const d of D[f]) {
      const cnt = new Array(LEVELS + 2).fill(0);
      for (const v of d.votes) cnt[Math.min(v, LEVELS + 1)]++;
      let acc = 0;
      for (let L = LEVELS + 1; L >= 0; L--) {
        acc += cnt[L];
        if (L <= LEVELS) ccdf[L] += acc / U.M / D[f].length;
      }
    }
    disc.feeds[f] = {
      browsed: avg(D[f].map((d) => d.browsed)), rel: avg(D[f].map((d) => d.rel)),
      median: avg(D[f].map((d) => FF.median(d.votes))),
      clears: avg(D[f].map((d) => FF.shareAtLeast(d.votes, floor))),
      reaches: avg(D[f].map((d) => FF.shareAtLeast(d.votes, mu))), ccdf,
    };
  }
  postMessage({ id, stage: "discovery", data: disc });

  // (c): fixed browse budget
  const sup = {};
  for (const f of FF.FEEDS) {
    const rs = [];
    for (const s of SEEDS_C) { rs.push(FF.support(U, f, S, s)); if (!(await tick())) return; }
    sup[f] = {
      crossMean: avg(rs.map((r) => r.crossMean)), crossAny: avg(rs.map((r) => r.crossAny)),
      wsa: avg(rs.map((r) => r.wsa)), hist: [0, 1, 2, 3, 4].map((b) => avg(rs.map((r) => r.hist[b]))),
    };
  }
  postMessage({ id, stage: "support", data: sup });

  // (d): top-20 quality, refined seed by seed
  const acc = {};
  variants.forEach((v) => (acc[v.key] = { q: 0, xi: 0, hi: 0, q20: null }));
  for (let n = 0; n < SEEDS_D.length; n++) {
    for (const v of variants) {
      const r = FF.quality(U, v, S, SEEDS_D[n]);
      const a = acc[v.key];
      a.q += r.qMean; a.xi += r.xiMean; a.hi += r.highXi;
      if (!a.q20) a.q20 = r.q;
      if (!(await tick())) return;
    }
    const out = { seeds: n + 1, total: SEEDS_D.length, fieldQ: U.fieldQ, bestQ20: U.bestQ20, variants: {} };
    for (const v of variants) {
      const a = acc[v.key];
      out.variants[v.key] = { qMean: a.q / (n + 1), xiMean: a.xi / (n + 1), highXi: a.hi / (n + 1), q20: a.q20 };
    }
    postMessage({ id, stage: "quality", data: out });
  }

  postMessage({ id, stage: "done" });
}
