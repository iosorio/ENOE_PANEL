*v1.0 Quality Checks runner (parallel)

* User 1: Israel Osorio Rodarte
if c(username)=="israel"|c(username)=="Israel" {
	global path "/Users/`c(username)'/Library/CloudStorage/OneDrive-Personal/IOR/Projects/Y2025/FY25_MEX_MinimumWage/ENOE_PANEL"
}

if "$path" == "" {
	global path "`c(pwd)'"
}

cd "$path"
cap mkdir "$path/Do-files/Quality_Checks/batch"

global qc_helpers_dir "$path/Do-files/Quality_Checks/helpers"
global qc_output_root "$path/Output/Quality_Checks"

*=========================================================================== 
* Parallel set-up (mirrors 01_ENOE_Harmonization.do)
*===========================================================================

local parallelfile "$path/Do-files/Quality_Checks/00_Run_All_Parallel.do"

local parallel "yes"
	local iniparallelyear = 2005
	local finparallelyear = 2025
	scalar xrxx = 1
	scalar xrxy = 1
	local _fakeiniyear=xrxx
	local _fakefinyear=xrxy

if "`parallel'"=="yes" & "`c(os)'"=="MacOSX" {
	cd "$path/Do-files/Quality_Checks/batch"
	cap erase myscript.sh
	cap file close myscript
	file open myscript using myscript.sh, write

	forval bi = `iniparallelyear'/`finparallelyear' {
		!cp "`parallelfile'" "batch_`bi'.do"
		!sed -i '' "s/_fakeiniyear=xrxx/iniyear=`bi'/g" batch_`bi'.do
		!sed -i '' "s/_fakefinyear=xrxy/finyear=`bi'/g" batch_`bi'.do
		!sed -i '' "s/local[[:space:]]parallel[[:space:]]/*local parallel[[:space:]]/g" batch_`bi'.do
		file write myscript "/usr/local/bin/stata-mp -b do batch_`bi' &" _n
	}
	file close myscript
	!chmod +x myscript.sh
	*!./myscript.sh
	etime
	exit
}

if "`parallel'"=="yes" & "`c(os)'"=="Windows" {
	cd "$path/Do-files/Quality_Checks/batch"
	cap erase myscript.bat
	cap file close myscript
	file open myscript using myscript.bat, write

	forval bi = `iniparallelyear'/`finparallelyear' {
		!copy "`parallelfile'" "batch_`bi'.do"
		!powershell -command " (Get-Content batch_`bi'.do) -replace '_fakeiniyear=xrxx', 'iniyear=`bi'' | Out-File -encoding ASCII batch_`bi'.do "
		!powershell -command " (Get-Content batch_`bi'.do) -replace '_fakefinyear=xrxy', 'finyear=`bi'' | Out-File -encoding ASCII batch_`bi'.do "
		!powershell -command " (Get-Content batch_`bi'.do) -replace 'local parallel ', '*local parallel ' | Out-File -encoding ASCII batch_`bi'.do "
		if `bi'==`iniparallelyear' file write myscript `"   "`c(sysdir_stata)'/StataMP-64" /e /i do batch_`bi'.do "'
		else                       file write myscript `" | "`c(sysdir_stata)'/StataMP-64" /e /i do batch_`bi'.do "'
	}
	file close myscript
	!myscript.bat
	etime
	exit
}

/*******************************************************************************
* Sequential runner (used by batch files)
*******************************************************************************/

local iniyear = 2005
local finyear = 2025

local _fakeiniyear=xrxx
local _fakefinyear=xrxy

forvalues yyyy = `iniyear'/`finyear' {
	forvalues q = 1/4 {
		local counter = (`yyyy'-2005)*4 + `q'
		if (`counter'>=1 & `counter'<=61) | (`counter'>=63 & `counter'<=83) {
			global qc_harmonized "$path/MEX_`yyyy'_ENOE-Q`q'/MEX_`yyyy'_ENOE_V01_M_V06_A_GLD/Data/Harmonized/MEX_`yyyy'_ENOE_V01_M_V06_A_GLD_ALL.dta"
			global qc_survey_id "MEX_`yyyy'_ENOE_V01_M_V06_A_GLD_ALL"
			global qc_output_dir "$qc_output_root/by-year/`yyyy'/Q`q'"
			global qc_other_harmonized " "

			do "$path/Do-files/Quality_Checks/QC_Run_All.do"
		}
	}
}
