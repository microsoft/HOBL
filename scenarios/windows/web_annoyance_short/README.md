# web_annoyance_short

`web_annoyance_short` is the video-friendly Wikipedia proof of concept for the
native responsiveness probes. It preserves the stock Wikipedia replay page and
scroll sequence, then runs these probes serially:

1. Mute and unmute
2. Start and Show all
3. File Explorer Windows-folder scroll
4. File Explorer Pictures thumbnail sizing

The probes use the same hardened implementations as `web_annoyance`, including
the empty Edge title-bar refocus at `(85%, 2%)`. A default run takes about two
minutes and does not enable power collection.

```powershell
hobl.cmd -p C:\profiles\dut_arm64.ini -s web_annoyance_short `
  "global:config_check=0" "global:post_run_delay=0"
```

Select a subset with `web_annoyance_short:probes`, or enable the standard power
collectors with `web_annoyance_short:power_reporting=1`.