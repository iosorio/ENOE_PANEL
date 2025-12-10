*v1.0 iosoriorodarte@worldbank.org
* Reproducibility Package
cap log close step01
log using "Do-files/Logs/01_ENOE_Harmonization.log", replace name(step01)
clear
/*******************************************************************************
* 01_ENOE_Harmonization.do
*******************************************************************************/

* ENOE Harmonization, cycle from 2005.Q1 to 2025.Q3
* Period 62 is ommited. ENOE not available due to COVID-19

        local iniyear = 2005
        local finyear = 2025

	local cycle = 1
	forvalues yyyy = `iniyear'/`finyear' {
	forvalues q = 1/4 {
		
		local counter = (`yyyy'-2005)*4 + `q'
		
                if (`counter'>=1 & `counter'<=61) | (`counter'>=63 & `counter'<=83) {
			quietly cd "$path/MEX_`yyyy'_ENOE-Q`q'/MEX_`yyyy'_ENOE_V01_M_V06_A_GLD/Programs/"
			noi di "`yyyy' `q' - counter: `counter'"
			do "MEX_`yyyy'_ENOE_V01_M_V06_A_GLD_ALL.do"
		local cycle = `cycle'+1
		}
	}
	}


/*******************************************************************************
* End of 01_ENOE_Harmonization.do
*******************************************************************************/
cap log close step01
