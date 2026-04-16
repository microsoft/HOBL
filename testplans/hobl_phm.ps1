if ($ARGS[0] -eq $null) {return("Params .ini not supplied, please supply a params .ini parameter.")}
.\hobl.cmd -p $ARGS[0] -s process_idle_tasks global:run_type=Power global:post_run_delay=600
.\hobl.cmd -p $ARGS[0] -s config_check
.\hobl.cmd -p $ARGS[0] -s charge_off global:run_type=Misc global:post_run_delay=300

.\hobl.cmd -p $ARGS[0] -s phm_prep global:run_type=Prep
.\hobl.cmd -p $ARGS[0] -s idle_desktop global:tools="+phm" global:run_type=PHM
.\hobl.cmd -p $ARGS[0] -s cs_floor global:tools="+phm powercfg" global:run_type=PHM

.\hobl.cmd -p $ARGS[0] -s abl_active global:tools="+phm" global:run_type=PHM
.\hobl.cmd -p $ARGS[0] -s abl_standby global:tools="+phm powercfg" global:run_type=PHM
.\hobl.cmd -p $ARGS[0] -s web global:tools="+phm" global:run_type=PHM
.\hobl.cmd -p $ARGS[0] -s idle_apps global:tools="+phm" global:run_type=PHM
.\hobl.cmd -p $ARGS[0] -s productivity global:tools="+phm" global:run_type=PHM
.\hobl.cmd -p $ARGS[0] -s netflix global:tools="+phm" global:run_type=PHM  
.\hobl.cmd -p $ARGS[0] -s youtube global:tools="+phm" global:run_type=PHM
.\hobl.cmd -p $ARGS[0] -s lvp global:tools="+phm" global:run_type=PHM
.\hobl.cmd -p $ARGS[0] -s teams2_3x3_video global:tools="+phm" global:run_type=PHM
.\hobl.cmd -p $ARGS[0] -s teams2_1on1_audio global:tools="+phm" global:run_type=PHM
.\hobl.cmd -p $ARGS[0] -s teams2_idle global:tools="+phm" global:run_type=PHM

.\hobl.cmd -p $ARGS[0] -s charge_on global:run_type=Misc
.\hobl.cmd -p $ARGS[0] -s study_report global:run_type=Misc
.\hobl.cmd -p $ARGS[0] -s notify global:run_type=Misc notify:plan_run_type=phm

