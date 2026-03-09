*v1.0 Quality Checks runner (sequential)

* User 1: Israel Osorio Rodarte
if c(username)=="israel"|c(username)=="Israel" {
	global path "/Users/`c(username)'/Library/CloudStorage/OneDrive-Personal/IOR/Projects/Y2025/FY25_MEX_MinimumWage/ENOE_PANEL"
}

if "$path" == "" {
	global path "`c(pwd)'"
}

cd "$path"
do "$path/Do-files/00_ENOE_Versioning.do"

global qc_helpers_dir "$path/Do-files/Quality_Checks/helpers"
global qc_output_root "$path/Output/Quality_Checks"

local country "$enoe_country"
local survey "$enoe_survey"
local harm_tag "$enoe_harm_tag"

local iniyear = 2005
local finyear = 2025

forvalues yyyy = `iniyear'/`finyear' {
	forvalues q = 1/4 {
		local counter = (`yyyy'-2005)*4 + `q'
		if (`counter'>=1 & `counter'<=61) | (`counter'>=63 & `counter'<=83) {
			local survey_stem "`country'_`yyyy'_`survey'"
			global qc_harmonized "$path/`survey_stem'-Q`q'/`survey_stem'_`harm_tag'/Data/Harmonized/`survey_stem'_`harm_tag'_ALL.dta"
			global qc_survey_id "`survey_stem'_`harm_tag'_ALL"
			global qc_output_diryear "$qc_output_root/by-year/`yyyy'"
			global qc_output_dir "$qc_output_root/by-year/`yyyy'/Q`q'"
			global qc_other_harmonized " "

			do "$path/Do-files/Quality_Checks/QC_Run_All.do"
		}
	}
}
