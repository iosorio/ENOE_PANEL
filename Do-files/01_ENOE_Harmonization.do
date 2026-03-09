*v1.0 iosoriorodarte@worldbank.org
* Reproducibility Package
cap log close step01
*log using "Do-files/Logs/01_ENOE_Harmonization.log", replace name(step01)
* User 1: Israel Osorio Rodarte
if c(username)=="israel"|c(username)=="Israel" {
	global path "/Users/`c(username)'/Library/CloudStorage/OneDrive-Personal/IOR/Projects/Y2025/FY25_MEX_MinimumWage/ENOE_PANEL"
}

cd "$path"
global thedo "$path/Do-files"
do "$path/Do-files/00_ENOE_Versioning.do"
cap mkdir "$thedo/batch"
clear

local country "$enoe_country"
local survey "$enoe_survey"
local harm_tag "$enoe_harm_tag"

*===========================================================================
* Parallel set-up
*===========================================================================

local parallelfile "$thedo/01_ENOE_Harmonization.do"

* If local parallel (below) is set to "yes". Then n batch files are created
* with the name batch_`i'.do located in the working directory.
* The iniyear and finyear locals above are replaced with those in line 91 and 92
* To run: copy and past the routine lines above in terminal or command prompt.

local parallel 	"yes"
		local iniparallelyear = 2005	// First batch file to be created
		local finparallelyear = 2025	// Last batch file to be created
		scalar xrxx = 1			// Do not modify
		scalar xrxy = 1			// Do not modify
		local _fakeiniyear=xrxx	// Do not modify
		local _fakefinyear=xrxy	// Do not modify

	
	if "`parallel'"=="yes" & "`c(os)'"=="MacOSX" {
		cd "$thedo/batch"
		
		* Create myscript.sh
		cap erase myscript.sh
		cap file close myscript
		file open myscript using myscript.sh, write
		
		forval bi = `iniparallelyear'/`finparallelyear' {
			
			* Copy batch file
			!cp "`parallelfile'" "batch_`bi'.do"
			* Replace xrxx and xryy with initial and final years
			!sed -i '' "s/_fakeiniyear=xrxx/iniyear=`bi'/g" batch_`bi'.do
			!sed -i '' "s/_fakefinyear=xrxy/finyear=`bi'/g" batch_`bi'.do
			* Turn off parallel option
			!sed -i '' "s/local[[:space:]]parallel[[:space:]]/*local parallel[[:space:]]/g" batch_`bi'.do
			
			* Append line to myscript.sh
			file write myscript "/usr/local/bin/stata-mp -b do batch_`bi' &" _n
		}
		
		* Close file
		file close myscript
		!chmod +x myscript.sh
		*!./myscript.sh
		etime
		exit
	}

	if "`parallel'"=="yes" & "`c(os)'"=="Windows" {
		cd "$thedo/batch"
		
		* Create myscript.sh
		cap erase myscript.bat
		cap file close myscript
		file open myscript using myscript.bat, write

		forval bi = `iniparallelyear'/`finparallelyear' {
			
			
			* Copy batch file
			!copy "`parallelfile'" "batch_`bi'.do"
			* Replace _fake xrxx and xryy with initial and final years
			!powershell -command " (Get-Content batch_`bi'.do) -replace '_fakeiniyear=xrxx', 'iniyear=`bi'' | Out-File -encoding ASCII batch_`bi'.do "
			!powershell -command " (Get-Content batch_`bi'.do) -replace '_fakefinyear=xrxy', 'finyear=`bi'' | Out-File -encoding ASCII batch_`bi'.do "
			* Turn off parallel option
			!powershell -command " (Get-Content batch_`bi'.do) -replace 'local parallel ', '*local parallel ' | Out-File -encoding ASCII batch_`bi'.do "
			
			* Append line to myscript.sh
			if `bi'==`iniparallelyear' file write myscript `"   "`c(sysdir_stata)'/StataMP-64" /e /i do batch_`bi'.do "'
			else                       file write myscript `" | "`c(sysdir_stata)'/StataMP-64" /e /i do batch_`bi'.do "'
		}
	
		file close myscript	
		!myscript.bat
		etime
		exit	
	}

/*******************************************************************************
* 01_ENOE_Harmonization.do
*******************************************************************************/

* ENOE Harmonization, cycle from 2005.Q1 to 2025.Q3
* Period 62 is ommited. ENOE not available due to COVID-19

	local iniyear = 2005	// Initial year when doing sequential runs
	local finyear = 2025	// Final year when doing sequential runs

	local _fakeiniyear=xrxx
	local _fakefinyear=xrxy
	
	local cycle = 1
	forvalues yyyy = `iniyear'/`finyear' {
	forvalues q = 1/4 {
		
		local counter = (`yyyy'-2005)*4 + `q'
		
                if (`counter'>=1 & `counter'<=61) | (`counter'>=63 & `counter'<=83) {
			local survey_stem "`country'_`yyyy'_`survey'"
			quietly cd "$path/`survey_stem'-Q`q'/`survey_stem'_`harm_tag'/Programs/"
			noi di "`yyyy' `q' - counter: `counter'"
			do "`survey_stem'_`harm_tag'_ALL.do"
		local cycle = `cycle'+1
		}
	}
	}


/*******************************************************************************
* End of 01_ENOE_Harmonization.do
*******************************************************************************/
cap log close step01
