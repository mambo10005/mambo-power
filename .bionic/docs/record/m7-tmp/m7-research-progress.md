# M7 research progress — UPDATE COMPLETE
Reframed §1/§3/§4/§5 against the 3 decided scope answers (overlay, best-response iteration, bid-side cap).
Numerically verified both §5(b) fixtures (single-pivotal-generator and paired-non-pivotal cases) via
uv run --project "/c/Claude Projects/mambo-power" python + scipy (closed-form + grid search + Nelder-Mead cross-check, all agree to 4 sig figs).
Found and reported: §5(a)'s bit-identical claim doesn't survive the decided overlay design (two solves,
not one) -- correction from first pass. §5(b)'s "second competitor makes markup unprofitable" premise
doesn't hold numerically -- corrected to "makes it ~17x less profitable, still real and nonzero."
§4 finding: neither named AC exercises >1 reactive agent, so neither exercises the loop's own termination
machinery -- flagged as a coverage gap for the design interview.
Report updated at .bionic/docs/record/m7-research.md. Done.
