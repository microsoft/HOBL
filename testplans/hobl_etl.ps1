if ($ARGS[0] -eq $null) {return("Params .ini not supplied, please supply a params .ini parameter.")}
.\hobl.cmd -p $ARGS[0] -s process_idle_tasks global:run_type=Power global:post_run_delay=0
.\hobl.cmd -p $ARGS[0] -s config_check
.\hobl.cmd -p $ARGS[0] -s charge_off global:run_type=Misc global:post_run_delay=900

.\hobl.cmd -p $ARGS[0] -s idle_desktop global:tools="+power_heavy" global:run_type=ETL
.\hobl.cmd -p $ARGS[0] -s cs_floor global:tools="+power_heavy powercfg" global:run_type=ETL
.\hobl.cmd -p $ARGS[0] -s abl_active global:tools="+power_heavy" global:run_type=ETL
.\hobl.cmd -p $ARGS[0] -s abl_standby global:tools="+power_heavy powercfg" global:run_type=ETL
.\hobl.cmd -p $ARGS[0] -s web global:tools="+power_heavy" global:run_type=ETL
.\hobl.cmd -p $ARGS[0] -s idle_apps global:tools="+power_heavy" global:run_type=ETL
.\hobl.cmd -p $ARGS[0] -s productivity global:tools="+power_heavy" global:run_type=ETL
.\hobl.cmd -p $ARGS[0] -s netflix global:tools="+power_heavy" global:run_type=ETL
.\hobl.cmd -p $ARGS[0] -s youtube global:tools="+power_heavy" global:run_type=ETL
.\hobl.cmd -p $ARGS[0] -s lvp global:tools="+power_heavy" global:run_type=ETL
.\hobl.cmd -p $ARGS[0] -s teams2_3x3_video global:tools="+power_heavy" global:run_type=ETL
.\hobl.cmd -p $ARGS[0] -s teams2_1on1_audio global:tools="+power_heavy" global:run_type=ETL
.\hobl.cmd -p $ARGS[0] -s teams2_idle global:tools="+power_heavy" global:run_type=ETL

.\hobl.cmd -p $ARGS[0] -s charge_on global:run_type=Misc
.\hobl.cmd -p $ARGS[0] -s study_report global:run_type=Misc
.\hobl.cmd -p $ARGS[0] -s notify global:run_type=Misc notify:plan_run_type=etl

