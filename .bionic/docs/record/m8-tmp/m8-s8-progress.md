# M8 S8 progress

- start: HEAD a78db18; all critic repros confirmed (e1, e2, e9)
- B1 committed 36e8398: pypsa trafo b / scale; green 36 passed, sabotage 2 failed
- B2 committed 9e2c9b3: tap_changer_type rule + TAP_CHANGER_TYPE_UNSUPPORTED; 15 tap tests green, sabotage 3 failed
- B3 committed 9e2c9b3: promote line+tap, is_transformer routing; sabotage 4 failed
- B3 committed df51ee8: promote line+tap, is_transformer routing; sabotage 4 failed
- S10 committed 1f442d6: res_bus removed both ways; 82 passed incl. parity; sabotage 1 failed
- S4 committed 841fb46: bulk export; case300 3062->112 ms; nets_equal; sabotage 2 failed
- S6 committed c6f9894: GEN_SLACK_PROMOTED; 146 passed; sabotage 2 failed
- S7 committed c5070ac: atomic csv dump; 59 passed; sabotage 1 failed
- S9 committed 53b084a: io/limitations.py; 94 passed; sabotage 8 failed
- nits committed e2d6da8: RAW area, CSV field limit, _label(inf), pypsa in-service vset + PYPSA_COST_NONCONVEX; sabotage 5 failed
- final gates running
- gates green (ruff/format/mypy; unit 1199; parity 175+4 skip; mkdocs strict 0; example 13 exit 0)
- completion message sent to team-lead; report written to .bionic/docs/record/m8-s8-report.md
