# idle_annoyance

`idle_annoyance` is the connected-desktop control for loaded annoyance
scenarios such as `web_annoyance`. It minimizes visible windows but does not
change Wi-Fi, radios, display brightness, or power mode.

The default `paired_web` schedule reproduces the logical start times, probe
order, probe counts, and `SlotId` values from the validated full web run. Every
probe reports `WebPhase=idle_desktop`, making idle and loaded rows directly
pairable by:

```text
SlotId + Probe + Iteration + Interaction
```

One schedule cycle lasts 1124 seconds and contains 17 probe instances:

- Mute/unmute: 4
- Start / Show all: 6
- Explorer / Windows folder: 4
- Pictures thumbnails: 3

Automatic ETW and 1 Hz Energy Meter power reporting is enabled by default.
Disable it with `idle_annoyance:power_reporting=0`.

Run independent HOBL iterations for statistical collection rather than using
multiple cycles in one run. This resets the desktop and power lifecycle between
samples while preserving the paired schedule inside each run.