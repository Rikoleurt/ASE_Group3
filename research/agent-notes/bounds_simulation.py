import numpy as np
from scipy.stats import binom, beta
rng = np.random.default_rng(0)
d = 0.1

def hoeff(x): return x.mean() + np.sqrt(np.log(1/d)/(2*len(x)))

def h1(a, b):
    a = min(max(a, 1e-12), 1-1e-12)
    return a*np.log(a/b) + (1-a)*np.log((1-a)/(1-b))

def hb_ucb(x):
    n, r = len(x), x.mean()
    for a in np.arange(0.0005, 0.3, 0.0001):
        if a <= r: continue
        p = min(np.exp(-n*h1(min(r, a), a)), np.e*binom.cdf(np.ceil(n*r), n, a))
        if p <= d: return a
    return 1.0

def cp_ucb(x):  # Bernoulli/beta approximation: treat n*Rhat as a count
    n, k = len(x), x.sum()
    return beta.ppf(1-d, k+1, n-k)

def bet_reject(x, m, lo=0.0, hi=1.0):
    # test H0: E[X] >= m, X in [lo,hi]; capital prod(1 + lam (m - X)); Ville
    n = len(x); K = 1.0; s2 = 0.25*(hi-lo)**2/4; mu = m
    cap = 0.5/(hi-m)  # keeps 1 + lam (m - X) >= 0.5 > 0 for X <= hi
    for t, xt in enumerate(x):
        lam = min(np.sqrt(2*np.log(1/d)/(n*s2)), cap)
        K *= 1 + lam*(m - xt)
        if K >= 1/d: return True
        s2 = (s2*(t+1) + (xt-mu)**2)/(t+2); mu = (mu*(t+1)+xt)/(t+2)
    return False

def wsr_ucb(x):
    lo, hi = max(x.mean(), 1e-6), 0.6
    if not bet_reject(x, hi): return 1.0
    for _ in range(18):
        mid = (lo+hi)/2
        if bet_reject(x, mid): hi = mid
        else: lo = mid
    return hi

def lines(n, mu_word, cov=0.8, hard=0.15, ratio=10):
    m = 1 + rng.poisson(8, n)
    ish = rng.random(n) < hard
    # per-accepted-word error: hard lines ratio x easy
    r = mu_word/cov
    pe = r/(hard*ratio + (1-hard)); ph = pe*ratio
    covl = np.where(ish, 0.6, (cov - hard*0.6)/(1-hard))
    A = rng.binomial(m, covl)
    W = rng.binomial(A, np.where(ish, ph, pe))
    return m, A, W

print("Q1: joint risk UCB (median of 100 sims), delta=0.1")
for n in (300, 500, 1000):
    for mu in (0.005, 0.01, 0.02):
        res = {k: [] for k in ("hoef", "HB", "CP", "WSR_bern", "HB_line", "WSR_line")}
        for _ in range(100):
            xb = (rng.random(n) < mu).astype(float)
            m, A, W = lines(n, mu)
            xl = W/m
            res["hoef"].append(hoeff(xb)); res["HB"].append(hb_ucb(xb)); res["CP"].append(cp_ucb(xb))
            res["WSR_bern"].append(wsr_ucb(xb)); res["HB_line"].append(hb_ucb(xl)); res["WSR_line"].append(wsr_ucb(xl))
        crc = 1/(n+1)
        print(n, mu, {k: round(float(np.median(v))*100, 2) for k, v in res.items()}, "CRC slack B/(n+1)=%.2f%%" % (crc*100))

print("\nQ4: selective risk certification at n=400, coverage 0.8")
def cert(n, r_true, cov, alpha):
    m, A, W = lines(n, r_true*cov, cov=cov)
    # (1) linearised, line-normalised: Z=(W-aA)/m in [-a,1]; H0 E[Z]>=0
    Y = ((W - alpha*A)/m + alpha)/(1+alpha)
    lin = bet_reject(Y, alpha/(1+alpha))
    # (2) joint UCB(d/2)/coverage LCB(d/2) (both line-normalised)
    global d
    d0 = d; d = d0/2
    uj = wsr_ucb(W/m); lc = 1 - wsr_ucb(1 - A/m)
    d = d0
    return lin, uj/lc <= alpha
for r_true in (0.005, 0.01, 0.02):
    for alpha in (0.01, 0.015, 0.02, 0.03, 0.04):
        out = np.array([cert(400, r_true, 0.8, alpha) for _ in range(60)])
        print("true sel risk %.1f%% alpha %.1f%%: P(certify) linearised=%.2f ratio-of-bounds=%.2f" % (r_true*100, alpha*100, out[:,0].mean(), out[:,1].mean()))
