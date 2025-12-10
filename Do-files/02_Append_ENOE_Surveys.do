*v1.0 iosoriorodarte@worldbank.org
* Reproducibility Package
cap log close step02
log using "Do-files/Logs/02_Append_ENOE_Surveys.log", replace name(step02)
clear
/*******************************************************************************
* 02_Append_ENOE_Surveys.do
*******************************************************************************/
			
	****************************************************************************
	* Declare program myfrappend
	****************************************************************************
		cap program drop myfrappend
		program myfrappend
			version 16

			syntax varlist, from(string)

			confirm frame `from'

			foreach var of varlist `varlist' {
				confirm var `var'
				frame `from' : confirm var `var'
			}

			frame `from': local obstoadd = _N

			local startn = _N+1
			set obs `=_N+`obstoadd''

			foreach var of varlist `varlist' {
				replace `var' = _frval(`from',`var',_n-`startn'+1) in `startn'/L
			}
		end
	****************************************************************************			
	
	****************************************************************************
	* Append ENOE Surveys
	****************************************************************************
	
	frame change default
	cap frame drop frameglobal
	
	#delimit ;
	local myvars "weight strata int_month int_year cd_a ent con v_sel n_hog h_mud n_ren emp_ppal urban age 
	              year n_ent male relationharm educy educat7 lstatus industry_orig
				  hhid hsize laborincome mv ingreso tamh pid pob lpT urb tipo subnatid1 subnatid2 subnatid3 cd_a ent mun";
				  
	local myvars2 "weight strata int_month int_year cd_a ent con v_sel n_hog h_mud n_ren emp_ppal urban age 
	              year n_ent male relationharm educy educat7 lstatus industry_orig
				  hhid hsize laborincome mv ingreso tamh pid pob lpT urb      subnatid1 subnatid2 subnatid3 cd_a ent mun";				  
	#delimit cr
	
	local cycle = 1
        forvalues yyyy =  2005/2025 {
	forvalues qq = 1/4 {
		clear
		local counter = (`yyyy'-2005)*4 + `qq'
		
                if (`counter'!=62 & `counter'<=83) {

				noi di "MEX_`yyyy'_ENOE-Q`qq'"
					       cap use `myvars'  using "$path/MEX_`yyyy'_ENOE-Q`qq'/MEX_`yyyy'_ENOE_V01_M_V06_A_GLD/Data/Harmonized/MEX_`yyyy'_ENOE_V01_M_V06_A_GLD_ALL.dta", clear
					if _rc cap use `myvars2' using "$path/MEX_`yyyy'_ENOE-Q`qq'/MEX_`yyyy'_ENOE_V01_M_V06_A_GLD/Data/Harmonized/MEX_`yyyy'_ENOE_V01_M_V06_A_GLD_ALL.dta", clear
				noi di "------"
				noi di ""
				
				gen byte quarter = `qq'
				cap gen tipo = ""
					
			if `cycle' == 1 {	
				frame put _all, into(frameglobal)
				frame change default
			}
			else {
				frame change frameglobal
				quietly myfrappend _all, from(default)
				frame change default
			}
			
			local cycle = `cycle'+1
		}
	}
	}

	frame change frameglobal
	compress
	
	****************************************************************************
	* Format ENOE Surveys
	****************************************************************************
		
	* Delete duplicates
		duplicates report
		duplicates drop

	* Informal/Formal/Unemployed population
		clonevar informal = emp_ppal
			label var informal "Classification of employment by formal/informal/unemployed"
			recode informal (0=3)
			recode informal (2=0)
			label def informal 1 "Informal" 0 "Formal" 3 "Not Employed", replace
			label val informal informal		

	* Check Individual Identifier
		isid year quarter pid

	***************************
	* Generate Panel Variables
	***************************

	egen foliop = concat(cd_a ent con v_sel n_hog h_mud n_ren) if tipo!="2"
	egen folioh = concat(cd_a ent con v_sel n_hog h_mud)       if tipo!="2"

	gen byte time = ((year-2005)*4) + quarter
		label variable time "Time, quarterly (2005.Q1 = 1)"
		
	destring n_ent, replace
	gen byte panel = (time - n_ent) + 1 
		
	label variable panel "Panel Time ID (2005.Q1 to 2006.Q1==1)"
			
	sort panel foliop n_ent
	egen pid_p = group(panel foliop) if tipo!="2"
	
	* Missing month
		cap drop mis_int_month
		bys pid_p: egen mis_int_month = max((int_month == .))
			* drop if mis_int_month == 1 // This is a restriction for q_panel now
		gen datem = ym(int_year,int_month)
		format datem %tm

		gen dateq = yq(int_year,quarter)
		format dateq %tq
		
	* Individuals in Quarterly Panel

	/*SAMPLE RESTRICTIONS*/ 
	/* drop individuals */ 
		gen q_panel = .
			
			// Identifying time frames that permit completion of 5 interviews
			//      Already coded in the variable panel		
			// Marking individuals with 5 interviews
			bys pid_p: gen Ninterviews = _N if pid_p!=.
			
			* Identifying individuals between 15 and 64 throught the sample
			gen _a1564_n = (age>=15 & age<=64) 
			bys pid_p: egen a1564_n = sum(_a1564_n) if pid_p!=.
			gen A1564 = (a1564_n == Ninterviews) if pid_p!=.
				drop _a1564_n a1564_n
				
			* Mark individuals with 3-month interview spans				
			sort pid_p dateq
				by pid_p: gen _timelapse = datem - datem[_n-1] if pid_p!=.
				by pid_p: egen timelapse = mean(_timelapse) if pid_p!=.
				gen timelapse3month = (timelapse == 3) if pid_p!=.
					drop _timelapse timelapse
			
			* Mark individuals suited for panel
			replace q_panel = (Ninterviews>=2 & Ninterviews<=5 & A1564==1 & timelapse3month==1) if panel!=.
			
		label var q_panel "Individuals 15-64, 5 interviews, 3-months"
		
		/* Check sequential interview numbers. 
		The variable n_ent does not always coincide with a sequential interview number 
		(e.g., when unable to interview a household)
		*/
		bys pid_p (dateq): gen int_num = _n if pid_p!=.
		tab int_num n_ent if q_panel==1
				
	* LF Participation
	gen particip = (lstatus == 1 | lstatus == 2) 
		recode particip 0 = . if lstatus == . 
		label define lblparticip 1 "LF Participation" 0 "Out of LF" 
	label values particip lblparticip
	
	compress
	
	order year-int_month quarter panel pid_p
	
	keep foliop folioh q_panel tipo urban age year quarter n_ent male relationharm educy educat7 lstatus informal industry_orig hhid hsize laborincome mv ingreso tamh pid pid_p panel pob lpT urb ///
	     `myvars2'
		 
	save "$path/PANEL/DATA/MEX_2005_2023_ENOE_V01_M_V06_A_GLD_FULLSAMPLE.dta", replace	
	frame reset	

/*******************************************************************************
* 02_Append_ENOE_Surveys.do
*******************************************************************************/
cap log close step02
