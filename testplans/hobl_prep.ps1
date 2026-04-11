if ($ARGS[0] -eq $null) {return("Params .ini not supplied, please supply a params .ini parameter.")}
.\hobl.cmd -p $ARGS[0] -s charge_on post_run_delay=0
.\hobl.cmd -p $ARGS[0] -s net_prep attempts=2 connection=Wi-Fi post_run_delay=0
.\hobl.cmd -p $ARGS[0] -s os_install post_run_delay=0

.\hobl.cmd -p $ARGS[0] -s prep post_run_delay=0 prep:scenarios_to_prep="abl_active cs_floor lvp teams"

.\hobl.cmd -p $ARGS[0] -s net_prep attempts=2 post_run_delay=0
.\hobl.cmd -p $ARGS[0] -s version_report post_run_delay=0
.\hobl.cmd -p $ARGS[0] -s notify post_run_delay=0  
.\hobl.cmd -p $ARGS[0] -s run_hobl_if_preps_passed post_run_delay=0