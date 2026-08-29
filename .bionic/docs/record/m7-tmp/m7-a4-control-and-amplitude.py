"""Final A4 measurements: AC-4's paired control, and the oscillation amplitude that separates
'dithering at the peak' (converged) from 'genuinely cycling' (not converged).
"""

import numpy as np

from a4_fix import Market, hill_climb  # noqa: F401  (reuses the fixtures and the climb)


def trace(mkt, step=0.5, max_rounds=400, simultaneous=True):
    """Run the climb and report the final oscillation amplitude of the offer vector."""
    n = len(mkt.caps)
    offers = mkt.costs.copy()
    d, price = mkt.clear(offers)
    p2 = np.array([(price - mkt.costs[i]) * d[i] for i in range(n)])
    o2 = offers.copy()
    offers = offers.copy()
    for i in mkt.reactive:
        offers[i] += step
    d, price = mkt.clear(offers)
    p1 = np.array([(price - mkt.costs[i]) * d[i] for i in range(n)])
    hist, seen = [o2.copy(), offers.copy()], {}
    for r in range(2, max_rounds + 1):
        nxt = offers.copy()
        idxs = mkt.reactive if simultaneous else [mkt.reactive[(r - 2) % len(mkt.reactive)]]
        for i in idxs:
            direction = np.sign(offers[i] - o2[i]) or 1.0
            if p1[i] < p2[i] - 1e-9:
                direction = -direction
            nxt[i] = max(mkt.costs[i], offers[i] + direction * step)
        key = tuple(np.round(np.concatenate([offers, nxt]), 6))
        if key in seen:
            period = r - seen[key]
            tail = np.array(hist[-period:])
            amp = float(np.max(np.ptp(tail[:, mkt.reactive], axis=0)))
            mid = tail[:, mkt.reactive].mean(axis=0)
            d, p = mkt.clear(tail[int(np.argmax(tail[:, mkt.reactive[0]]))])
            return r, period, amp, mid, p
        seen[key] = r
        o2, p2 = offers, p1
        offers = nxt
        hist.append(offers.copy())
        d, price = mkt.clear(offers)
        p1 = np.array([(price - mkt.costs[i]) * d[i] for i in range(n)])
    return max_rounds, None, None, offers[mkt.reactive], price


def profit_at(mkt, offers):
    d, p = mkt.clear(np.array(offers, float))
    return float(sum((p - mkt.costs[i]) * d[i] for i in mkt.reactive)), p, d


# AC-4 pivotal (smooth): 900 MW @ $20 facing q = 1000 - 10*price. Peak: $60 / 400 MW / $16,000.
piv = Market([900.0, 1.0], [20.0, 999.0], reactive=[0])
# AC-4 control (non-pivotal): the same agent, but a 900 MW rival at $22 caps what withholding buys.
ctl = Market([900.0, 900.0], [20.0, 22.0], reactive=[0])

for name, mkt in (("pivotal  (smooth, no rival)", piv), ("control  (900 MW rival @ $22)", ctl)):
    base, bp, bd = profit_at(mkt, mkt.costs)
    r, period, amp, mid, peak_price = trace(mkt, step=0.5)
    best, pp, pd = profit_at(mkt, [mid[0] if i == 0 else mkt.costs[i]
                                   for i in range(len(mkt.caps))])
    print(f"{name}")
    print(f"    true-cost offers : price={bp:6.2f}  strategic profit={base:10.2f}")
    print(f"    climb ends       : r={r:<4d} period={period}  amplitude={amp}  offer~{mid.round(2)}")
    print(f"    at that offer    : price={pp:6.2f}  strategic profit={best:10.2f}  "
          f"gain={best - base:10.2f}")

# The separation: a dither at the peak vs a genuine cycle (R1's at-capacity rule, from part 1).
duo = Market([300.0, 300.0], [20.0, 20.0], reactive=[0, 1])
r, period, amp, mid, _ = trace(duo, step=0.5, simultaneous=True)
base, bp, bd = profit_at(duo, duo.costs)
best, pp, pd = profit_at(duo, mid)
print("\nduopoly 300/300 @ $20, both reactive (AC-5 fixture)")
print(f"    true-cost offers : price={bp:6.2f}  joint profit={base:10.2f}")
print(f"    climb ends       : r={r:<4d} period={period}  amplitude={amp}  offer~{mid.round(2)}")
print(f"    at that offer    : price={pp:6.2f}  joint profit={best:10.2f}  gain={best - base:10.2f}")
print(f"\n>>> amplitude at a peak is one step ({0.5}); a genuine cycle is far wider "
      f"(R1 at-capacity swung the full markup range)")
