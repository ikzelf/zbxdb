if [ $1 = "OpenProblems" ]
then
	/opt/oracle/oak/bin/oakcli show server  >/tmp/zbx_oda.tmp0 2>/dev/null
	if [ -s  /tmp/zbx_oda.tmp0 ]
	then
#	Power State              : On
#	Open Problems            : 0
#	Model                    : ODA X4-2
#	Type                     : Rack Mount
#	Part Number              : 33154356+1+1
#	Serial Number            : 1446NMP006
#	Primary OS               : Not Available
#	ILOM Address             : 172.16.96.230
#	ILOM MAC Address         : 00:10:E0:62:95:8E
#	Description              : Oracle Database Appliance X4-2 1446NMP006
#	Locator Light            : Off
#	Actual Power Consumption : 223 watts
#	Ambient Temperature      : 22.500 degree C
#	Open Problems Report     : System is healthy
	egrep "Open Problems  |Actual Power Consumption|Ambient Temperature" /tmp/zbx_oda.tmp0|
	sed "s/\t *Open Problems *:/OpenProblems:/"                            |
	sed "s/\t *Actual Power Consumption *:/ActualPowerConsumption:/"       |
	sed "s/\t *Ambient Temperature *:/AmbientTemperature:/"                |
	cut -f-2 -d" " | sed "s/://" >/tmp/zbx_oda.tmp
#	OpenProblems: 0
#	ActualPowerConsumption: 211
#	AmbientTemperature: 22.500
	fi
fi
grep $1 /tmp/zbx_oda.tmp|awk '{print $2}'
