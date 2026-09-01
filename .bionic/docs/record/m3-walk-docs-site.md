# M3 docs site walk

A first-look pass through the running `mambo-power` docs site (`mkdocs serve`, mkdocs-material), driven with a real browser via `playwright-cli`, starting from the home page and following the nav and search the way a visitor would. Screenshots are in `walk-m3/`, numbered in the order I took them.

## Home page

`walk-m3/01-home.png`. Clean, readable landing page: a one-paragraph pitch, a runnable code snippet, a status callout, a "three principles" section, a "where to go next" table, and a roadmap table at the bottom. Nothing looks templated or placeholder-ish.

One thing stood out immediately, though: the status callout still reads "Wave **M1** ... is merged. Wave **M2** ... is in progress on its wave branch" and doesn't mention DC-OPF or N-1 at all — the "where to go next" table has no row pointing at the new OPF/N-1 material, and the roadmap table at the bottom still lists M3 as "planned." But the site I'm looking at very clearly *has* a full DC-OPF and N-1 manual, API pages, and a worked example (see below) — so the home page's own narrative of "what's done" is stale relative to what's actually sitting one click away in the nav. A visitor landing here first would come away thinking OPF/N-1 doesn't exist yet.

The page also throws one console error on load, on every page: a 404 fetching `https://api.github.com/repos/mambo10005/mambo-power/releases/latest` (the repo-info widget in the header trying to reach GitHub's API and failing, presumably because the sandboxed dev environment has no outbound network access, or the repo has no releases). Cosmetically harmless — the little star/fork counters in the header just show "0 0" — but worth knowing it's there.

## Manual → DC-OPF

`walk-m3/02-manual-opf-top.png`. The DC-OPF page is dense, well-organized technical writing: entry-point table, formulation, cost handling (LP vs QP), piecewise-linear costs, duals/LMPs, the AC-feasibility check, and a named "formulation note" explaining exactly where this solver's PTDF-based approach diverges from pandapower's theta-based one and why. It reads like someone who actually understands the domain wrote it, not boilerplate.

The math rendering is broken on this page, though, and I confirmed it's not just a load-timing thing (reloaded the page fresh, waited several seconds, checked again — same result every time). Some inline formulas render fine (crisp italic variables with real subscripts), but others show up as raw, unprocessed LaTeX source sitting right on the page: `\(`/`\)` delimiters left in as literal text, and — worse — an entire display-mode block equation (the epigraph/segment LP encoding, `\[ \text{cost}_g \ge \text{slope}_i \cdot p_g + ... \]`) renders as completely raw source with `\text{}`, `\cdot`, `\qquad`, `\frac{}{}` all visible verbatim. See `walk-m3/03-manual-opf-pwl-math.png` (and `03b-...-after-wait.png`, taken after a deliberate pause, showing no change). No console error accompanies this — it fails silently, so a visitor has no indication anything's wrong beyond the garbled text itself.

## Manual → N-1 screening

`walk-m3/04-manual-n1-top.png`. Similarly well-written: the screen/confirm split, the result shape, an explicit "Scope" section calling out what's *not* done yet (generator outages, N-2+, redispatch), a rating-data caveat, and a nice "agreement guarantee" table showing screen-vs-brute-force outage counts match exactly across five real MATPOWER fixtures. I liked the small callout box explaining the deliberate `contingency.n1` name collision between the module and the function — that's the kind of thing that'd otherwise confuse a reader poking at the source.

The core formula on this page — the one thing a reader most needs to actually understand the LODF screening estimate — is the worst-rendered thing I found on the whole site. See `walk-m3/05-manual-n1-formula.png`: it comes out as a scattered, multi-line mess of disconnected fragments — `estimated[l` on one line, `\bigl|\, \text{base\_flow}` on the next, an isolated `l` centered on its own line, `+ \text{LODF}` below that, `l,k` centered alone, `\cdot \text{base\_flow}` below that, `k` alone, then `\,\bigr| \]` trailing off. It's genuinely hard to parse as a formula at all; you'd have to already know DC contingency screening to reconstruct what it's supposed to say. Same silent-failure pattern as the OPF page.

## Examples → 08. OPF and N-1

`walk-m3/06-examples-08-opf-n1.png`. The new example script is embedded via `pymdownx.snippets` (the page states explicitly that the code shown is the same bytes CI runs), which is a nice trust signal. The docstring at the top of the script gives a good plain-English tour of what it demonstrates.

I noticed the embedded code block clips long comment lines at the right edge with no way to see the rest — I checked, and there's genuinely no horizontal scrollbar or wrap on that `<pre>`; the inner `<code>` measurably overflows its container (848px of content in a 688px box) but nothing exposes the extra ~160px. Lines like the docstring's bullet points ("...the cost-minimising LP/QP dispatch, its ...", "...one branch's rating until it binds splits the price into ...") just get truncated mid-sentence. This isn't unique to this page — I saw the same clipping later on the "Module map on disk" code block on the Architecture page — so it looks like a site-wide code-block behavior rather than something specific to the new content, but it's most noticeable here because the new example's docstring has long descriptive lines.

## Design → Architecture

Two mermaid diagrams (a component flowchart and a sequence diagram). On a genuinely fresh page load, both sit blank for at least several seconds — I explicitly tested this (fresh navigation, 4-second passive wait, checked the DOM: zero rendered SVGs). But scrolling a diagram into view reliably makes it render within well under a second, so this looks like intentional scroll-triggered/lazy rendering rather than a broken diagram — a visitor scrolling down normally would never notice, they'd just see it appear. Once rendered, both diagrams look right: `walk-m3/07-design-architecture-mermaid-blank.png` (this one actually caught the *rendered* state, since my scroll-into-view call to capture the "blank" state ended up triggering the render before the screenshot fired) and `walk-m3/08-design-architecture-sequence-diagram.png` show a component graph with `opf` and `contingency` boxes wired into `model`/`numerics`/`pf`/`results`/`jobs` exactly the way the manual pages describe, and a sequence diagram for a single `pf.solve_dc` call. Content-wise these are accurate and match the prose around them.

## API reference

`walk-m3/09-api-opf.png` and `walk-m3/11-api-contingency.png`. Both `mambo_power.opf` and `mambo_power.contingency` have full mkdocstrings-generated pages: class/function nav in the left rail, cross-referenced types in blue, expandable "Source code in ..." blocks with line numbers and a copy button. Clicking one of these ("Source code in") expanded cleanly and showed the real implementation (`walk-m3/14-api-source-expanded.png`).

Two small things:
- Every "Source code in ..." path on this build shows Windows-style backslashes (`src\mambo_power\opf\__init__.py`), which reads oddly for what's presumably meant to look like a repo path. Almost certainly just an artifact of building the docs locally on Windows rather than something that'd show up in the real (Linux CI) published site, but worth flagging since it's what I actually saw.
- The `mambo_power.contingency` module docstring includes the literal string "wave M3 W5" in its first paragraph ("N-1 branch-contingency screening (epic Design §2 `contingency/`; wave M3 W5)"). That's internal planning shorthand leaking into public API documentation — a reader with no context on this project's process has no idea what "wave M3 W5" refers to.

I also followed a cross-reference link (`mambo_power.pf.solve_dc` from the opf page) and it landed exactly on the right anchor with the target heading highlighted — `walk-m3/10-api-crossref-solve_dc.png`. That worked well.

## Search

Tried searching for `lmp_decomposition` from the home page. It surfaced 3 matching documents, and the top hit showed the exact function signature plus a syntax-highlighted excerpt of the docstring with the search term highlighted in place — `walk-m3/12-search-lmp_decomposition.png`. Clicking through landed precisely on `mambo_power.opf.dc_opf.lmp_decomposition` with the term highlighted on the page itself (`walk-m3/13-search-result-landed.png`), URL carrying a `?h=lmp_decomposition` query param for the highlight. This is a genuinely nice piece of UX — the search index clearly reaches into API docstrings and source excerpts, not just prose pages.

## Overall

The new OPF/N-1 content itself — the writing, the structure, the worked example, the API docs, the architecture diagram update — is thorough and reads like it was written by someone who actually did the work and wants a reader to understand the real formulation, including its known limitations and divergences from the pandapower oracle. The two things I'd most want someone to look at are the math rendering (silently broken on both new manual pages, badly enough on the N-1 page that the core formula is unreadable) and the stale home-page status blurb, which currently undersells what this wave actually shipped.
