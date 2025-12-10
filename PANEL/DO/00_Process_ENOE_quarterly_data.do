*! v0.6 iosoriorodarte@worldbank.org 11/18/2023
*! v0.5 iosoriorodarte@worldbank.org 03/24/2023
*! v0.4 iosoriorodarte@worldbank.org 03/02/2023
*! v0.2 esuarezmoran@worldbank.org 12/09/2022
*! v0.1 iosoriordarte@worldbank.org 13/07/2022
/*******************************************************************************
ENOE Surveys from 2005 to 2020 were harmonized using the World Bank 
Global Labor Database (GLD V03 template)
Visit: https://github.com/worldbank/gld

Developed by:
	Israel Osorio Rodarte
	Brenda Samaniego de la Parra
	Eugenia Suarez Moran

* Parallel run in MacOSX is automatic

* Parallel run in Windows is automatic

* References to use the panel
https://github.com/AzaelMateo/ENOE-ENOE_N/blob/main/AM202102_B4ML_3.BasesGlobales.does

* Instructions on how to assemble the panel of workers
https://inegi.org.mx/contenidos/programas/enoe/15ymas/doc/seguimiento_enoe-etoe-enoen.pdf

*******************************************************************************/
clear
frame reset

* User 1: Israel Osorio Rodarte
	if c(username)=="israel"|c(username)=="Israel" {
		global path "/Users/`c(username)'/OneDrive/Data/GLD/MEX copy"
		global temp "$path/PANEL/DATA/temp"
	}

* User 2: Israel Osorio Rodarte (WB308767)
	if c(username)=="WB308767" & c(hostname)=="WBGXDP0663" {
		global path "C:/Users/`c(username)'/OneDrive/Data/GLD/MEX copy"
		global temp "$path/PANEL/DATA/temp"
	}	
	

* To run part0 to part3, write "yes" to activate	
local part0 	"yes" // Re-run GLD harmonization
local part1 	"" // Append cross-section of household surveys data
local part2 	"" // Panel of Workers Quarterly

local iniyear = 2005
local finyear = 2023

local parallel 	"yes"
		local iniparallelyear = 2005
		local finparallelyear = 2023
		local parallel_automatic "yes"
		
/*******************************************************************************
* Parallel Set up
*******************************************************************************/
{
	scalar xrxx = 1			// Do not modify
	scalar xrxy = 1			// Do not modify
	local _fakeiniyear=xrxx	// Do not modify
	local _fakefinyear=xrxy	// Do not modify
	
	
	if "`parallel'"=="yes" & "`c(os)'"=="MacOSX" {
		
		* Create myscript.sh
		cap erase myscript.sh
		cap file close myscript
		file open myscript using myscript.sh, write		
		
		forval bi = `iniparallelyear'/`finparallelyear' {
			cd "$path/PANEL/DO/"
			!cp "00_Process_ENOE_quarterly_data.do" "batch_`bi'.do"
			* Replace xrxx and xryy with initial and final years
			!sed -i '' "s/_fakeiniyear=xrxx/iniyear=`bi'/g" batch_`bi'.do
			!sed -i '' "s/_fakefinyear=xrxy/finyear=`bi'/g" batch_`bi'.do
			* Turn off parallel option
			!sed -i '' "s/local[[:space:]]parallel/*local parallel/g" batch_`bi'.do
			
			* Append line to myscript.sh
			file write myscript "/usr/local/bin/stata-mp -b do batch_`bi' &" _n
		}
		* Close file
		file close myscript	
		!chmod u+rx myscript.sh
		if "`parallel_automatic'"=="yes" {
			!./myscript.sh	
		}
		exit	
	}

	if "`parallel'"=="yes" & "`c(os)'"=="Windows" {
		
		* Create myscript.sh
		cap erase myscript.bat
		cap file close myscript
		file open myscript using myscript.bat, write		
		
		forval bi = `iniparallelyear'/`finparallelyear' {
			cd "$path/Do-files"
			!copy "00_Process_ENOE_quarterly_data.do" "batch_`bi'.do"
			* Replace _fake xrxx and xryy with initial and final years
			!powershell -command " (Get-Content batch_`bi'.do) -replace '_fakeiniyear=xrxx', 'iniyear=`bi'' | Out-File -encoding ASCII batch_`bi'.do "
			!powershell -command " (Get-Content batch_`bi'.do) -replace '_fakefinyear=xrxy', 'finyear=`bi'' | Out-File -encoding ASCII batch_`bi'.do "
			* Turn off parallel option
			!powershell -command " (Get-Content batch_`bi'.do) -replace 'local parallel', '*local parallel' | Out-File -encoding ASCII batch_`bi'.do "
			
			* Append line to myscript.sh
			if `bi'==`iniparallelyear' file write myscript `"   "`c(sysdir_stata)'/StataMP-64" /e /i do batch_`bi'.do "'
			else                       file write myscript `" | "`c(sysdir_stata)'/StataMP-64" /e /i do batch_`bi'.do "'
		}
		* Close file
		file close myscript	
		if "`parallel_automatic'"=="yes" !myscript.bat		
		exit	
	}	
}
********************************************************************************
* Part 0. Re-run GLD / Can be run in parallel mode
********************************************************************************
if "`part0'"=="yes" {
	
	local cycle = 1
	forvalues yyyy = `iniyear'/`finyear' {
	forvalues q = 1/4 {
		
		local counter = (`yyyy'-2005)*4 + `q'
		
		if (`counter'>=1 & `counter'<=61) | (`counter'>=63 & `counter'!=.) {
			quietly cd "$path/MEX_`yyyy'_ENOE-Q`q'/MEX_`yyyy'_ENOE_V01_M_V06_A_GLD/Programs/"
			noi di "`yyyy' `q' - counter: `counter'"
			do "MEX_`yyyy'_ENOE_V01_M_V06_A_GLD_ALL.do"
		local cycle = `cycle'+1
		}
	}
	}
}

********************************************************************************
* End of do-file
********************************************************************************


