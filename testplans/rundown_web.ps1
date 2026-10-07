if ($ARGS[0] -eq $null) {return("Params .ini not supplied, please supply a params .ini parameter.")}

.\hobl.cmd -p $ARGS[0] -s charge_on
.\hobl.cmd -p $ARGS[0] -s wait_for_dut
.\hobl.cmd -p $ARGS[0] -s process_idle_tasks process_idle_tasks:timeout=7200 process_idle_tasks:loops=1
.\hobl.cmd -p $ARGS[0] -s recharge post_charge_delay=1800
.\hobl.cmd -p $ARGS[0] -s web web:loops="100" global:rundown_mode=1 global:stop_soc=0 global:crit_batt_level=3 screenshot:pause=3600 global:tools="+power_light powercfg auto_charge"
.\hobl.cmd -p $ARGS[0] -s charge_on
.\hobl.cmd -p $ARGS[0] -s study_report