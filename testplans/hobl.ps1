if ($ARGS[0] -eq $null) {return("Params .ini not supplied, please supply a params .ini parameter.")}
.\hobl.cmd -p $ARGS[0] -s process_idle_tasks global:run_type=Prep global:post_run_delay=0
.\hobl.cmd -p $ARGS[0] -s config_check
.\hobl.cmd -p $ARGS[0] -s charge_off global:run_type=Misc global:post_run_delay=900

.\hobl.cmd -p $ARGS[0] -s idle_desktop global:iterations=3 global:attempts=2 global:run_type=Power global:tools="+power_light"
.\hobl.cmd -p $ARGS[0] -s cs_floor global:iterations=2 global:attempts=2 global:run_type=Power global:tools="+powercfg power_light"
.\hobl.cmd -p $ARGS[0] -s abl_active global:iterations=3 global:attempts=2 global:run_type=Power global:tools="+power_light"
.\hobl.cmd -p $ARGS[0] -s web global:iterations=3  global:run_type=Power global:tools="+power_light"
# .\hobl.cmd -p $ARGS[0] -s idle_apps global:iterations=3 global:run_type=Power global:tools="+power_light"
# .\hobl.cmd -p $ARGS[0] -s productivity global:iterations=3 global:run_type=Power global:tools="+power_light"
.\hobl.cmd -p $ARGS[0] -s abl_standby global:iterations=3 global:attempts=2 global:run_type=Power global:tools="+powercfg power_light"
.\hobl.cmd -p $ARGS[0] -s netflix global:iterations=3 global:attempts=2 global:run_type=Power global:tools="+power_light"
.\hobl.cmd -p $ARGS[0] -s youtube global:iterations=3 global:attempts=2 global:run_type=Power global:tools="+power_light"
.\hobl.cmd -p $ARGS[0] -s lvp global:iterations=3 global:attempts=2 global:run_type=Power global:tools="+power_light"
.\hobl.cmd -p $ARGS[0] -s teams2_3x3_video global:iterations=3 global:attempts=2 global:run_type=Power global:tools="+power_light"
.\hobl.cmd -p $ARGS[0] -s teams2_1on1_audio global:iterations=3 global:attempts=2 global:run_type=Power global:tools="+power_light"
.\hobl.cmd -p $ARGS[0] -s teams2_1on1_video global:iterations=3 global:attempts=2 global:run_type=Power global:tools="+power_light"
.\hobl.cmd -p $ARGS[0] -s teams2_idle global:iterations=3 global:attempts=2 global:run_type=Power global:tools="+power_light"
.\hobl.cmd -p $ARGS[0] -s idle_desktop global:iterations=1 global:run_type=Power global:tools="+power_light"
.\hobl.cmd -p $ARGS[0] -s cs_floor global:iterations=1 global:run_type=Power global:tools="+powercfg power_light"
.\hobl.cmd -p $ARGS[0] -s charge_on global:run_type=Misc
.\hobl.cmd -p $ARGS[0] -s study_report global:run_type=Misc
.\hobl.cmd -p $ARGS[0] -s version_report global:run_type=Prep global:post_run_delay=0
.\hobl.cmd -p $ARGS[0] -s notify global:run_type=Misc

