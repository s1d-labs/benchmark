# benchmark

This family of the s1d-labs scrape pool collects public reference data from Indian government sites: Jan Aushadhi
products and stores, and first pages of the NPPA and CPWD sites (discovery).
It has one task, `crawl` (`crawl.py`). `family.py` lists the projects.

## Projects

| Project | Site | How it runs | Queue |
|---|---|---|---|
| `benchmark-janaushadhi` | janaushadhi.gov.in (Jan Aushadhi, PMBJP): its public API on port 8443 | GitHub runners through the hub's Indian proxies (`proxy="IN"`), 1 thread, 1.5 s delay | 25 product pages of 100, and one item for every Kendra (store) |
| `benchmark-nppa` | nppa.gov.in (National Pharmaceutical Pricing Authority) | India pool servers (`geo="IN"`) | the home page (discovery) |
| `benchmark-cpwd` | cpwd.gov.in (Central Public Works Department) | India pool servers and proxies `91.124.42.x` | the home page (discovery) |

The sites answer only from India. The projects register no health check, because the hub checks from outside India.

## Run and check

- `python -m pytest tests` runs the parsing tests on the saved page in `tests/pages/`. No network.
- `scrape-check --items 2` runs setup and the task against a local stand-in hub. Run it through an Indian proxy from a team
  box: `myproxy run scrape-check --items 2`.
- Run the **setup** workflow after a change to `family.py`.

The full contract for family code is in [CLAUDE.md](CLAUDE.md).
