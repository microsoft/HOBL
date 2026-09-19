# productivity_annoyance

`productivity_annoyance` preserves the stock `productivity` setup, application
open order, complete app interaction stream, close order, and teardown. After
all Office apps open, it inserts the stock five-app `prod_idle` phase and runs
native responsiveness probes inside those explicit idle windows. The complete
stock `prod_run` then executes unchanged.

| Foreground app and idle action | Idle window | Inserted probes | Residual idle |
|---|---:|---|---:|
| Outlook `V4KHPE` | 111 s | Mute, Start | 94.00 s |
| Excel `V4KJ0J` | 111 s | Explorer | 100.25 s |
| Word `V4KJ53` | 111 s | Pictures | 94.50 s |
| PowerPoint `V4KJ7E` | 111 s | Mute, Start | 94.00 s |
| OneNote `V4KJ9F` | 111 s | Explorer, Pictures | 81.75 s |

This yields eight balanced probe instances: two of each probe type. No probe is
inserted into active typing, scrolling, document loading, or file operations.
The added loaded-app phase is 570 seconds at the default setting: five 111-second
idle windows plus the stock three-second app switches.

```powershell
hobl.cmd -p <profile> -s productivity_annoyance
```

Select a subset with `productivity_annoyance:probes`. Power reporting is enabled
by default through `power_light` and `annoyance_power`; disable it with
`productivity_annoyance:power_reporting=0`.

Change the per-app idle duration with
`productivity_annoyance:idle_seconds_per_app`; the adapter fails before running
if the selected probe plan cannot fit.

Every latency, occupancy, and direct-power row includes the stock module phase
and slot ID, such as `productivity_outlook / outlook_UPTF4X`.