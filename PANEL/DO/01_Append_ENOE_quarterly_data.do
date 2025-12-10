*! v0.6 iosoriorodarte@worldbank.org 11/18/2023
*! v0.5 iosoriorodarte@worldbank.org 03/24/2023
*! v0.4 iosoriorodarte@worldbank.org 03/02/2023
*! v0.2 esuarezmoran@worldbank.org 12/09/2022
*! v0.1 iosoriordarte@worldbank.org 13/07/2022
/*******************************************************************************
ENOE Surveys from 2005 to 2020 were harmonized using the World Bank 
Global Labor Database (GLD V03 template)
Visit: https://github.com/worldbank/gld

	Code to calculate attrition weights
	Developed by:
		Israel Osorio Rodarte
		Brenda Samaniego de la Parra
		Eugenia Suarez Moran

* Parallel run in MacOSX is automatic

* Parallel run in Windows is automatic

* References to use the panel
https://github.com/AzaelMateo/ENOE-ENOE_N/blob/main/AM202102_B4ML_3.BasesGlobales.does
* Very important explanation on how to assemble the panel
https://inegi.org.mx/contenidos/programas/enoe/15ymas/doc/seguimiento_enoe-etoe-enoen.pdf

		
*******************************************************************************/
clear
frame reset

* User 1: Israel Osorio Rodarte
	if c(username)=="israel"|c(username)=="Israel" {
		global path "/Users/`c(username)'/OneDrive/Data/GLD/MEX copy"
		global panjiva "/Users/`c(username)'/OneDrive/Data/Panjiva/Exports Shipper Report"
		global temp "$path/PANEL/DATA/temp"
		global paper "/Users/`c(username)'/OneDrive/Authors Workshop/Draft and notes/graphs"
	}

* User 2: Eugenia Suarez Moran (WB406475)
	if "`c(os)'"=="Windows" & "`c(username)'"=="wb406475" {
		global path "C:/Users/wb406475/OneDrive/Data/GLD/MEX copy"
		global panjiva "C:/Users/wb406475/OneDrive/Data/Panjiva/Exports Shipper Report"
		global temp "$path/PANEL/DATA/temp"
	}

* User 3: WB308767
	if c(username)=="WB308767" & c(hostname)=="WBGXDP0663" {
		global path "C:/Users/`c(username)'/OneDrive/Data/GLD/MEX copy"
		global panjiva "C:/Users/`c(username)'/OneDrive/Data/Panjiva/Exports Shipper Report"
		global temp "$path/PANEL/DATA/temp"
		global paper "/Users/`c(username)'/OneDrive/Authors Workshop/Draft and notes/graphs"
	}	
	
	
local part0 	"yes" // Re-run GLD
local part1 	"" // append panel data
local part2 	"" 	// Panel of Workers Quarterly
local part21 	""	// Statistics by city
local part3 	""	// probabilities
local part31	""
local part32	""

local mygvarlist "occupjobs"	// informal

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
		cd "$path/PANEL/DO"
		cap erase myscript.sh
		cap file close myscript
		file open myscript using myscript.sh, write		
		
		forval bi = `iniparallelyear'/`finparallelyear' {
			cd "$path/PANEL/DO"
			!cp "01_Append_ENOE_quarterly_data.do" "batch_`bi'.do"
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
			cd "$path/PANEL/DO"
			!copy "01_Append_ENOE_quarterly_data.do" "batch_`bi'.do"
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
* Part 0. Re-run GLD
********************************************************************************
if "`part0'"=="yes" {
	
	local cycle = 1
	forvalues yyyy = `iniyear'/`finyear' {
	forvalues q = 1/4 {
		
		local counter = (`yyyy'-2005)*4 + `q'
		
		if (`counter'>=1 & `counter'<=61) | (`counter'>=63 & `counter'<=75) {
			quietly cd "$path/MEX_`yyyy'_ENOE-Q`q'/MEX_`yyyy'_ENOE_V01_M_V06_A_GLD/Programs/"
			noi di "`yyyy' `q' - counter: `counter'"
			do "MEX_`yyyy'_ENOE_V01_M_V06_A_GLD_ALL.do"
		local cycle = `cycle'+1
		}
	}
	}
}

********************************************************************************
* Part 1. Append Panel and Incorporate Variables
********************************************************************************
if "`part1'"=="yes" {
			
	****************************************************************************
	* Declare myfrappend
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
			
	frame change default
	cap frame drop frameglobal
	
	local cycle = 1
	forvalues yyyy =  `iniyear'/`finyear' {
	forvalues qq = 1/4 {
		clear
		local counter = (`yyyy'-2005)*4 + `qq'
		
		if (`counter'!=62) {

				noi di "MEX_`yyyy'_ENOE-Q`qq'"
					use "$path/MEX_`yyyy'_ENOE-Q`qq'/MEX_`yyyy'_ENOE_V01_M_V06_A_GLD/Data/Harmonized/MEX_`yyyy'_ENOE_V01_M_V06_A_GLD_ALL.dta", clear
				noi di "------"
				noi di ""
		
			* Add quarter variable
			qui {
				cap gen byte quarter = `qq'
				cap gen union = . 
				cap gen healthins = . 
				cap gen subnatid3 = .
				cap gen socialsec = .	
				cap gen industrycat_isic = .
				cap gen industrycat10 = .
				cap gen industrycat4 = .
				cap gen industrycat_isic_2 = . 
				cap gen industrycat10_2 = .
				cap gen industrycat4_2 = .
				cap gen p3r_anio = .
				cap gen p3r_mes = .
				cap gen p3r = .
				cap gen p3s = . 
				cap gen p3t = .
				cap gen p3t_anio = .
				cap gen p3t_mes = .
				cap gen loc = .
				cap gen mun = .
				cap gen firmsize_l_2 = .
				cap gen tipo = ""
				cap gen mes_cal = ""
				cap gen ca = ""
				
				foreach var in p2a_dia p2a_sem p2a_mes p2a_anio p2b_dia  p2b_sem p2b_mes p2b_anio p2b p2d1 ///
							   p2d2 p2d3 p2d4 p2d5 p2d6 p2d7 p2d8 p2d9 p2d10 p2d11 p2d99 p3n p3r_anio		///
							   p3r_mes p3r p3s p3t_anio p3t_mes {
					cap gen `var' = .
				}
				
			}

			* APPEND FRAMES
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
	
	* Delete duplicates
		duplicates report
		duplicates drop

	* Clean unnecesary variables
		drop countrycode survname survey vermast veralt harmonization subnatid3 loc

	* Encode string variables
		foreach var in icls_v isced_version isco_version isic_version subnatid1 subnatid2 {
			capture confirm numeric variable `var'
			if _rc {
				encode `var', gen(s`var')
				drop `var'
				rename s`var' `var'
			}
			else {
				noi di "Variable `var' is already numberic"
			}
		}
		
	* Informal/Formal/Unemployed population
		clonevar informal = emp_ppal
			label var informal "Classification of employment by formal/informal/unemployed"
			recode informal (0=3)
			recode informal (2=0)
			label def informal 1 "Informal" 0 "Formal" 3 "Not Employed", replace
			label val informal informal		
	
	* Fix wrong label in subnatid1
		label de lblsubnatid1 1 "Aguascalientes" 2 "Baja California" 3 "Baja California Sur" 4 "Campeche" 5 "Coahuila de Zaragoza" 6 "Colima" 7 "Chiapas" 8 "Chihuahua" 9 "Ciudad de Mexico" 10 "Durango" 11 "Guanajuato" 12 "Guerrero" 13 "Hidalgo" 14 "Jalisco" 15 "Mexico" 16 "Michoacan de Ocampo" 17 "Morelos" 18 "Nayarit" 19 "Nuevo Leon" 20 "Oaxaca" 21 "Puebla" 22 "Queretaro de Arteaga" 23 "Quintana Roo" 24 "San Luis Potosi" 25 "Sinaloa" 26 "Sonora" 27 "Tabasco" 28 "Tamaulipas" 29 "Tlaxcala" 30 "Veracruz de Ignacio de la Llave" 31 "Yucatan" 32 "Zacatecas", replace
		label values subnatid1 lblsubnatid1

	* Fix labels in subnatid2
		label define lblsubnatid2 1 "Ciudad de Mexico" 2 "Guadalajara" 3 "Monterrey" 4 "Puebla" 5 "Leon" 6 "Torreon" 7 "San Luis Potosi" 8 "Merida" 9 "Chihuahua" 10 "Tampico" 12 "Veracruz" 13 "Acapulco" 14 "Aguascalientes" 15 "Morelia" 16 "Toluca" 17 "Saltillo" 18 "Villahermosa" 19 "Tuxtla Gutierrez" 20 "Juarez" 21 "Tijuana" 24 "Culiacan" 25 "Hermosillo" 26 "Durango" 27 "Tepic" 28 "Campeche" 29 "Cuernavaca" 30 "Coatzacoalcos" 31 "Oaxaca" 32 "Zacatecas" 33 "Colima" 36 "Queretaro" 39 "Tlaxcala" 40 "La Paz" 41 "Cancun" 42 "Ciudad del Carmen" 43 "Pachuca" 44 "Mexicali" 46 "Reynosa" 52 "Tapachula" 81 "Complemento Urbano Rural", replace
		label values subnatid2 lblsubnatid2

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
		
		** RECODE/replace VARIABLES THAT ARE ONLY CAPTURED DURING EMPLOYMENT SPELLS 
		gen firmsizev2 = firmsize_l 
		recode firmsizev2 .= 0 if lstatus == 2 | lstatus == 3
		
	* SVYSET
		svyset psu [pweight=weight], strata(strata)
	
	* LF Participation
	gen particip = (lstatus == 1 | lstatus == 2) 
		recode particip 0 = . if lstatus == . 
		label define lblparticip 1 "LF Participation" 0 "Out of LF" 
	label values particip lblparticip
	
	* IND
	rename industrycat10 ind

	* Age Category
	gen age_catego = round(age/10,1)
	
	* Married
	gen married    = (marital== 1)
	
	* There are unlabeled occupations. Will recode as "NA"
	* Will also code as NA if occup or ind is missing but lstatus = employed
	foreach v in ind occup {

		local lbe`v' : value label `v'
		label list `lbe`v''
		local tc = `r(max)'+1
		recode `v' 0 = `tc' if lstatus == 1
		recode `v' . = `tc' if lstatus == 1
		label define `lbe`v'' `tc' "NA", add
		
		count if `v' == 0 
		local nn = `r(N)'
		if `nn' == 0 {
			recode `v' . = 0 if lstatus == 2 | lstatus == 3
			local lbe`v' : value label `v'
			label define `lbe`v'' 0 "Not Employed", add
			
		} 
		else { 
			local lbe`v' : value label `v'
			label list `lbe`v''
			local tc = `r(max)'+1
			recode `v' . = `tc' if lstatus == 2 | lstatus == 3
			label define `lbe`v'' `tc' "Not Employed", add
		} 
	}	
	
	* Municipalities in ENOE can be at the same time part of a city and part of
	* "Complemento Urbano Rural". This is problematic for the merge.
	* In order to have a consistent treatment, whenever a municipality is part of
	* both, a city and the "Complemento Urbano Rural", it will be assigned in
	* its entirety to the city
	clonevar state = subnatid1
	clonevar city  = subnatid2
	
	preserve
		contract mun state city
			drop _freq
			* First, we keep only municipalities that are part of a city
			drop if city==81
			count
				local muncities = r(N)
			drop if mun==.
			
			order state city mun
			sort  state city mun
			
			* Rename the city, before merging this contracted database with 
			* the original one
			clonevar newcity = city		
			replace city = 81
			tempfile torecode
			save `torecode', replace
	restore
	
	merge m:1 state city mun using `torecode'
		drop if _merge==2
		noi di "Total Municipalities in Cities: " `muncities'
		
		replace city = newcity if _merge==3
		drop newcity
		drop _merge
	
	* Generating variable to merge with Panjiva
	gen str3 state1 = string(state, "%02.0f") // Nice way of doing it
	gen str3 mnpio = string(mun, "%03.0f")	  // Nice way of doing it
	gen c_mnpio = "9" + state1 + mnpio
	destring c_mnpio, replace
		drop state1 mnpio
			
	merge m:1 year quarter c_mnpio using "$panjiva/Quarterly Exports by Municipality and SIC Division and GOB.dta"
		drop if _merge==2 & year==2022
		drop if _merge==2 & year==2021
		drop if _merge==2 & year==2020 & quarter==2
		drop if _merge==2 & year==2020 & quarter==3
		drop if _merge==2 & year==2020 & quarter==4
		tab _merge
			gen byte panjiva = 2 if (_merge==2)	// Check that I don't have municipalities 
											// in Panjiva that do not appear in ENOE
		drop _merge
	
	bys year quarter c_mnpio: replace panjiva = 1 if (_n==1) & panjiva==.
	
	foreach var of varlist exports_mnpio* {
		replace `var' = 0 if exports_mnpio==.
	}

	table panjiva if (panjiva!=.) & year==2019, stat(sum exports_mnpio) 
	
	* Calculate exports at the city level - Panjiva
	preserve
		drop if year<2011
		keep if panjiva==1
		
		collapse (sum) exports_mnpio* , by(year quarter state city)
			rename exports_mnpio exports_city
			foreach letter in A B C D E F G H I J NA {
				rename exports_mnpio_`letter' exports_city_`letter'
			}
		
		tempfile exports_city
		save `exports_city', replace
	restore
	
		merge m:1 year quarter state city using `exports_city'
		bys year quarter state city: gen byte panjivacity = 1 if _n==1
		drop _merge
		table panjiva if (panjiva!=.) & year==2019, stat(sum exports_mnpio) 	
		
		foreach letter in A B C D E F G H I J NA {
			local lblA "Div. A - Agr., Forstry, Fishing"
			local lblB "Div. B - Mining"
			local lblC "Div. C - Construction Industry"
			local lblD "Div. D - Manufacturing"
			local lblE "Div. E -Transport., Com., Util."
			local lblF "Div. F - Wholesale Trade"
			local lblG "Div. G - Retail Trade"
			local lblH "Div. H - Fin., Ins., RE."
			local lblI "Div. I - Service Industries"
			local lblJ "Div. J - Public Administration"
			
			label var exports_mnpio_`letter' "`lbl`letter'' Exports by municipality, USD millions"
			label var exports_city_`letter'  "`lbl`letter'' Exports by city, USD millions"
		
		}
		
		
	* Calculate exports at the city level - GOB
	preserve
		
		collapse (sum) exgob* imgob* , by(year quarter state city)
			
			forval letter = 1/21 {
				rename exgob_mnpioID`letter' exgob_cityID`letter'
				rename imgob_mnpioID`letter' imgob_cityID`letter'
			}
		
		tempfile exgob_city
		save `exgob_city', replace
	restore
	
		merge m:1 year quarter state city using `exgob_city'
		bys year quarter state city: gen byte gobcity = 1 if _n==1
		drop _merge
		
	foreach f in ex im {
		
		if "`f'"=="ex" local flabel "Exports"
		if "`f'"=="im" local flabel "Imports"
		
		label var `f'gob_cityID1	"`flabel' Animal Products"
		label var `f'gob_cityID2	"`flabel' Vegetable Products"
		label var `f'gob_cityID3	"`flabel' Animal and Vegetable Bi-Products"
		label var `f'gob_cityID4	"`flabel' Foodstuffs"
		label var `f'gob_cityID5	"`flabel' Mineral Products"
		label var `f'gob_cityID6	"`flabel' Chemical Products"
		label var `f'gob_cityID7	"`flabel' Plastics and Rubbers"
		label var `f'gob_cityID8	"`flabel' Animal Hides"
		label var `f'gob_cityID9	"`flabel' Wood Products"
		label var `f'gob_cityID10	"`flabel' Paper Goods"
		label var `f'gob_cityID11	"`flabel' Textiles"
		label var `f'gob_cityID12	"`flabel' Footwear and Headwear"
		label var `f'gob_cityID13	"`flabel' Stone and Glass"
		label var `f'gob_cityID14	"`flabel' Precious Metals"
		label var `f'gob_cityID15	"`flabel' Metals"
		label var `f'gob_cityID16	"`flabel' Machines"
		label var `f'gob_cityID17	"`flabel' Transportation"
		label var `f'gob_cityID18	"`flabel' Instruments"
		label var `f'gob_cityID19	"`flabel' Weapons"
		label var `f'gob_cityID20	"`flabel' Miscellaneous"
		label var `f'gob_cityID21	"`flabel' Arts and Antiques"
	}
		
		
	* Generate Mesoregion
	
		gen byte mesoregion = 0
			* Mesorregion Noroeste
			foreach ms in 2 3 26 25 {
				replace mesoregion = 1 if subnatid1==`ms'
			}
			* Mesorregion Noreste
			foreach ms in 8 10 5 19 28 {
				replace mesoregion = 2 if subnatid1==`ms'
			}
			* Mesorregion Centro
			foreach ms in 13 21 29 22 9 17 16 {
				replace mesoregion = 3 if subnatid1==`ms'
			}
			* Mesorregion Pacifico Occidente
			foreach ms in 1 11 24 32 6 14 15 18 {
				replace mesoregion = 4 if subnatid1==`ms'
			}	
			* Mesorregion Sur Sureste
			foreach ms in 4 23 27 30 31 7 12 20 {
				replace mesoregion = 5 if subnatid1==`ms'
			}
			
		#delimit ;
			label define lblmesoregion
			1 "Northwest"
			2 "Northeast"
			3 "Central"
			4 "Pacific West"
			5 "South & Southeast", replace;
		#delimit cr
		label values mesoregion lblmesoregion

	replace mesoregion = 3 if city==1
	replace mesoregion = 2 if city==10		
	
	* Workers by municipality
		gen _worker = weight if age>=15 & age<=64 & lstatus==1
		bys year quarter c_mnpio: egen double workers_mnpio = sum(_worker)
		drop _worker
	
	* Replace long labels for ind
	#delimit ;
	label define lblind 
           0 "Not Emp"
           1 "Agriculture"
           2 "Mining"
           3 "Manuf"
           4 "Public ut"
           5 "Const"
           6 "Commerce"
           7 "T and C"
           8 "F and BS"
           9 "Public Adm"
          10 "Other Serv"
          11 "NA", replace;
	#delimit cr
	label values ind lblind
	
	* Replace long labels for occup
	#delimit ;
	label define lbloccup
		   0 "Not Emp"
           1 "Man"
           2 "Prof"
           3 "Tech"
           4 "Clerks"
           5 "S and msw"
           6 "Sk agri"
           7 "Craft w"
           8 "Machine op"
           9 "Elem occup"
          10 "Armed f"
          99 "Others"
         100 "NA", replace;
	#delimit cr
	label values occup lbloccup
		
	* gen industry broad
		gen indbroad = . 
			replace indbroad = 0 if ind==0
			replace indbroad = 1 if ind==1|ind==2
			replace indbroad = 2 if ind==3
			replace indbroad = 3 if ind==4|ind==5
			replace indbroad = 4 if ind==6|ind==7
			replace indbroad = 5 if ind==8|ind==9|ind==10|ind==11
		
	#delimit ;
	label define lblindbroad 
           0 "Not Emp"
           1 "Primary"
           2 "Manuf"
           3 "PubU Cons"
           4 "Comm TC"
           5 "Other S";
	#delimit cr
	label values indbroad lblindbroad	
	
	* generate occupation broad
	gen occup_orig2 = int(occup_orig/100)
	gen occup_orig3 = int(occup_orig/10)
	gen occupbroad = .
		replace occupbroad = 0 if occup==0
		
	replace occupbroad = 1 if occup_orig3==111
	replace occupbroad = 1 if occup_orig3==112
	replace occupbroad = 1 if occup_orig3==113

	replace occupbroad = 2 if occup_orig3==121
	replace occupbroad = 2 if occup_orig3==122

	replace occupbroad = 2 if occup_orig3==131
	replace occupbroad = 2 if occup_orig3==132

	replace occupbroad = 2 if occup_orig3==141
	replace occupbroad = 2 if occup_orig3==142

	replace occupbroad = 2 if occup_orig3==151
	replace occupbroad = 2 if occup_orig3==152

	replace occupbroad = 2 if occup_orig3==161
	replace occupbroad = 2 if occup_orig3==162

	replace occupbroad = 2 if occup_orig3==171
	replace occupbroad = 2 if occup_orig3==172

	replace occupbroad = 2 if occup_orig3==199

	replace occupbroad = 6 if occup_orig3==211
	replace occupbroad = 6 if occup_orig3==212
	replace occupbroad = 6 if occup_orig3==213
	replace occupbroad = 6 if occup_orig3==214
	replace occupbroad = 6 if occup_orig3==215
	replace occupbroad = 6 if occup_orig3==216
	replace occupbroad = 6 if occup_orig3==217

	replace occupbroad = 3 if occup_orig3==221
	replace occupbroad = 3 if occup_orig3==222
	replace occupbroad = 3 if occup_orig3==223
	replace occupbroad = 3 if occup_orig3==224
	replace occupbroad = 3 if occup_orig3==225
	replace occupbroad = 3 if occup_orig3==226
	replace occupbroad = 3 if occup_orig3==227
	replace occupbroad = 3 if occup_orig3==228

	replace occupbroad = 5 if occup_orig3==231
	replace occupbroad = 5 if occup_orig3==232
	replace occupbroad = 5 if occup_orig3==233
	replace occupbroad = 5 if occup_orig3==234

	replace occupbroad = 4 if occup_orig3==241
	replace occupbroad = 4 if occup_orig3==242

	replace occupbroad = 6 if occup_orig3==251
	replace occupbroad = 6 if occup_orig3==252
	replace occupbroad = 6 if occup_orig3==253
	replace occupbroad = 6 if occup_orig3==254
	replace occupbroad = 6 if occup_orig3==255
	replace occupbroad = 6 if occup_orig3==256

	replace occupbroad = 3 if occup_orig3==261
	replace occupbroad = 3 if occup_orig3==262
	replace occupbroad = 3 if occup_orig3==263
	replace occupbroad = 3 if occup_orig3==264
	replace occupbroad = 3 if occup_orig3==265
	replace occupbroad = 3 if occup_orig3==266

	replace occupbroad = 5 if occup_orig3==271

	replace occupbroad = 4 if occup_orig3==281
	replace occupbroad = 4 if occup_orig3==282

	replace occupbroad = 6 if occup_orig3==299

	replace occupbroad = 7 if occup_orig3==310
	replace occupbroad = 7 if occup_orig3==311
	replace occupbroad = 7 if occup_orig3==312
	replace occupbroad = 7 if occup_orig3==313
	replace occupbroad = 7 if occup_orig3==314

	replace occupbroad = 7 if occup_orig3==320
	replace occupbroad = 7 if occup_orig3==321
	replace occupbroad = 7 if occup_orig3==322
	replace occupbroad = 7 if occup_orig3==323

	replace occupbroad = 7 if occup_orig3==399

	replace occupbroad = 9 if occup_orig3==411

	replace occupbroad = 9 if occup_orig3==420
	replace occupbroad = 9 if occup_orig3==421
	replace occupbroad = 9 if occup_orig3==422
	replace occupbroad = 9 if occup_orig3==423

	replace occupbroad = 9 if occup_orig3==431

	replace occupbroad = 9 if occup_orig3==499

	replace occupbroad = 8 if occup_orig3==510
	replace occupbroad = 8 if occup_orig3==511

	replace occupbroad = 8 if occup_orig3==520
	replace occupbroad = 8 if occup_orig3==521
	replace occupbroad = 8 if occup_orig3==522
	replace occupbroad = 8 if occup_orig3==523
	replace occupbroad = 11 if occup_orig3==524
	replace occupbroad = 8 if occup_orig3==525

	replace occupbroad = 8 if occup_orig3==530
	replace occupbroad = 8 if occup_orig3==531

	replace occupbroad = 8 if occup_orig3==599

	replace occupbroad = 11 if occup_orig3==610
	replace occupbroad = 11 if occup_orig3==611
	replace occupbroad = 11 if occup_orig3==612
	replace occupbroad = 11 if occup_orig3==613

	replace occupbroad = 11 if occup_orig3==620
	replace occupbroad = 11 if occup_orig3==621
	replace occupbroad = 11 if occup_orig3==622
	replace occupbroad = 11 if occup_orig3==623

	replace occupbroad = 10 if occup_orig3==631

	replace occupbroad = 11 if occup_orig3==699

	replace occupbroad = 10 if occup_orig3==710
	replace occupbroad = 10 if occup_orig3==711
	replace occupbroad = 10 if occup_orig3==712
	replace occupbroad = 10 if occup_orig3==713

	replace occupbroad = 10 if occup_orig3==720
	replace occupbroad = 10 if occup_orig3==721
	replace occupbroad = 10 if occup_orig3==722

	replace occupbroad = 10 if occup_orig3==730
	replace occupbroad = 10 if occup_orig3==731
	replace occupbroad = 10 if occup_orig3==732
	replace occupbroad = 10 if occup_orig3==733
	replace occupbroad = 10 if occup_orig3==734
	replace occupbroad = 10 if occup_orig3==735

	replace occupbroad = 10 if occup_orig3==740
	replace occupbroad = 10 if occup_orig3==741

	replace occupbroad = 10 if occup_orig3==750
	replace occupbroad = 10 if occup_orig3==751

	replace occupbroad = 10 if occup_orig3==760
	replace occupbroad = 10 if occup_orig3==761

	replace occupbroad = 10 if occup_orig3==799

	replace occupbroad = 10 if occup_orig3==810
	replace occupbroad = 10 if occup_orig3==811
	replace occupbroad = 10 if occup_orig3==812
	replace occupbroad = 10 if occup_orig3==813
	replace occupbroad = 10 if occup_orig3==814
	replace occupbroad = 10 if occup_orig3==815
	replace occupbroad = 10 if occup_orig3==816
	replace occupbroad = 10 if occup_orig3==817
	replace occupbroad = 10 if occup_orig3==818
	replace occupbroad = 10 if occup_orig3==819

	replace occupbroad = 10 if occup_orig3==820
	replace occupbroad = 10 if occup_orig3==821

	replace occupbroad = 13 if occup_orig3==830
	replace occupbroad = 13 if occup_orig3==831
	replace occupbroad = 13 if occup_orig3==832
	replace occupbroad = 13 if occup_orig3==833
	replace occupbroad = 13 if occup_orig3==834
	replace occupbroad = 13 if occup_orig3==835

	replace occupbroad = 10 if occup_orig3==899

	replace occupbroad = 11 if occup_orig3==911
	replace occupbroad = 11 if occup_orig3==912

	replace occupbroad = 10 if occup_orig3==921
	replace occupbroad = 10 if occup_orig3==922
	replace occupbroad = 10 if occup_orig3==923

	replace occupbroad = 13 if occup_orig3==931
	replace occupbroad = 13 if occup_orig3==932
	replace occupbroad = 13 if occup_orig3==933

	replace occupbroad = 8 if occup_orig3==941

	replace occupbroad = 9 if occup_orig3==951
	replace occupbroad = 9 if occup_orig3==952

	replace occupbroad = 8 if occup_orig3==960
	replace occupbroad = 8 if occup_orig3==961
	replace occupbroad = 8 if occup_orig3==962
	replace occupbroad = 8 if occup_orig3==963
	replace occupbroad = 8 if occup_orig3==964
	replace occupbroad = 8 if occup_orig3==965
	replace occupbroad = 8 if occup_orig3==966

	replace occupbroad = 8 if occup_orig3==971
	replace occupbroad = 8 if occup_orig3==972
	replace occupbroad = 8 if occup_orig3==973

	replace occupbroad = 12 if occup_orig3==988
	
	replace occupbroad = 2 if occup_orig2>=11 & occup_orig2<=19 & occupbroad==.
	replace occupbroad = 6 if occup_orig2==21 & occupbroad==.
	replace occupbroad = 5 if occup_orig2==23 & occupbroad==.
	replace occupbroad = 8 if occup_orig2>=51 & occup_orig2<=53 & occupbroad==.
	replace occupbroad = 9 if occup_orig2==41 & occupbroad==.
	replace occupbroad =12 if occup_orig2>=54 & occup_orig2<=55 & occupbroad==.	
	replace occupbroad =11 if occup_orig2>=61 & occup_orig2<=62 & occupbroad==.
	replace occupbroad =10 if occup_orig2>=71 & occup_orig2<=72 & occupbroad==.
	replace occupbroad =13 if occup_orig2==83 & occupbroad==.
	replace occupbroad =12 if occup_orig2>=98 & occup_orig2<=99 & occupbroad==.
	
	clonevar occupjobs = occupbroad
	
	recode occupbroad  (1 2 = 1) (3 = 2) (4 5 8 12 = 5) (6 7 9 = 3) (10 11 13 = 4)
	
	#delimit ;
	label define lbloccupbroad
		   0 "Not Emp"
           1 "Managerial"
           2 "Engineering"
		   3 "Support S"
		   4 "Production"
		   5 "Other", replace;
	#delimit cr
	label values occupbroad lbloccupbroad	
	drop occup_orig2 occup_orig3
	
	* Replace long labels for occup
	#delimit ;
	label define lbloccup
		   0 "Not Emp"
           1 "Man"	
           2 "Prof"
           3 "Tech"
           4 "Clerks"
           5 "S and msw"
			6 "Sk agri"
			7 "Craft w"
			8 "Machine op"
           9 "Elem occup"
          10 "Armed f"
          99 "Others"
         100 "NA", replace;
	#delimit cr
	label values occup lbloccup

	compress
	
	order year-int_month quarter panel pid_p
	
	save "$path/PANEL/DATA/MEX_2005_2023_ENOE_V01_M_V06_A_GLD_FULLSAMPLE.dta", replace	
	frame reset
	
}

********************************************************************************
* Part 2. Panel of Workers Quarterly
********************************************************************************
if "`part2'"=="yes" {

	* Create a balance database
	use pid_p n_ent q_panel tipo if q_panel==1 using "$path/PANEL/DATA/MEX_2005_2023_ENOE_V01_M_V06_A_GLD_FULLSAMPLE.dta", clear
		tab tipo, m
		drop tipo
		* duplicates report 
		reshape wide q_panel, i(pid_p) j(n_ent)
		reshape long q_panel, i(pid_p) j(n_ent)
		
		* We need to identify individuals that missed the first interview
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
		
	use "$path/PANEL/DATA/MEX_2005_2023_ENOE_V01_M_V06_A_GLD_FULLSAMPLE.dta", clear

	count /*24,246,404*/
	
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
		
	** Identify temporary or permanent attrition 
	gen att_dummy = (dateq==.)

	/* NOTE: We could, for some observations, try to correct for temporary 
	attrition using the tenure variable. Let's chat about whether we want to 
	do that. */
 
	* There is no attrition between first and second interview - by definition in q_panel
	* probit att_dummy l1.i.age_catego#l1.i.male#l1.i.married#l1.i.literacy if l.att_dummy==0 & (n_ent>=1 & n_ent<=2)
	
	gen ratio = 1
	gen attweight = .	
	replace attweight = weight if n_ent==1|n_ent==2
	
	forval i = 3/5 {
		probit att_dummy l1.i.age_catego#l1.i.male#l1.i.married#l1.i.literacy if l.att_dummy==0 & n_ent==`i'
			predict p_ur if n_ent==`i'
		
		sum att_dummy if l.att_dummy==0 & (n_ent==`i')
			scalar p_r = r(mean)
		
		replace ratio = p_ur/p_r if n_ent==`i'
			drop p_ur
			scalar drop p_r

		replace attweight = weight * ratio if n_ent==`i'
	}	
	
	* Saving rotating panel data with the 5 interviews/quarters
	save "$path/PANEL/DATA/MEX_2005_2023_PANEL_QUARTER_EXPORTS.dta", replace
	* 12,219,965
	frame reset
}

********************************************************************************
* Part 2.1 Exports and Workers by City to XLSX
********************************************************************************
if "`part21'"=="yes" {
	
	use "$path/PANEL/DATA/MEX_2005_2020_ENOE_V01_M_V03_A_GLD_FULLSAMPLE.dta", clear
	* 24,253,724 obs	
		*drop if year<2011
		
		sort year quarter state city
		by   year quarter state city: keep if _n==1
		
		collapse (sum) exports_city, by(dateq year quarter mesoregion city)
		tempfile exports_city
		save `exports_city'
			
	use "$path/PANEL/DATA/MEX_2005_2020_ENOE_V01_M_V03_A_GLD_FULLSAMPLE.dta", clear	
	
		*drop if year<2011
		gen worker = 1
		replace informal = . if informal==3
		collapse (sum) worker (mean) educy informal if age>=15 & age<=64 & lstatus==1 [fw=weight], by(dateq year quarter mesoregion city)
	
	merge 1:1 year quarter mesoregion city using `exports_city'
	
		keep if _merge==3
		drop _merge
		
	* Variables
	replace informal = informal*100
	
	gen double exports_city_worker = (exports_city/worker) * 10^6
	gen lninformal = ln(informal)
	gen lnexports_city  = ln(exports_city)
	gen lnexports_city_worker = ln(exports_city_worker)
	
	*gen double exports_city_D_worker = (exports_city_D/worker) * 10^6
	*gen lnexports_city_D_worker = ln(exports_city_D_worker)
		
	order date year quarter city 
		
	label var dateq "Date"
	label var year "Year"
	label var quarter "Quarter"
	label var city "City"
	label var worker "Employees (15-64 years old)"
	label var educy "Years of schooling"
	label var informal "Informality, % of employeed" 
	label var exports_city "Exports by city, USD millions"
	label var exports_city_worker "Exports per employee, US$"
	label var mesoregion 	"Region"
	label var lninformal 		"Informality, % of employeed (log scale)"
	label var lnexports_city	"Exports by city, USD millions (log scale)"
	label var lnexports_city_worker	"Exports per employee, US$ (log scale)"
		
	* Export to xlsx
	* export excel using "$path/PANEL/DATA/Tableau/Exports_by_city.xlsx", firstrow(variables) sheet("exports_by_city") replace
	
	rename educy  educy_city
	rename worker workers_city
	rename informal informal_city
	
	gen double   exports_city_worker100 = exports_city_worker/(10^2)
	gen double lnexports_city_worker100 = ln(exports_city_worker100)
	gen double lnexports_city_worker1002 = lnexports_city_worker100^2
	
	save "$path/PANEL/DATA/Statistics by City.dta", replace
	
}

********************************************************************************
* Part 3. Probabilities
********************************************************************************
if "`part3'"=="yes" {
	
	local myif "if n_ent>=2 & att_dummy==0"
	
	use "$path/PANEL/DATA/MEX_2005_2020_PANEL_QUARTER_EXPORTS.dta", clear
	* 12,219,965 obs
		merge m:1 dateq year quarter mesoregion city using "$path/PANEL/DATA/Statistics by City.dta"
		* _merge = 1 includes dataq from 2005 to 2010
		* there are 706,793 obs that complement the "square panel", but that have no data -> marked with att_dummy==1
	
	keep pid_p n_ent `mygvarlist' informal lnexports_city_worker educy_city urban male married age_catego educy firmsizev2 ind attweight dateq quarter att_dummy mesoregion
	
	* Code regressions
	* Informalidad
	* Industria Agregada
	* Ocupacion Agregada
	#delimit ;	
	label define lbloccupjobs 
	0	"Not Emp"
	1	"Leg"
	2	"Man"
	3	"Eng"
	4	"Heal"
	5	"Teach"
	6	"OProf"
	7	"Cler"
	8	"Pers"
	9	"Sales"
	10	"Craft"
	11	"Agri"
	12	"Other"
	13	"Drivers"
	;
	#delimit cr
	label values occupjobs lbloccupjobs
	
	
	local regressors_informal   "lnexports_city_worker educy_city i.urban male married i.age_catego educy i.firmsizev2 ib1.ind ib5.mesoregion"
	local regressors_ind 	    "lnexports_city_worker educy_city i.urban male married i.age_catego educy i.firmsizev2         ib5.mesoregion"
	local regressors_occup 	    "lnexports_city_worker educy_city i.urban male married i.age_catego educy i.firmsizev2         ib5.mesoregion"
	
	local regressors_indbroad   "lnexports_city_worker educy_city i.urban male married i.age_catego educy i.firmsizev2         ib5.mesoregion"
	local regressors_occupbroad "lnexports_city_worker educy_city i.urban male married i.age_catego educy i.firmsizev2         ib5.mesoregion"
	local regressors_occupjobs  "lnexports_city_worker educy_city i.urban male married i.age_catego educy i.firmsizev2         ib5.mesoregion"
	
	sort pid_p n_ent

	foreach var of local mygvarlist {
		levelsof `var', local(mygvar)
		foreach l of local mygvar {
		foreach m of local mygvar {
			* generate byte `var'_`l'_`m' = (`var' == `l' & f1.`var' == `m') if att_dummy==0
			 generate byte `var'_`l'_`m' = (`var' == `l' & l1.`var' == `m') if att_dummy==0
		}
		}
	}
	
	foreach var of local mygvarlist {

		putexcel set "$temp/conditional_pred_transitions_attweights_`var'.xlsx", sheet("Probabilities") modify
		putexcel B1 = ("b") C1 = ("se") D1 = ("t") E1 = ("pvalue") F1 = ("ll") G1 = ("ul") H1 = ("df") I1 = ("crit") 
		local r = 2
	
		levelsof `var', local(mygvar)
		foreach l of local mygvar {
		foreach m of local mygvar {
			
			* Recovering names for `var'
				local lblvar : value label `var'
				local l_name : label `lblvar' `l'
				local m_name : label `lblvar' `m'
			
			putexcel set "$temp/conditional_pred_transitions_attweights_`var'.xlsx", sheet("`l_name' `m_name'", replace) modify
			reghdfe `var'_`l'_`m' `regressors_`var'' `myif'  [aw = attweight], absorb(i.dateq i.quarter) vce(robust)
			
			mat B = r(table)'
			putexcel A1 = matrix(B), names
			
			putexcel set "$temp/conditional_pred_transitions_attweights_`var'.xlsx", sheet("Probabilities") modify
			
			margins, atmeans 
			mat T = r(table)'
			
			putexcel A`r' = ("`var'_`l'_`m'")
			putexcel B`r' = matrix(T)
			local r = `r'+1 			
		}
		}

	}
}	

********************************************************************************
* Part 3.1 Assembling probabilities
********************************************************************************	
if "`part31'"=="yes" {

	foreach var of local mygvarlist {

		* Set Excel
		putexcel set "$temp/conditional_pred_transitions_attweights_`var'.xlsx", modify sheet("Summary Trade")
		local allwords "A B C D E F G H I J K L M N O P Q R S T U V W X Y Z"
		
		* Recover values
			use `var' using "$path/PANEL/DATA/MEX_2005_2020_PANEL_QUARTER_EXPORTS.dta", clear

			* generate occupation broad
			bys `var': keep if _n==1
					
			* Read all value labels
			bys `var': keep if _n==1
			drop if `var'==.
			levelsof `var', local(all`var')
		
			* Write titles, in rows
				local ln = 3
				local mn = 2
				foreach l of local all`var' {
				local mt : word `mn' of `allwords'
				
				* Recovering names for `var'
					local lblvar : value label `var'
					local l_name : label `lblvar' `l'
					noi di "`lbvar' `l_name'"
							
					* Excel Put
					putexcel `mt'`ln' = "`l_name'"
					local ln = `ln'+1
					
				}		
			
			* Write titles, in rows
				local ln = 2
				local mn = 3
				foreach m of local all`var' {
				local mt : word `mn' of `allwords'
				
				* Recovering names for `var'
					local lblvar : value label `var'
					local m_name : label `lblvar' `m'
					noi di "`lbvar' `m_name'"
							
					* Excel Put
					putexcel `mt'`ln' = "`m_name'"
					local mn = `mn'+1
					
				}		
			
			
			* Write results
			local ln = 3
			foreach l of local all`var' {
			
				local mn = 3
				foreach m of local all`var' {
				local mt : word `mn' of `allwords'
				noi di "Cell: Column `mt' Row `ln'"
				
					* Recovering names for `var'
						local lblvar : value label `var'
						local l_name : label `lblvar' `l'
						local m_name : label `lblvar' `m'

						noi di "`lbvar' `l_name' `m_name'"
						
					* Excel Put
						putexcel `mt'`ln' = formula("=IF('`l_name' `m_name''!E2<0.01,'`l_name' `m_name''!B2*100,0)")
					
					local mn = `mn'+1
				}
			
			local ln = `ln'+1
			}
		

		* Set Excel - Probabilities
		putexcel set "$temp/conditional_pred_transitions_attweights_`var'.xlsx", modify sheet("Summary Probs")
		
			* Write titles, in rows
				local ln = 3
				local mn = 2
				foreach l of local all`var' {
				local mt : word `mn' of `allwords'
				
				* Recovering names for `var'
					local lblvar : value label `var'
					local l_name : label `lblvar' `l'
					noi di "`lbvar' `l_name'"
							
					* Excel Put
					putexcel `mt'`ln' = "`l_name'"
					local ln = `ln'+1
					
				}		
			
			* Write titles, in rows
				local ln = 2
				local mn = 3
				foreach m of local all`var' {
				local mt : word `mn' of `allwords'
				
				* Recovering names for `var'
					local lblvar : value label `var'
					local m_name : label `lblvar' `m'
					noi di "`lbvar' `m_name'"
							
					* Excel Put
					putexcel `mt'`ln' = "`m_name'"
					local mn = `mn'+1
					
				}		
			
			
			* Write results
			local ln = 3
			local pn = 2
			foreach l of local all`var' {
			
				local mn = 3
				foreach m of local all`var' {
				local mt : word `mn' of `allwords'
				noi di "Cell: Column `mt' Row `ln'"
				
					* Recovering names for `var'
						local lblvar : value label `var'
						local l_name : label `lblvar' `l'
						local m_name : label `lblvar' `m'

						noi di "`lbvar' `l_name' `m_name'"
						
					* Excel Put
						putexcel `mt'`ln' = formula("='Probabilities'!B`pn'*100")
					
					local mn = `mn'+1
					local pn = `pn'+1
				}
			
			local ln = `ln'+1
			
			}
		
	}	
	
}

********************************************************************************
* Part 3.2 Testing regression specifications
********************************************************************************	
if "`part32'"=="yes" {
	use "$path/PANEL/DATA/MEX_2005_2020_PANEL_QUARTER_EXPORTS.dta", replace
	* 12,219,965 obs
		merge m:1 dateq year quarter mesoregion city using "$path/PANEL/DATA/Statistics by City.dta"
		* _merge = 1 includes dataq from 2005 to 2010
		* there are 706,793 obs that complement the "square panel", but that have no data -> marked with att_dummy==1
		
		egen double exgob_city = rsum(exgob_cityID1 - exgob_cityID21)
		gen double exgob_city_worker = exgob_city/workers_city
		gen lnexgob_city_worker = ln(exgob_city_worker)
		
	* exports_city_worker, hundreds of US$
		* replace      exports_city_worker = 0 if exports_city_worker==. & att_dummy==0
		* gen double   exports_city_worker100 = exports_city_worker/(10^2)
		* gen double lnexports_city_worker100 = ln(exports_city_worker100)
		* gen double lnexports_city_worker1002 = lnexports_city_worker100^2
	
		* replace ind = 0 if (lstatus==2|lstatus==3) & ind==. & att_dummy==0

	local mygvarlist "informal"
	sort pid_p n_ent
	foreach var of local mygvarlist {
		levelsof `var', local(mygvar)
		foreach l of local mygvar {
		foreach m of local mygvar {
			*generate byte old`var'_`l'_`m' = (`var' == `l' & f1.`var' == `m') if att_dummy==0
			generate byte    `var'_`l'_`m' = (`var' == `l' & l1.`var' == `m') if att_dummy==0
		}
		}
	}		
		
		local myif "if n_ent<=4 & att_dummy==0"
		*reghdfe oldinformal_3_3 lnexports_city_worker100                        educy_city i.age_catego educy literacy male i.firmsizev2 i.urban married 		`myif'			[aw = attweight], absorb(i.dateq i.quarter i.mesoregion)
		
		* Regression 1: with literacy and marriage and i.mesoregion
		* 6,171,602
		*reghdfe informal_1_0 lnexgob_city_worker                        educy_city i.age_catego educy literacy male i.firmsizev2 i.urban married 		`myif'			[aw = attweight], absorb(i.dateq i.quarter i.mesoregion)		
		reghdfe informal_1_0 lnexports_city_worker100                        educy_city i.age_catego educy literacy male i.firmsizev2 i.urban married 		`myif'			[aw = attweight], absorb(i.dateq i.quarter i.mesoregion)

		* Regression 2: with literacy, marriage, i.mesoregion + lnexports_city_worker1002
		* 6,171,602
		reghdfe informal_1_0 lnexports_city_worker100 lnexports_city_worker1002 educy_city i.age_catego educy literacy male i.firmsizev2 i.urban married 					[aw = attweight], absorb(i.dateq i.quarter i.mesoregion)	
		
		
		* Regression 3: including sector of employment with literacy, marriage, i.mesoregion + lnexports_city_worker1002
		* obs 201,482
		reghdfe informal_1_0 lnexports_city_worker100 lnexports_city_worker1002 educy_city i.age_catego educy literacy male i.firmsizev2 i.urban married ib1.ind 	[aw = attweight], absorb(i.dateq i.quarter i.mesoregion)	

		* Regression 4 - including sector of employment 
		*  6,171,602
		reghdfe informal_1_0 lnexports_city_worker100 lnexports_city_worker1002 educy_city i.age_catego educy literacy male i.firmsizev2 i.urban married ib1.ind [aw = attweight], absorb(i.dateq i.quarter i.mesoregion)	
		
		
		* Regression 5 - including sector of employment + robust standard errors
		* 6,171,602
		reghdfe informal_1_0 lnexports_city_worker100 lnexports_city_worker1002 educy_city i.age_catego educy literacy male i.firmsizev2 i.urban married ib1.ind [aw = attweight], absorb(i.dateq i.quarter i.mesoregion)	vce(robust)	
	
	
		* Regression 6 - including sector of employment + robust standard errors + i.city
		* 6,171,602 -> including the i.city dummy makes exports_worker not significant
		reghdfe informal_1_0 lnexports_city_worker100 lnexports_city_worker1002 educy_city i.age_catego educy literacy male i.firmsizev2 i.urban married ib1.ind [aw = attweight], absorb(i.dateq i.quarter i.mesoregion i.city)	vce(robust)	
	
		* Regression 7 - including sector of employment + robust standard errors + i.city
		* 6,171,602 -> 	including the i.city dummy makes just lnexports_worker  not significant
		*				This may be expected since these are variables that explain each city dynamic
		reghdfe informal_1_0 lnexports_city_worker100                        educy_city i.age_catego educy literacy male i.firmsizev2 i.urban married ib1.ind [aw = attweight], absorb(i.dateq i.quarter i.mesoregion i.city)	vce(robust)	
	
		* Regression 8 - including sector of employment + robust standard errors + i.city
		* 6,171,602 -> 	including the i.c_mnpio dummy makes just lnexports_worker  not significant
		*				This may be expected since these are variables that explain each city dynamic
		reghdfe informal_1_0 lnexports_city_worker100                        educy_city i.age_catego educy literacy male i.firmsizev2 i.urban married ib1.ind [aw = attweight], absorb(i.dateq i.quarter i.mesoregion i.c_mnpio)	vce(robust)	
	
		* Regression 8 - including sector of employment + robust standard errors + i.city
		* 6,171,602 -> 	including the i.pid_p leaves no room for drawing standard errors
		*				This may be expected since these are variables that explain each city dynamic
		reghdfe informal_1_0 lnexports_city_worker100                        educy_city i.age_catego educy literacy male i.firmsizev2 i.urban married ib1.ind [aw = attweight], absorb(i.dateq i.quarter i.mesoregion i.pid_p)	vce(robust)	
	
	
		* For Mesoregion = 1 - lnexports_city_worker100 not significant when i.city included
		* 687,254
		reghdfe informal_1_0 lnexports_city_worker100                        educy_city i.age_catego educy literacy male i.firmsizev2 i.urban married ib1.ind [aw = attweight] if (mesoregion==1), absorb(i.dateq i.quarter  i.city)	vce(robust)	
	
		* For Mesoregion = 2 - lnexports_city_worker100 not significant when i.city included
		* 972,654
		reghdfe informal_1_0 lnexports_city_worker100                        educy_city i.age_catego educy literacy male i.firmsizev2 i.urban married ib1.ind [aw = attweight] if (mesoregion==2), absorb(i.dateq i.quarter  i.city)	vce(robust)	
	
		* For Mesoregion = 3 - lnexports_city_worker100 not significant when i.city included
		* 1,410,373
		reghdfe informal_1_0 lnexports_city_worker100                        educy_city i.age_catego educy literacy male i.firmsizev2 i.urban married ib1.ind [aw = attweight] if (mesoregion==3), absorb(i.dateq i.quarter  i.city)	vce(robust)	
	
		* For Mesoregion = 4 - lnexports_city_worker100 not significant when i.city included
		* 1,614,008
		reghdfe informal_1_0 lnexports_city_worker100                        educy_city i.age_catego educy literacy male i.firmsizev2 i.urban married ib1.ind [aw = attweight] if (mesoregion==4), absorb(i.dateq i.quarter  i.city)	vce(robust)	

		* For Mesoregion = 5 - lnexports_city_worker100 not significant when i.city included
		* 1,487,313
		reghdfe informal_1_0 lnexports_city_worker100                        educy_city i.age_catego educy literacy male i.firmsizev2 i.urban married ib1.ind [aw = attweight] if (mesoregion==5), absorb(i.dateq i.quarter  i.city)	vce(robust)	

		

		
		* For Mesoregion = 1 significantly different than zero .0023907
		* 687,254
		reghdfe informal_1_0 lnexports_city_worker100                        educy_city i.age_catego educy literacy male i.firmsizev2 i.urban married ib1.ind [aw = attweight] if (mesoregion==1), absorb(i.dateq i.quarter)	vce(robust)	
		
		reghdfe informal_1_0 lnexports_city_worker100                        educy_city i.age_catego educy          male i.firmsizev2 i.urban married ib1.ind [aw = attweight] if (mesoregion==1), absorb(i.dateq i.quarter)	vce(robust)		
		
		* For Mesoregion = 2 significantly different than zero .0025306
		* 972,654
		reghdfe informal_1_0 lnexports_city_worker100                        educy_city i.age_catego educy literacy male i.firmsizev2 i.urban married ib1.ind [aw = attweight] if (mesoregion==2), absorb(i.dateq i.quarter)	vce(robust)	

		reghdfe informal_1_0 lnexports_city_worker100                        educy_city i.age_catego educy          male i.firmsizev2 i.urban         ib1.ind [aw = attweight] if (mesoregion==2), absorb(i.dateq i.quarter)	vce(robust)			
		
		* For Mesoregion = 3 weakly significant .0003804
		* 1,410,373
		reghdfe informal_1_0 lnexports_city_worker100                        educy_city i.age_catego educy literacy male i.firmsizev2 i.urban married ib1.ind [aw = attweight] if (mesoregion==3), absorb(i.dateq i.quarter)	vce(robust)	

		reghdfe informal_1_0 lnexports_city_worker100                        educy_city i.age_catego educy          male i.firmsizev2 i.urban         ib1.ind [aw = attweight] if (mesoregion==3), absorb(i.dateq i.quarter)	vce(robust)			
		
		* For Mesoregion = 4 weakly significant .0003954
		* 1,614,008
		reghdfe informal_1_0 lnexports_city_worker100                        educy_city i.age_catego educy literacy male i.firmsizev2 i.urban married ib1.ind [aw = attweight] if (mesoregion==4), absorb(i.dateq i.quarter)	vce(robust)	

		reghdfe informal_1_0 lnexports_city_worker100                        educy_city i.age_catego educy          male i.firmsizev2 i.urban         ib1.ind [aw = attweight] if (mesoregion==4), absorb(i.dateq i.quarter)	vce(robust)			
		
		* For Mesoregion = 5 not statistically different than zero
		* 1,487,313
		reghdfe informal_1_0 lnexports_city_worker100                        educy_city i.age_catego educy literacy male i.firmsizev2 i.urban married ib1.ind [aw = attweight] if (mesoregion==5), absorb(i.dateq i.quarter)	vce(robust)	
		
		reghdfe informal_1_0 lnexports_city_worker100                        educy_city i.age_catego educy          male i.firmsizev2 i.urban married ib1.ind [aw = attweight] if (mesoregion==5), absorb(i.dateq i.quarter)	vce(robust)	
		*/
}
