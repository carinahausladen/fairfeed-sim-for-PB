# Auditing feed sort orders across Consul Democracy participatory-budgeting deployments

*Empirical note for the FairFeed long paper. Audit conducted 2026-06-14.*

## 1. Motivation and research question

FairFeed argues that the order in which participatory-budgeting (PB) proposals are
presented is agenda-setting power, and that the orderings real platforms offer are
popularity-, recency-, or chance-based — never relevance-aware. To ground that claim
beyond a single city, we audit **Consul Democracy** (originally CONSUL, built by Madrid
in 2015), the most widely deployed open-source digital-democracy platform
(self-reported: 200+ public institutions, 35+ countries, ~100M people;
<https://consuldemocracy.org/>).

Two empirical questions:

1. **What sort orderings does each live deployment actually offer on its budget feed,
   and which is the default?**
2. **Is any deployment's ordering relevance-aware**, or are they all popularity / recency
   / chance / price?

The headline result: across **18 live deployments in 8 countries**, the default feed
ordering is **`random` in every single case**, and **no deployment offers a
relevance-aware sort**. The only orderings observed anywhere are random, most-voted,
newest, most-commented, most-active, alphabetical, and price.

## 2. How feed ordering works in Consul (source-code grounding)

Ordering is **framework code**, not a per-citizen or per-admin UI setting. Verified
against `consuldemocracy/consuldemocracy` at commit `eee533f`:

- **Budget feed** — `Budget#investments_orders` (`app/models/budget.rb`) returns a
  hardcoded list of allowed orderings, and it is **phase-dependent**:

  ```ruby
  def investments_orders
    case phase
    when "accepting", "reviewing", "finished"
      %w[random]
    when "publishing_prices", "balloting", "reviewing_ballots"
      hide_money? ? %w[random] : %w[random price]
    else                                   # selecting / valuating
      %w[random confidence_score]
    end
  end
  ```

- **Default selection** — the `HasOrders` concern
  (`app/controllers/concerns/has_orders.rb`) picks the URL's `?order=` value if valid,
  otherwise the **first element of the list**:

  ```ruby
  @current_order = @valid_orders.include?(params[:order]) ? params[:order] : @valid_orders.first
  ```

  Since `random` is first in every branch, the **out-of-the-box default is `random`**.

- **`confidence_score`** (`app/lib/score_calculator.rb`) is `(up − down) · (up/total) · 100`;
  for support-only budget ballots this reduces to a popularity count. The
  **proposals/debates feed** (`Proposal.proposals_orders`) is a different, richer menu
  (`hot_score`, `confidence_score`, `created_at`, `relevance`, `archival_date`); the PB
  module uses the *budget* feed above.

**Two consequences that shaped the audit:**

1. **Phase-dependence.** A deployment caught mid-**ballot** renders only `random`
   (`+ price` if money is shown) — *by design*, as an anti-bias choice for the binding
   vote. The fuller popularity/recency menu only appears in the earlier
   **selecting/accepting** phases. So "random only" in the table below usually reflects
   *phase*, not a deployment that offers nothing else.

2. **Forks are unreliable as evidence.** The public Munich fork
   (`it-at-m/consul-lhm-dev`, even its deployed `cli_muc` branch, last commit 2023-10-26)
   shows the stock `random / confidence_score / price` set — but Munich's **live** site
   shows `random / newest / most-commented`. The real customization was never pushed to
   the public mirror, and GitHub code-search does not index forks. **Therefore the only
   reliable evidence of what a deployment offers is its live HTML, not its repository.**

## 3. Method

### 3.1 Enumeration (finding deployments)

There is **no authoritative machine-readable registry**, and "200+ institutions" counts
*any* Consul use (proposals, debates, consultations) — only a subset run a *budget* feed.
We enumerated candidates from:

- the demokratie.today German municipal cluster (from our sibling report
  `PB in the field/demokratie_today_buergerbudget/`);
- `consuldemocracy.org` (users / world map) and
  `consul.mehr-demokratie.info/consulprojekte`;
- web search per region ("Consul presupuestos participativos" / "orçamento participativo
  Consul" / "Consul participatory budgeting" + city/country);
- known hosting clusters discovered during the audit: `*.communitychoices.scot`
  (Scotland), the `djnd.si` cluster (Slovenia), `*.consul.ellak.gr` (Greece/GFOSS).

We split the work across three regional passes (Spain; Latin America/Brazil/Portugal;
rest-of-world) plus the already-completed German cluster.

### 3.2 Locating the budget feed

For each domain, candidate paths: `/budgets`, `/presupuestos`, `/orcamentos`, a named
landing (e.g. `/buergerbudget`, `/gruenes-buergerbudget`), or the investments index
`/budgets/<id>/investments`. The investments index frequently **302-redirects** to a
landing page where the dropdown renders; we followed redirects with `curl -sIL`.

### 3.3 Extracting the orderings (the core technique)

The sort control is **server-rendered into the HTML** — no JavaScript needed, so a plain
`curl` suffices:

```bash
curl -sL -A "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) \
  AppleWebKit/537.36 Chrome/120 Safari/537.36" "<url>" -o page.html
```

Two markup variants exist:

- **Newer UI** — a `<div class="dropdown-select-container js-dropdown-select-menu">`
  block; each option is `<a href="...order=XXX...">Label</a>`; the **current/default**
  ordering is the text inside `js-dropdown-select-menu-toggle`.
- **Older UI** — a `<ul class="order-links">` / `<ul class="submenu">` /
  `<ul class="menu simple">` list of `<a href="...order=XXX...">` links; the default
  carries the `active` / `is-active` class.

To read the **default**, load the bare URL with **no `?order=` param** and record which
option is active in the toggle.

### 3.4 Keying on the param, not the label

Labels are localized; the `order=` query parameter is language-independent and is the
ground truth. Mapping:

| `order=` param | Meaning | Sample labels seen |
|---|---|---|
| `random` | random | Zufällig, Aleatorio/Aleatorios, aleatório |
| `newest`, `created_at`, `creation_date_asc` | by submission date | Neueste zuerst, Fecha de creación, Más recientes |
| `confidence_score`, `most_voted`, `total_votes`, `votes_up`, `cached_votes_up` | most-voted (popularity) | Mejor valorados, Aktuelles Ranking, Am meisten gewählt, Ranking de apoio |
| `comments_count`, `most_commented` | most-commented | Meist kommentiert, Más comentados |
| `hot_score` | most-active | Aktivste |
| `alphabetical` / `alphabetically` | alphabetical | Alphabetisch |
| `price` | by cost (balloting phase) | — |

We treat the popularity family (`confidence_score`/`total_votes`/`votes_up`/`cached_votes_up`)
as a single **most-voted** ordering for the cross-deployment overview.

### 3.5 Inclusion / exclusion criteria

- **Included** only if the ordering UI *actually rendered* in the fetched HTML and we
  parsed real `order=` params from it.
- **Excluded** (with a recorded reason) if: the site was dead/unreachable; had no budget
  module or no active budget; rendered no ordering UI (a non-sortable phase); was blocked
  by a WAF; or had migrated to another platform (e.g. Decidim, VOLIS, LiberOpinion).
- **No guessing.** A row exists only if its dropdown was parsed.

### 3.6 Archiving (citable proof)

Each live page is submitted to the Internet Archive Save-Page-Now endpoint so the
server-rendered dropdown is preserved at a timestamped URL:

```bash
curl -sL "https://web.archive.org/save/<url>"   # returns Location: .../web/<ts>/<url>
```

### 3.7 Limitations

- **Sample, not census.** Several of the largest deployments were unreachable from this
  environment: **Madrid (`decide.madrid.es`), A Coruña, Gran Canaria, Montevideo** were
  blocked by WAFs (403/503), and most `.gob.*`/`.gov.*` government hosts returned
  connection failures (HTTP 000). A run from an unblocked network would add rows.
- **Phase snapshot.** Each deployment is observed in whatever phase it was in on
  2026-06-14; the menu it shows at other times may differ (per §2).
- **Provenance varies.** Most rows are direct live fetches; São Paulo was read from a
  current Internet Archive snapshot because its `.gov.br` host firewalls direct requests.

## 4. Results

### 4.1 Master table (18 deployments, default `order=` param marked ★)

| # | City | Country | Orderings (`order=` family) | Default | Provenance |
|---|---|---|---|---|---|
| 1 | Munich 2025 | DE | random, newest, most-commented | random ★ | live |
| 2 | Munich 2026 | DE | random, newest, most-commented, most-voted | random ★ | live |
| 3 | Garching | DE | random, newest, most-commented | random ★ | live |
| 4 | Jena | DE | random, newest, most-commented | random ★ | live |
| 5 | Unterschleißheim | DE | random, newest, most-commented, most-voted | random ★ | live |
| 6 | Gelsenkirchen | DE | random, newest, most-voted, most-active, alphabetical | random ★ | live |
| 7 | Marchamalo | ES | random, most-voted | random ★ | live |
| 8 | Valencia | ES | random, newest (creation date) | random ★ | live |
| 9 | Valladolid | ES | random, most-voted | random ★ | live |
| 10 | Getafe | ES | random, most-voted | random ★ | live |
| 11 | São Paulo | BR | random, most-voted | random ★ | Archive 2026-01-23 |
| 12 | Cancún | MX | random | random ★ | live |
| 13 | Aarhus | DK | random, price | random ★ | live |
| 14 | Glasgow | UK (Scotland) | random | random ★ | live (balloting) |
| 15 | Inverclyde | UK (Scotland) | random | random ★ | live (balloting) |
| 16 | North Lanarkshire | UK (Scotland) | random | random ★ | live (balloting) |
| 17 | Renfrewshire | UK (Scotland) | random | random ★ | live (balloting) |
| 18 | Province of Fryslân | NL | random | random ★ | live (balloting) |

Reference (not counted): the official demo `demo.consuldemocracy.org/budgets/1/investments`
renders `random` + `price`, default `random` — consistent with a balloting phase.

### 4.2 Working source URLs (the proof, re-fetchable)

- Munich 2025 — `https://unser.muenchen.de/muenchenbudget2025`
- Munich 2026 — `https://unser.muenchen.de/muenchenbudget2026?projekt_phase_id=688`
- Garching — `https://beteiligung.garching.de/buergerbudget?projekt_phase_id=11`
- Jena — `https://mitmachen.jena.de/buergerbudget`
- Unterschleißheim — `https://consul.unterschleissheim.de/buergerbudget-2026?projekt_phase_id=497`
- Gelsenkirchen — `https://mitmachen.gelsenkirchen.de/gruenes-buergerbudget`
- Marchamalo — `https://decide.marchamalo.es/budgets/9/investments`
- Valencia — `https://vlcparticipa.valencia.es/budgets/8/investments`
- Valladolid — `https://www10.ava.es/presupuestosparticipativos/budgets/6/investments`
- Getafe — `https://participa.getafe.es/budgets/8/investments`
- São Paulo — `https://participemais.prefeitura.sp.gov.br/budgets/6/investments` (also budget 5, identical)
- Cancún — `https://participa-y-transforma.cancun.gob.mx/budgets/1/investments`
- Aarhus — `https://www.sammenomaarhus.dk/budgets/29/investments`
- Glasgow — `https://glasgow.communitychoices.scot/budgets/5/investments`
- Inverclyde — `https://inverclyde.communitychoices.scot/budgets/6/investments`
- North Lanarkshire — `https://nla.communitychoices.scot/budgets/1/investments`
- Renfrewshire — `https://renfrewshire.communitychoices.scot/budgets/4/investments`
- Fryslân — `https://stimfanfryslan.frl/budgets/3/investments`

### 4.3 Wayback snapshots (captured 2026-06-14, dropdown verified present)

German cluster:
- Munich 2025 — `https://web.archive.org/web/20260614074420/https://unser.muenchen.de/muenchenbudget2025`
- Munich 2026 — `https://web.archive.org/web/20260614074451/https://unser.muenchen.de/muenchenbudget2026?projekt_phase_id=688`
- Garching — `https://web.archive.org/web/20260614075526/https://beteiligung.garching.de/buergerbudget?projekt_phase_id=11`
- Unterschleißheim — `https://web.archive.org/web/20260614075606/https://consul.unterschleissheim.de/buergerbudget-2026?projekt_phase_id=497`
- Gelsenkirchen — `https://web.archive.org/web/20260614075637/https://mitmachen.gelsenkirchen.de/gruenes-buergerbudget`
- Jena — `https://web.archive.org/web/20260614075801/https://mitmachen.jena.de/buergerbudget`

International cluster: archived 2026-06-14 (snapshot URLs in `wayback_intl.txt` alongside this file).

### 4.4 Patterns

1. **Default = `random`, universally.** All 18 deployments default to random. None defaults
   to a popularity sort. This corrects an earlier assumption that Munich "defaults to
   most-commented" — most-commented is one *offered* option, not the default.
2. **No relevance-aware ordering anywhere.** Every observed ordering is
   random / most-voted / newest / most-commented / most-active / alphabetical / price.
3. **Stock vs. customized menus.** Where a multi-option feed was live:
   - **Stock Consul** (Spain, Brazil) offers `random + most-voted` (`confidence_score` /
     `cached_votes_up`) — exactly the upstream code.
   - The **demokratie.today German cluster** *adds* `newest` and `most-commented` on top
     of stock — a shared regional customization. Gelsenkirchen further adds `most-active`
     and `alphabetical`.
   This is the concrete instance of "the framework ships most-voted + random; a deployment
   can widen the menu, but only with more popularity/recency orders."
4. **Ballot phases show `random` only** (Scotland, Fryslân, Cancún; Aarhus `+ price`) —
   the deliberate anti-bias default for the binding vote.

### 4.5 Coverage and exclusions

Roughly **90+ domains/hostnames checked** across the three regional passes; **18 yielded a
live ordering UI we parsed**. Notable exclusions (recorded reason):

- **WAF-blocked (live but unreadable):** decide.madrid.es (Akamai 403); A Coruña
  aportaaberta.coruna.es (503) & nacorunacontas.coruna.gal (403); Gran Canaria
  participa.grancanaria.com (Imperva 403); Montevideo participa.montevideo.gub.uy
  (custom 403); Greece xylokastro & weopengov (Cloudflare 403); Vila Nova de Famalicão
  ideiasnapraca.org (403).
- **Live Consul, no sortable phase / no budget:** Las Palmas, Tenerife (test budget),
  Palencia (no active budget), Calahorra (random-only), the **Slovenian djnd.si cluster**
  (Celje, Medvode, Nova Gorica, Novo Mesto, Trebnje, Tržič, Ankaran — all live PB but the
  current phase renders no ordering UI), Greece consul.ellak.gr (no budgets), Bari (500),
  Porto Alegre (500), Groningen (`/budgets` 404).
- **Unreachable from this environment (HTTP 000):** most `.gob`/`.gov` hosts — León,
  San Pedro, Quito, Buenos Aires; Lisboa op.lisboaparticipa.pt; Torino; Issy-les-Moulineaux;
  Brașov.
- **Migrated / not Consul:** Decidim (decidimvlc.valencia.es, Monterrey, Brasil
  Participativo, Contagem, Uruguay national); VOLIS (Tartu); LiberOpinion / static vendors
  (many Portuguese `op.<city>.pt`); ArcGIS/Colab (various LatAm).

## 5. Implications for the paper

- The universal claim ("the same weak orderings recur across deployments; none is
  relevance-aware") is now backed by a real **18-deployment, 8-country sample** plus the
  **source code** (which proves it by construction for *all* deployments), not by Munich
  alone.
- Present the table explicitly as **"a sample of live Consul PB deployments,"** never a
  census, and state the **phase-dependence** and **WAF** caveats.
- The **stock-vs-customized** contrast (Spain/Brazil = `random + most-voted`; Germany adds
  `newest + most-commented`) is a clean illustration of the "framework ships X; a city can
  widen it" narrative already in the data section.

## 6. Reproduction checklist

1. Get the candidate domain from a registry or search (§3.1).
2. `curl -sIL` the budget path to follow redirects to the landing page.
3. `curl -sL -A "Mozilla/5.0 …"` the landing page; grep for `js-dropdown-select-menu` or
   `order-links`.
4. Extract every `order=XXX`; read the toggle/`is-active` on the bare URL for the default.
5. Map params via the §3.4 table; collapse the popularity family to "most-voted."
6. Record only if a dropdown rendered; otherwise log the exclusion reason.
7. `curl https://web.archive.org/save/<url>` to archive.
