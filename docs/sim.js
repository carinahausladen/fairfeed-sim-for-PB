/* sim.js — the FairFeed participatory-budgeting simulation, in the browser.
 *
 * A port of ../simulation.py. Same model, same universe: universe.json is
 * exported from build_universe(seed=42) by export_universe.py, so the 459
 * proposals and 7,134 voters are identical to the paper's. The voters' random
 * draws are not (JavaScript has no numpy PCG64), so a single run differs from
 * Python by noise; seed averages agree (check.js).
 *
 * One engine covers the three Python loops through options:
 *   simulate_table  →  { browse: "fixed", mcJitter: false }
 *   simulate_endo   →  { browse: "endo",  comments: false, mcJitter: false }
 *   simulate_net    →  { browse: "fixed", mcJitter: true, reject, nFlood }
 * Works as a <script>, in a Web Worker (importScripts), and in Node (require).
 */
(function (root) {
  "use strict";

  // paper constants (simulation.py, top of file)
  const PAPER = {
    beta: 5, lambda: 0.5, k: 0.15,            // fit slope, divisiveness discount, position decay
    commentBase: 0.04, off: 0.3,              // base commenting rate, m_ij for an off-topic card
    engAlpha: 0.6, b0: 0.5, bR: 4.0, bF: 0.05, maxScroll: 80,   // Eq. "continue past rank r"
    floodAmt: 120, boost: 0.5, wr: 1.5, unlock: 2,              // flood size, FairFeed b, w_r, D21 gate
  };
  const PAPER_REJECT = 0.10, PAPER_FLOOD = 5;

  // sfc32 seeded through splitmix32: small, fast, good enough for Monte Carlo
  function makeRng(seed) {
    let s = seed >>> 0;
    const sm = () => {
      s = (s + 0x9e3779b9) >>> 0;
      let z = s;
      z = Math.imul(z ^ (z >>> 16), 0x85ebca6b);
      z = Math.imul(z ^ (z >>> 13), 0xc2b2ae35);
      return (z ^ (z >>> 16)) >>> 0;
    };
    let a = sm(), b = sm(), c = sm(), d = sm();
    return function () {
      a >>>= 0; b >>>= 0; c >>>= 0; d >>>= 0;
      let t = (a + b) | 0;
      a = b ^ (b >>> 9);
      b = (c + (c << 3)) | 0;
      c = (c << 21) | (c >>> 11);
      d = (d + 1) | 0;
      t = (t + d) | 0;
      c = (c + t) | 0;
      return (t >>> 0) / 4294967296;
    };
  }

  const sigmoid = (x) => 1 / (1 + Math.exp(-x));

  function loadUniverse(j) {
    const U = {
      M: j.M, N: j.N, C: j.C, nWin: j.nWin, nVet: j.nVet,
      cats: Int32Array.from(j.cats), q: Float64Array.from(j.q), xi: Float64Array.from(j.xi),
      tsub: Float64Array.from(j.tsub), kappa: Float64Array.from(j.kappa),
      seeds: Int32Array.from(j.seeds), budgets: Int32Array.from(j.budgets),
      tau: Float64Array.from(j.tau), order: Int32Array.from(j.order),
    };
    // numpy's tie order for equal comment counts (see export_universe.py); < 1 so it only breaks ties
    U.tieBreak = Float64Array.from(j.tieRank || j.cats.map((_, i) => i), (r) => -r * 1e-6);
    U.byQ = Int32Array.from(Array.from(U.q.keys()).sort((a, b) => U.q[b] - U.q[a]));   // best first
    U.fieldQ = mean(U.q);
    U.bestQ20 = mean(Array.from(U.byQ.slice(0, 20), (i) => U.q[i]));
    return U;
  }

  // indices of the k highest scores, best first; ties keep index order (stable)
  function topK(score, k, out, M) {
    let n = 0;
    for (let j = 0; j < M; j++) {
      const v = score[j];
      if (n < k) {
        let p = n++;
        while (p > 0 && score[out[p - 1]] < v) { out[p] = out[p - 1]; p--; }
        out[p] = j;
      } else if (v > score[out[k - 1]]) {
        let p = k - 1;
        while (p > 0 && score[out[p - 1]] < v) { out[p] = out[p - 1]; p--; }
        out[p] = j;
      }
    }
    return n;
  }

  /* createSim(U, opts, seed) → a stepper. Voters arrive in U.order; step(n)
   * lets the next n of them browse. opts.feed ∈ random | newest | mc | fair. */
  function createSim(U, opts, seed) {
    const p = Object.assign({}, PAPER,
      { feed: "fair", browse: "fixed", reject: 0, nFlood: 0, mcJitter: true, comments: true }, opts);
    const M = U.M, N = U.N, rnd = makeRng(seed);
    const endo = p.browse === "endo", ron = p.reject > 0, off = p.off;

    const sup = new Int32Array(M), com = new Int32Array(M), vot = new Int32Array(M), dn = new Int32Array(M);
    for (let t = 0; t < p.nFlood; t++) com[U.byQ[M - 1 - t]] = p.floodAmt;   // the weakest proposals
    const cross = new Int32Array(N), browsed = new Int32Array(N), rel = new Int32Array(N);
    const score = new Float64Array(M), perm = Int32Array.from({ length: M }, (_, i) => i);
    const feed = new Int32Array(Math.max(p.maxScroll, 50));
    let t = 0, vsum = 0, dmax = 0, fitN = 0, fitHi = 0;

    function buildFeed(s, V) {
      V = Math.min(V, M);
      if (p.feed === "random") {                       // V distinct proposals, uniformly
        for (let a = 0; a < V; a++) {
          const b = a + Math.floor(rnd() * (M - a));
          const x = perm[a]; perm[a] = perm[b]; perm[b] = x;
          feed[a] = perm[a];
        }
        return V;
      }
      if (p.feed === "newest") {
        for (let j = 0; j < M; j++) score[j] = U.tsub[j] + rnd() * 1e-6;
      } else if (p.feed === "mc") {
        if (p.mcJitter) for (let j = 0; j < M; j++) score[j] = com[j] + rnd() * 1e-6;
        else for (let j = 0; j < M; j++) score[j] = com[j] + U.tieBreak[j];
      } else {                                         // FairFeed, Eq. (fairfeed)
        const cs = U.cats[s], floor = Math.max(3, 0.5 * vsum / M);
        for (let j = 0; j < M; j++) {
          let v = U.cats[j] === cs ? 1 : off;
          if (vot[j] < floor) v += p.boost;
          if (ron) v -= p.wr * dn[j] / (dmax + 1);
          score[j] = v + rnd() * 1e-6;
        }
      }
      return topK(score, V, feed, M);
    }

    function step(count) {
      const end = Math.min(N, t + count);
      for (; t < end; t++) {
        const i = U.order[t], s = U.seeds[i], tau = U.tau[i];
        sup[s]++; vot[s]++; vsum++;
        let rated = 1;
        if (p.comments && rnd() < p.commentBase * (1 + 3 * U.xi[s])) com[s]++;
        const V = endo ? p.maxScroll : U.budgets[i];
        if (V <= 0) continue;
        const n = buildFeed(s, V);
        let eng = U.q[s], nb = 0, nrel = 0;
        for (let r = 0; r < n; r++) {
          const j = feed[r];
          if (j === s) continue;
          rated++; vot[j]++; vsum++; nb++;
          const on = U.cats[j] === U.cats[s];
          if (on) nrel++;
          const qm = U.q[j] * (on ? 1 : off);
          const fit = sigmoid(p.beta * (qm - tau)), dec = 1 / (1 + p.k * r);
          if (rnd() < fit * (1 - p.lambda * U.xi[j]) * dec) {           // Eq. (support)
            sup[j]++; cross[i]++; fitN++;
            if (fit >= 0.5) fitHi++;
          } else if (ron && rated >= p.unlock && rnd() < p.reject * U.xi[j] * (1 - qm) * dec) {   // Eq. (reject)
            dn[j]++;
            if (dn[j] > dmax) dmax = dn[j];
          }
          if (p.comments && rnd() < p.commentBase * (1 + 3 * U.xi[j]) * dec) com[j]++;
          if (endo) {                                                   // Eq. (continue)
            eng = p.engAlpha * qm + (1 - p.engAlpha) * eng;
            if (rnd() >= sigmoid(p.b0 + p.bR * eng - p.bF * r)) break;
          }
        }
        browsed[i] = nb; rel[i] = nrel;
      }
      return t >= N;
    }

    // the shortlist: top 20 on net support, rejects capped at half the supports (2:1)
    function ballot(size = 20) {
      const sc = new Float64Array(M), out = new Int32Array(size);
      for (let j = 0; j < M; j++) sc[j] = ron ? sup[j] - Math.min(dn[j], 0.5 * sup[j]) : sup[j];
      topK(sc, size, out, M);
      return out;
    }

    return {
      p, sup, com, vot, dn, cross, browsed, rel, step, ballot,
      get t() { return t; },
      get wsa() { return fitN ? fitHi / fitN : 0; },      // share of non-seed supports with fit ≥ 0.5
    };
  }

  function runFull(U, opts, seed) {
    const S = createSim(U, opts, seed);
    S.step(U.N);
    return S;
  }

  // ─────────────────────────────── small stats ───────────────────────────────
  function mean(a) { let s = 0; for (let i = 0; i < a.length; i++) s += a[i]; return s / a.length; }
  function median(a) {
    const b = Float64Array.from(a).sort(), n = b.length;
    return n % 2 ? b[(n - 1) / 2] : (b[n / 2 - 1] + b[n / 2]) / 2;
  }
  function gini(a) {
    const b = Float64Array.from(a).sort(), n = b.length;
    let s = 0, tot = 0;
    for (let i = 0; i < n; i++) { s += (2 * (i + 1) - n - 1) * b[i]; tot += b[i]; }
    return tot ? s / (n * tot) : 0;
  }
  function shareAtLeast(a, x) { let c = 0; for (let i = 0; i < a.length; i++) if (a[i] >= x) c++; return c / a.length; }

  // ────────────── the paper's analyses (figure 2 panels a–d, sweep) ─────────────
  const FEEDS = ["random", "newest", "mc", "fair"];

  // panels (a), (b): browsing responds to relevance; Python simulate_endo
  function discovery(U, feed, settings, seed) {
    const S = runFull(U, Object.assign({}, settings.params,
      { feed, browse: "endo", comments: false, mcJitter: false }), seed);
    return { browsed: mean(S.browsed), rel: mean(S.rel), votes: Array.from(S.vot) };
  }

  // panel (c): fixed budget; Python simulate_table
  function support(U, feed, settings, seed) {
    const S = runFull(U, Object.assign({}, settings.params,
      { feed, browse: "fixed", mcJitter: false }), seed);
    const hist = [0, 0, 0, 0, 0];
    for (let i = 0; i < U.N; i++) hist[Math.min(S.cross[i], 4)]++;
    return { crossMean: mean(S.cross), crossAny: 1 - hist[0] / U.N, hist: hist.map((h) => h / U.N), wsa: S.wsa };
  }

  // panel (d) + sweep: fixed budget, gated reject, flooding; Python simulate_net
  const QUALITY_VARIANTS = [
    { key: "random", feed: "random" },
    { key: "newest", feed: "newest" },
    { key: "mc", feed: "mc" },
    { key: "mcFlood", feed: "mc", flood: true },
    { key: "fair", feed: "fair" },
    { key: "fairReject", feed: "fair", reject: true },
  ];
  function quality(U, variant, settings, seed, rejectOverride) {
    const S = runFull(U, Object.assign({}, settings.params, {
      feed: variant.feed, browse: "fixed", mcJitter: true,
      nFlood: variant.flood ? settings.nFlood : 0,
      reject: rejectOverride !== undefined ? rejectOverride : (variant.reject ? settings.reject : 0),
    }), seed);
    const b = S.ballot(), q = Array.from(b, (j) => U.q[j]), xi = Array.from(b, (j) => U.xi[j]);
    return { q, qMean: mean(q), xiMean: mean(xi), highXi: xi.filter((x) => x > 0.6).length };
  }

  const API = {
    PAPER, PAPER_REJECT, PAPER_FLOOD, FEEDS, QUALITY_VARIANTS,
    makeRng, loadUniverse, createSim, runFull, discovery, support, quality,
    mean, median, gini, shareAtLeast,
  };
  if (typeof module !== "undefined" && module.exports) module.exports = API;
  else root.FF = API;
})(typeof self !== "undefined" ? self : this);
