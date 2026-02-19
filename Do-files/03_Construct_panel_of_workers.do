*v1.0 iosoriorodarte@worldbank.org
* Reproducibility Package
cap log close step03
log using "Do-files/Logs/03_Construct_panel_of_workers.log", replace name(step03)
clear
/*******************************************************************************
* 03_Construct_panel_of_workers.do
*******************************************************************************/

	local panel_start_year = 2005
	if "$panel_start_year" != "" local panel_start_year = real("$panel_start_year")

	local panel_end_year = `panel_start_year'
	if "$panel_end_year" != "" local panel_end_year = real("$panel_end_year")

	local panel_end_quarter = 4
	if "$panel_end_quarter" != "" local panel_end_quarter = real("$panel_end_quarter")

	if `panel_end_quarter' < 1 | `panel_end_quarter' > 4 {
		di as error "panel_end_quarter must be in 1..4"
		exit 198
	}
	if `panel_end_year' < `panel_start_year' {
		di as error "panel_end_year must be >= panel_start_year"
		exit 198
	}

	local panel_tag "`panel_start_year'_`panel_end_year'Q`panel_end_quarter'"
	local fullsample_file "$path/PANEL/DATA/MEX_`panel_tag'_ENOE_V01_M_V06_A_GLD_FULLSAMPLE.dta"
	local fullsample_latest "$path/PANEL/DATA/MEX_ENOE_V01_M_V06_A_GLD_FULLSAMPLE_latest.dta"
	local panel_file "$path/PANEL/DATA/MEX_`panel_tag'_PANEL_QUARTER.dta"
	local panel_latest "$path/PANEL/DATA/MEX_PANEL_QUARTER_latest.dta"

	cap confirm file "`fullsample_file'"
	if _rc {
		cap confirm file "`fullsample_latest'"
		if _rc {
			di as error "Full sample input not found: `fullsample_file'"
			exit 601
		}
		local fullsample_file "`fullsample_latest'"
	}

	* Create a balance database
	use pid_p n_ent q_panel tipo if q_panel==1 using "`fullsample_file'", clear
		tab tipo, m
		drop tipo
		duplicates report 
		
		reshape wide q_panel, i(pid_p) j(n_ent)
		reshape long q_panel, i(pid_p) j(n_ent)
		
		* Identify individuals that missed the first interview
			gen _miss_first = 1 if q_panel==. & n_ent==1
			by pid_p: egen miss_first = sum(_miss_first)
		
			clonevar q_panel2 = q_panel
			replace  q_panel2 = . if miss_first==1
				drop _miss_first
				drop q_panel
			
			keep if q_panel2==1
			drop miss_first

		reshape wide q_panel2, i(pid_p) j(n_ent)
		reshape long q_panel2, i(pid_p) j(n_ent)
			replace q_panel2=1 
			
		tab n_ent
		isid pid_p n_ent
		tempfile balanced
		save `balanced', replace
	
	* Recover full database
	use "`fullsample_file'", clear
	count
	
	* Panel that follows workers for up to 5 quarters
		keep if q_panel==1
		* duplicates report pid_p dateq
		tempfile data
		save `data', replace
		
	use `balanced'
	merge 1:1 pid_p n_ent using `data'
		order q_panel, before(q_panel2)
		keep if q_panel2==1
		drop _merge
		xtset pid_p n_ent	// This should be a strongly balanced panel
		
	* Saving rotating panel data with the 5 interviews/quarters
	compress
	save "`panel_file'", replace
	copy "`panel_file'" "`panel_latest'", replace
	count
	frame reset

cap log close step03

/*******************************************************************************
* End of 03_Construct_panel_of_workers.do
*******************************************************************************/
cap log close step03
