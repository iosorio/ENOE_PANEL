/*==================================================
project:       Run GLD Quality Checks (canonical)
Author:        World Bank Jobs Group (adapted)
Dependencies:  distinct, mdesc, confirmdir, wbopendata
----------------------------------------------------
Inputs (globals expected):
  qc_harmonized      = path to harmonized .dta
  qc_other_harmonized= optional list of other .dta files (can be " ")
  qc_survey_id       = survey id
  qc_output_dir      = output folder for Q-checks
  qc_helpers_dir     = folder with helper programs
==================================================*/

version 16

* Ensure strict variable matching for checks
set varabbrev off, permanently

* ENOE QC defaults to reduce structural false positives
if "${qc_skip_dict_missing}" == "" global qc_skip_dict_missing "1"
if "${qc_skip_dict_extra}" == "" global qc_skip_dict_extra "1"
if "${qc_allow_numeric_string_vars}" == "" global qc_allow_numeric_string_vars "subnatid1 subnatid2 subnatid3"
if "${qc_ignore_unique_vars}" == "" global qc_ignore_unique_vars "wave unempldur_l unempldur_u unitwage firmsize_l_2 firmsize_u_2"
if "${qc_year_upper}" == "" global qc_year_upper "2100"
if "${qc_wdi_no_data_flag}" == "" global qc_wdi_no_data_flag "99"
if "${qc_skip_wdi}" == "" global qc_skip_wdi "0"

* Validate inputs
if "${qc_harmonized}" == "" {
	display as error "qc_harmonized is not set"
	exit 198
}
if "${qc_survey_id}" == "" {
	display as error "qc_survey_id is not set"
	exit 198
}
if "${qc_output_dir}" == "" {
	display as error "qc_output_dir is not set"
	exit 198
}
if "${qc_helpers_dir}" == "" {
	display as error "qc_helpers_dir is not set"
	exit 198
}
if "${qc_other_harmonized}" == "" {
	global qc_other_harmonized " "
}

* Map canonical globals expected by helper programs
global path_to_harmonization "${qc_harmonized}"
global path_to_other_harmonization "${qc_other_harmonized}"
global survey_id "${qc_survey_id}"
global path_to_output_folder "${qc_output_dir}"
global path_to_helpers "${qc_helpers_dir}"

* Ensure output directory exists
cap mkdir "${path_to_output_folder}"

* Install dependencies
capture which distinct
if _rc ssc install distinct

capture which mdesc
if _rc ssc install mdesc

capture which confirmdir
if _rc ssc install confirmdir

capture which wbopendata
if _rc ssc install wbopendata

* Check inputs exist
capture confirm file "${path_to_harmonization}"
if _rc != 0 {
	display as error "path_to_harmonization file cannot be found"
	exit
}

cap mkdir "${qc_output_diryear}"
cap mkdir "${path_to_output_folder}"
confirmdir "${path_to_output_folder}"
if `r(confirmdir)' != 0 {
	display as error "Folder of path_to_output_folder cannot be found"
	exit
}

cap mkdir "${path_to_helpers}"
confirmdir "${path_to_helpers}"
if `r(confirmdir)' != 0 {
	display as error "Folder of path_to_helpers cannot be found"
	exit
}

* Run static checks
local path_to_static = "${path_to_helpers}/GLD Static Q-Checks.do"
do "`path_to_static'"

* Run dynamic checks
local path_to_dynamic = "${path_to_helpers}/GLD Dynamic Q-Checks.do"
do "`path_to_dynamic'"

* Export postfiles to Excel
local output_dta_files : dir "${path_to_output_folder}" files "*.dta"
local output_png_files : dir "${path_to_output_folder}" files "*.png"
local output_excel_filename = "${path_to_output_folder}/${survey_id}_Q-Checks.xlsx"

foreach filename of local output_dta_files {
	local filename_full_path = "${path_to_output_folder}/`filename'"
	local position_helpr = strpos("`filename'", "q_checks_")
	local sheet_name = regexr(substr("`filename'", `position_helpr' + 44, .), ".dta", "")

	use "`filename_full_path'", clear
	export excel using "`output_excel_filename'", sheet("`sheet_name'") replace
}

foreach filename of local output_png_files {
	local filename_full_path = "${path_to_output_folder}/`filename'"
	local sheet_name = substr("`filename'", 1, strpos("`filename'", ".") - 1)

	putexcel set "`output_excel_filename'", sheet("`sheet_name'") modify
	putexcel A1 = picture(`filename_full_path')
}
