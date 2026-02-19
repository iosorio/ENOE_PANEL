*v1.0 Quality Checks runner (sequential)

* User 1: Israel Osorio Rodarte
if c(username)=="israel"|c(username)=="Israel" {
	global path "/Users/`c(username)'/Library/CloudStorage/OneDrive-Personal/IOR/Projects/Y2025/FY25_MEX_MinimumWage/ENOE_PANEL"
}

if "$path" == "" {
	global path "`c(pwd)'"
}

cd "$path"

global qc_helpers_dir "$path/Do-files/Quality_Checks/helpers"
global qc_output_root "$path/Output/Quality_Checks"

local iniyear = 2005
local finyear = 2025

forvalues yyyy = `iniyear'/`finyear' {
	forvalues q = 1/4 {
		local counter = (`yyyy'-2005)*4 + `q'
		if (`counter'>=1 & `counter'<=61) | (`counter'>=63 & `counter'<=83) {
			global qc_harmonized "$path/MEX_`yyyy'_ENOE-Q`q'/MEX_`yyyy'_ENOE_V01_M_V06_A_GLD/Data/Harmonized/MEX_`yyyy'_ENOE_V01_M_V06_A_GLD_ALL.dta"
			global qc_survey_id "MEX_`yyyy'_ENOE_V01_M_V06_A_GLD_ALL"
			global qc_output_diryear "$qc_output_root/by-year/`yyyy'"
			global qc_output_dir "$qc_output_root/by-year/`yyyy'/Q`q'"
			global qc_other_harmonized " "

			do "$path/Do-files/Quality_Checks/QC_Run_All.do"
		}
	}
}
