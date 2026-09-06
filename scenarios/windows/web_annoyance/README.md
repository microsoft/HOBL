# web_annoyance

`web_annoyance` serializes native responsiveness probes into known input-idle
windows in a web workload. The stock `web` scenario remains unchanged.

## Full web workload

The scenario reuses the complete stock `web_run` action stream and therefore
keeps the canonical 12-site order, tab handling, cache clearing, replay checks,
and archive selection. Only six site modules are adapted in memory, and only at
seven verified input-idle `Delay` actions. Page-load waits are never used.

| Site and stock action | Stock window | Inserted probes | Residual idle |
|---|---:|---|---:|
| Reddit `UC69K4` | 60 s | Mute, Start, Explorer | 30.25 s |
| Instagram `UCJ082` | 30 s | Mute, Start | 13.00 s |
| Instagram `UCHYN5` | 30 s | Mute, Explorer | 8.75 s |
| YouTube ToS `UCL4U1` | 76 s | Start, Explorer, Pictures | 38.25 s |
| Wikipedia `UC6L36` | 10 s | Start | 3.50 s |
| YouTube NASA `UCL4U1` | 87 s | Mute, Start, Explorer, Pictures | 38.75 s |
| The Verge `UC6L36` | 38 s | Start, Pictures | 13.00 s |

This yields 17 probe instances while preserving every stock window's scripted
duration. Each probe closes its UI and restores Edge by clicking the empty
browser title bar at `(85%, 2%)` before stock web input resumes.

The standard stock selectors remain available. For example:

```powershell
hobl.cmd -p <profile> -s web_annoyance `
  "web:web_workload=reddit instagram youtubenasa"
```

Select a subset of probe types with `web_annoyance:probes`. Every latency,
occupancy, and power row includes `WebPhase` and `SlotId`, allowing repeated
probe instances to be joined back to the owning site and stock action.

## Power reporting

Power reporting is enabled by default with two complementary HOBL tools:

- `power_light` records the standard ETW Energy Estimation Engine trace and
  produces whole-run HOBL power files.
- `annoyance_power` polls the Windows Energy Meter counters once per second and
  joins those samples to the annoyance event timeline.

The run directory contains:

- `<run>_power_light.csv` and `<run>_e3_power_summary.csv`: standard whole-run
  HOBL power output.
- `<run>_annoyance_power.trace`: raw 1 Hz per-rail samples.
- `<run>_annoyance_probe_power.trace`: whole-run and per-probe power and energy.
- `<run>_annoyance_interaction_power.trace`: interaction-window power and energy.
- `<run>_annoyance_power_data.csv`: two-column metrics consumed by `run_report`.

The interaction windows can be shorter than the one-second power sampling
interval. Use per-probe rows for primary comparisons and treat sub-second
interaction power as contextual rather than precise energy attribution.

Disable all automatic power collection with:

```powershell
hobl.cmd -p <profile> -s web_annoyance "web_annoyance:power_reporting=0"
```

An explicit `global:tools` command-line override takes precedence over scenario
defaults. Include both `power_light` and `annoyance_power` when supplying that
override and power reporting is desired.