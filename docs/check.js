/* check.js — does the browser engine reproduce the paper?
 *
 * Runs sim.js under Node at the paper's settings, averages over voter seeds,
 * and prints each number next to the value in the paper (paper_numbers.py).
 *
 *     node docs/check.js
 */
const fs = require("fs");
const path = require("path");
const FF = require("./sim.js");

const U = FF.loadUniverse(JSON.parse(fs.readFileSync(path.join(__dirname, "universe.json"))));
const SETTINGS = { params: {}, reject: FF.PAPER_REJECT, nFlood: FF.PAPER_FLOOD };
const SEEDS = [1, 2, 3, 4];
const Q_SEEDS = Array.from({ length: 12 }, (_, i) => 101 + i);
const NAMES = { random: "Random", newest: "Newest", mc: "Most-commented", fair: "FairFeed" };

const avg = (xs) => xs.reduce((a, b) => a + b, 0) / xs.length;
const pct = (x) => `${(100 * x).toFixed(0)}%`;
const line = (label, got, paper) => console.log(`  ${label.padEnd(40)} js = ${String(got).padEnd(9)} paper: ${paper}`);
const t0 = Date.now();

console.log("\n(a) browsing responds to relevance, mean over 4 seeds");
const D = {};
for (const f of FF.FEEDS) D[f] = SEEDS.map((s) => FF.discovery(U, f, SETTINGS, s));
for (const f of FF.FEEDS) line(`browsed, ${NAMES[f]}`, avg(D[f].map((d) => d.browsed)).toFixed(2), { random: "3.5", newest: "3.6", mc: "3.8", fair: "5.2" }[f]);
line("on-topic seen, FairFeed", avg(D.fair.map((d) => d.rel)).toFixed(2), "5.2");
line("on-topic seen, other feeds", avg(["random", "newest", "mc"].flatMap((f) => D[f].map((d) => d.rel))).toFixed(2), "≈0.3");

console.log("\n(b) exposure");
const mu = avg(D.fair.map((d) => FF.mean(d.votes))), floor = Math.max(3, mu / 2);
line("perfect-equality views ē", mu.toFixed(1), "≈97");
line("visibility floor ē/2", floor.toFixed(1), "≈49");
for (const f of ["newest", "mc"]) line(`median views, ${NAMES[f]}`, avg(D[f].map((d) => FF.median(d.votes))).toFixed(1), "9");
for (const f of FF.FEEDS) line(`clears floor, ${NAMES[f]}`, pct(avg(D[f].map((d) => FF.shareAtLeast(d.votes, floor)))), { random: "98%", newest: "8%", mc: "7%", fair: "100%" }[f]);
for (const f of ["fair", "random"]) line(`reaches ē, ${NAMES[f]}`, pct(avg(D[f].map((d) => FF.shareAtLeast(d.votes, mu)))), { random: "5%", fair: "39%" }[f]);

console.log("\n(c) fixed browse budget, mean over 4 seeds");
const C = {};
for (const f of FF.FEEDS) C[f] = SEEDS.map((s) => FF.support(U, f, SETTINGS, s));
for (const f of FF.FEEDS) line(`non-seed votes per citizen, ${NAMES[f]}`, avg(C[f].map((c) => c.crossMean)).toFixed(2), f === "fair" ? "1.41" : "≈0.7");
line("cast ≥1 non-seed vote, FairFeed", pct(avg(C.fair.map((c) => c.crossAny))), "67%");
line("cast ≥1 non-seed vote, other feeds", pct(avg(["random", "newest", "mc"].flatMap((f) => C[f].map((c) => c.crossAny)))), "≈44%");
line("fit ≥ 0.5, FairFeed", pct(avg(C.fair.map((c) => c.wsa))), "35%");
line("fit ≥ 0.5, Most-commented", pct(avg(C.mc.map((c) => c.wsa))), "12%");

console.log("\n(d) top-20 quality, mean over 12 seeds");
const Q = {};
for (const v of FF.QUALITY_VARIANTS) Q[v.key] = avg(Q_SEEDS.map((s) => FF.quality(U, v, SETTINGS, s).qMean));
const paperQ = { random: "0.36", newest: "0.35", mc: "0.35", mcFlood: "0.27", fair: "0.41", fairReject: "0.48" };
for (const v of FF.QUALITY_VARIANTS) line(`quality, ${v.key}`, Q[v.key].toFixed(3), paperQ[v.key]);
line("reject lift at r̄ = 0.10", `+${(100 * (Q.fairReject / Q.fair - 1)).toFixed(0)}%`, "+18%");
const knee = avg(Q_SEEDS.map((s) => FF.quality(U, { feed: "fair" }, SETTINGS, s, 0.3).qMean));
line("reject lift at r̄ = 0.30 (knee)", `+${(100 * (knee / Q.fair - 1)).toFixed(0)}%`, "+32%");

console.log(`\ndone in ${((Date.now() - t0) / 1000).toFixed(1)} s`);
