*v1.0 iosoriorodarte@worldbank.org
* Reproducibility Package
cap log close step05
log using "Do-files/Logs/05_Annex_Table_6.log", replace name(step05)
clear
/*******************************************************************************
* Annex Table 6
*******************************************************************************/
	
	forval set = 1/8 {
	foreach time in 2014 2023 {

		if `set'==1 local oc = 4
		if `set'==2 local oc = 8
		if `set'==3 local oc = 12
		if `set'==4 local oc = 18
		if `set'==5 local oc = 25
		if `set'==6 local oc = 31
		if `set'==7 local oc = 50
		if `set'==8 local oc = 53
		if `set'==9 local oc = 66
		
		*if `time'==2009 local op = "D"
		if `time'==2014 local op = "D"
		*if `time'==2018 local op = "X"
		if `time'==2023 local op = "J"
	
		local outputsheet	"Annex table 6"
		local outputcell 	"`op'`oc'"
	
	*set1: urban
	if `set'==1 {
		local myvar			"urban"
		local panelkeepvars "`myvar' age year quarter n_ent"
		local ifpanelconds 	"if age>=15 & age<=64 & year==`time' & quarter==1 & n_ent==5"
		local crosskeepvars "`myvar' age year quarter"
		local ifcrossconds "if age>=15 & age<=64 & year==`time' & quarter==1"
	}
	
	*set2: male
	if `set'==2 {
		local myvar			"male"
		local panelkeepvars "`myvar' age year quarter n_ent relationharm"
		local ifpanelconds 	"if age>=15 & age<=64 & year==`time' & quarter==1 & n_ent==5 & relationharm==1"	
		local crosskeepvars "`myvar' age year quarter relationharm"
		local ifcrossconds "if age>=15 & age<=64 & year==`time' & quarter==1 & relationharm==1"
	}
	
	*set3: agehead
	if `set'==3 {
		local myvar			"agehead"
		local panelkeepvars "age year quarter n_ent relationharm"
		local ifpanelconds 	"if age>=15 & age<=64 & year==`time' & quarter==1 & n_ent==5 & relationharm==1"
		local crosskeepvars "age year quarter relationharm"
		local ifcrossconds "if age>=15 & age<=64 & year==`time' & quarter==1 & relationharm==1"
	}
	
	*set4: schooling
	if `set'==4 {
		local myvar			"schooling"
		local panelkeepvars "age year quarter n_ent relationharm educy educat7"
		local ifpanelconds 	"if age>=15 & age<=64 & year==`time' & quarter==1 & n_ent==5 & relationharm==1"
		local crosskeepvars "age year quarter relationharm educy educat7"
		local ifcrossconds "if age>=15 & age<=64 & year==`time' & quarter==1 & relationharm==1"
	}	
	
	*set5: employment
	if `set'==5 {
		local myvar			"employment"
		local panelkeepvars "age year quarter n_ent relationharm educy educat7 lstatus informal"
		local ifpanelconds 	"if age>=15 & age<=64 & year==`time' & quarter==1 & n_ent==5 & relationharm==1"
		local crosskeepvars "age year quarter relationharm educy educat7 lstatus informal"
		local ifcrossconds "if age>=15 & age<=64 & year==`time' & quarter==1 & relationharm==1"
	}	
	
	*set6: myind2
	if `set'==6 {
		local myvar			"myind2"
		local panelkeepvars "age year quarter n_ent relationharm educy educat7 lstatus informal industry_orig"
		local ifpanelconds 	"if age>=15 & age<=64 & year==`time' & quarter==1 & n_ent==5 & relationharm==1"
		local crosskeepvars "age year quarter relationharm educy educat7 lstatus informal industry_orig"
		local ifcrossconds "if age>=15 & age<=64 & year==`time' & quarter==1 & relationharm==1"
	}
	
	*set7: incomepc
	if `set'==7 {
		local myvar			"incomepc"
		local panelkeepvars "age year quarter n_ent hhid hsize relationharm laborincome mv ingreso tamh"
		local ifpanelconds 	"if age>=15 & age<=64 & year==`time' & quarter==1 & n_ent==5"
		local crosskeepvars "age year quarter hhid hsize relationharm laborincome mv ingreso tamh"
		local ifcrossconds "if age>=15 & age<=64 & year==`time' & quarter==1"
	}
	
	*set8: famsize
	if `set'==8 {
		local myvar			"famsize"
		local panelkeepvars "age year quarter n_ent hhid hsize relationharm laborincome"
		local ifpanelconds 	"if age>=15 & age<=64 & year==`time' & quarter==1 & n_ent==5 & relationharm==1"
		local crosskeepvars "age year quarter hhid hsize relationharm laborincome"
		local ifcrossconds "if age>=15 & age<=64 & year==`time' & quarter==1 & relationharm==1"
	}	
		
	*set9: famtype
	if `set'==9 {
		local myvar			"famtype"
		local panelkeepvars "age year quarter n_ent hhid hsize relationharm"
		local ifpanelconds 	"if  year==`time' & quarter==1 & n_ent==5"
		local crosskeepvars "age year quarter       hhid hsize relationharm"
		local ifcrossconds  "if  year==`time' & quarter==1"
	}	

	
	* Panel
	if `set'!=9 use `panelkeepvars' `ifpanelconds' using "$path/PANEL/DATA/MEX_2005_2023_PANEL_QUARTER.dta", clear
	if `set'==9 use `panelkeepvars' `ifpanelconds' using "$path/PANEL/DATA/MEX_2005_2023_ENOE_V01_M_V06_A_GLD_FULLSAMPLE.dta",clear
		
		if `set'==3 {
			gen agehead = .
			replace agehead = 1 if age>=15 & age<=29
			replace agehead = 2 if age>=30 & age<=44
			replace agehead = 3 if age>=45 & age<=59
			replace agehead = 4 if age>=60 & age!=.
		}
		
		if `set'==4 {
			gen schooling = .
			*replace schooling = 0 if educat7==1
			*replace schooling = 1 if educat7==2|educat7==3
			replace schooling = 1 if  educat7==1|educat7==2|educat7==3
			replace schooling = 2 if (educy>=7  & educy<=9)  & (educat7==4)
			replace schooling = 3 if (educy>=10 & educy<=12) & (educat7==4|educat7==5)
			replace schooling = 4 if (educy>=13 & educy<=17)
			replace schooling = 5 if (educy>=18 & educy!=.)
		}

		if `set'==5 {
			replace informal = 1 if informal==3 & lstatus==1
			gen employment = .
			replace employment = 1 if lstatus==3
			replace employment = 2 if lstatus==2
			replace employment = 3 if lstatus==1 & informal==1
			replace employment = 4 if lstatus==1 & informal==0
		}
		
		if `set'==6 {
			replace industry_orig = 9999 if industry_orig==. & lstatus==1
			gen industry_orig2d = int(industry_orig/100)
			#delimit ;
			recode industry_orig2d (11 = 1)
								   (21 22 = 2)
								   (23 = 3)
								   (31/33 = 4)
								   (43 46 = 5)
								   (48 49 = 6)
								   (51 = 7)
								   (52 53 = 8)
								   (54 55 = 9)
								   (61 =10)
								   (62 =11)
								   (71 =12)
								   (72 =13)
								   (93 =14)
								   (97 98 99 81 56 =15)
									, gen(myind);
			#delimit cr
			gen myind2 = .
			replace myind2 = myind+2
			replace myind2 = 1 if lstatus==3
			replace myind2 = 2 if lstatus==2
		}
		
		if `set'==7 {
			drop if hhid==""
			keep if mv==0
			gen double incomepc = ingreso/tamh
			keep if relationharm==1
		}
		
		if `set'==8 {
			drop if hhid==""
			drop if hsize==.
			gen famsize = .
			replace famsize = 1 if hsize>=0 & hsize<=4
			replace famsize = 2 if hsize>=5 & hsize!=.
		}
		
		if `set'==9 {
			drop if hhid == ""
			drop if hsize == .
			gen head 		= (relationharm==1)
			gen spouse 		= (relationharm==2)
			gen child   	= (relationharm==3)
			gen granpa  	= (relationharm==4)
			gen famother  	= (relationharm==5|relationharm==6)
			
			bys hhid: egen hashead     	= sum(head)
			bys hhid: egen hasspouse   	= sum(spouse)
			bys hhid: egen haschildren 	= sum(child)
			bys hhid: egen hasgranpa 	= sum(granpa)
			bys hhid: egen hasfamother 	= sum(famother)
			
			gen famtype = 7
				replace famtype = 1 if hsize==1 & hashead==1 // single person
				replace famtype = 2 if hsize==2 & hashead==1 & (hasspouse==1) & (haschildren==0) & (hasgranpa==0) & (hasfamother==0) // couple without children
				replace famtype = 3 if hsize>=3 & hsize<=5 & hashead==1 & (hasspouse==1) & (haschildren>=1 & haschildren<=3) & (hasgranpa==0) & (hasfamother==0) // couple with up to three children
				replace famtype = 4 if hsize>=6 & hsize!=. & hashead==1 & (hasspouse==1) & (haschildren>=4 & haschildren!=.) & (hasgranpa==0) & (hasfamother==0) // couple with four children or more
				replace famtype = 5 if hsize>=2 & hsize!=. & hashead==1 & (hasspouse==0) & (haschildren>=1 & haschildren!=.) & (hasgranpa==0) & (hasfamother==0) // single parent with children
				replace famtype = 6 if hsize>=2 & hsize!=. & hashead==1 & (haschildren>=1 & haschildren!=.) & (hasgranpa>=1 & hasgranpa!=.) & (hasfamother==0) // multi-generational family
			keep if relationharm==1
		}		
		
		if `set'!=7 tab `myvar', gen(_`myvar')
		if `set'==7 rename `myvar' _`myvar'
		local counter = 0
		foreach var of varlist _`myvar'* {
		sum `var'
			scalar p`var'_m = r(mean)
			scalar p`var'_v = r(Var)
			scalar p`var'_n = r(N)

			if "`var'"=="incomepc" scalar p`var'_m = p`var'_m/100 // This will return back to original units in line 371
			
			matrix p`var' = [p`var'_m , p`var'_v' , p`var'_n]
			
			if `counter' ==0 {
				local _mypmatrix = ""
				local _mypmatrix = "p`var'"
			}
			else             local _mypmatrix = "`_mypmatrix' \ p`var'"
			
			local counter = `counter'+1
		}
		
			matrix P_`myvar' = [`_mypmatrix']
	
	* Cross Section
	use `crosskeepvars' `ifcrossconds' using "$path/PANEL/DATA/MEX_2005_2023_ENOE_V01_M_V06_A_GLD_FULLSAMPLE.dta",clear
	
		if `set'==3 {
			gen agehead = .
			replace agehead = 1 if age>=15 & age<=29
			replace agehead = 2 if age>=30 & age<=44
			replace agehead = 3 if age>=45 & age<=59
			replace agehead = 4 if age>=60 & age!=.
		}

		if `set'==4 {
			gen schooling = .
			*replace schooling = 0 if educat7==1
			*replace schooling = 1 if educat7==2|educat7==3
			replace schooling = 1 if  educat7==1|educat7==2|educat7==3
			replace schooling = 2 if (educy>=7  & educy<=9)  & (educat7==4)
			replace schooling = 3 if (educy>=10 & educy<=12) & (educat7==4|educat7==5)
			replace schooling = 4 if (educy>=13 & educy<=17)
			replace schooling = 5 if (educy>=18 & educy!=.)
		}
		
		if `set'==5 {
			replace informal = 1 if informal==3 & lstatus==1
			gen employment = .
			replace employment = 1 if lstatus==3
			replace employment = 2 if lstatus==2
			replace employment = 3 if lstatus==1 & informal==1
			replace employment = 4 if lstatus==1 & informal==0
		}
		
		if `set'==6 {
			replace industry_orig = 9999 if industry_orig==. & lstatus==1
			gen industry_orig2d = int(industry_orig/100)
			#delimit ;
			recode industry_orig2d (11 = 1)
								   (21 22 = 2)
								   (23 = 3)
								   (31/33 = 4)
								   (43 46 = 5)
								   (48 49 = 6)
								   (51 = 7)
								   (52 53 = 8)
								   (54 55 = 9)
								   (61 =10)
								   (62 =11)
								   (71 =12)
								   (72 =13)
								   (93 =14)
								   (97 98 99 81 56 =15)
									, gen(myind);
			#delimit cr
			gen myind2 = .
			replace myind2 = myind+2
			replace myind2 = 1 if lstatus==3
			replace myind2 = 2 if lstatus==2
		}

		if `set'==7 {
			drop if hhid==""
			keep if mv==0
			gen double incomepc = ingreso/tamh
			keep if relationharm==1
		}		
		
		if `set'==8 {
			drop if hhid==""
			drop if hsize==.
			gen famsize = .
			replace famsize = 1 if hsize>=0 & hsize<=4
			replace famsize = 2 if hsize>=5 & hsize!=.
		}
		
		if `set'==9 {
			drop if hhid == ""
			drop if hsize == .
			gen head 		= (relationharm==1)
			gen spouse 		= (relationharm==2)
			gen child   	= (relationharm==3)
			gen granpa  	= (relationharm==4)
			gen famother  	= (relationharm==5|relationharm==6)
			
			bys hhid: egen hashead     	= sum(head)
			bys hhid: egen hasspouse   	= sum(spouse)
			bys hhid: egen haschildren 	= sum(child)
			bys hhid: egen hasgranpa 	= sum(granpa)
			bys hhid: egen hasfamother 	= sum(famother)
			
			gen famtype = 7
				replace famtype = 1 if hsize==1 & hashead==1 // single person
				replace famtype = 2 if hsize==2 & hashead==1 & (hasspouse==1) & (haschildren==0) & (hasgranpa==0) & (hasfamother==0) // couple without children
				replace famtype = 3 if hsize>=3 & hsize<=5 & hashead==1 & (hasspouse==1) & (haschildren>=1 & haschildren<=3) & (hasgranpa==0) & (hasfamother==0) // couple with up to three children
				replace famtype = 4 if hsize>=6 & hsize!=. & hashead==1 & (hasspouse==1) & (haschildren>=4 & haschildren!=.) & (hasgranpa==0) & (hasfamother==0) // couple with four children or more
				replace famtype = 5 if hsize>=2 & hsize!=. & hashead==1 & (hasspouse==0) & (haschildren>=1 & haschildren!=.) & (hasgranpa==0) & (hasfamother==0) // single parent with children
				replace famtype = 6 if hsize>=2 & hsize!=. & hashead==1 & (haschildren>=1 & haschildren!=.) & (hasgranpa>=1 & hasgranpa!=.) & (hasfamother==0) // multi-generational family
			keep if relationharm==1
		}
		
		if `set'!=7 tab `myvar', gen(_`myvar')
		if `set'==7 rename `myvar' _`myvar'
		local counter = 0
		foreach var of varlist _`myvar'* {
		sum `var'
			scalar c`var'_m = r(mean)
			scalar c`var'_v = r(Var)
			scalar c`var'_n = r(N)
			
			matrix c`var' = [c`var'_m , c`var'_v' , c`var'_n]
			
			if `counter' ==0 {
				local _mycmatrix = ""
				local _mycmatrix = "c`var'"
			}
			else             local _mycmatrix = "`_mycmatrix' \ c`var'"
			
			local counter = `counter'+1
		}
	
			matrix C_`myvar' = [`_mycmatrix']
	
		matrix _`myvar' = [C_`myvar' , P_`myvar']
		
		foreach m in a b c d e f g h i j k l m {
			cap matrix drop `m'
		}

		matrix a = _`myvar'[1... , 2]
		matrix b = _`myvar'[1... , 3]
		matrix c = _`myvar'[1... , 5]
		matrix d = _`myvar'[1... , 6] 

		mata: st_matrix("e", st_matrix("a") :/ st_matrix("b"))
		mata: st_matrix("f", st_matrix("c") :/ st_matrix("d"))
		mata: st_matrix("g", st_matrix("e") :+ st_matrix("f"))
		mata: st_matrix("h", (st_matrix("g") :^(1/2)):* 100)

		matrix i = _`myvar'[1... , 1]
		matrix j = _`myvar'[1... , 4]

		mata: st_matrix("k", st_matrix("i"):*100)
		mata: st_matrix("l", st_matrix("j"):*100)

		mata: st_matrix("m", st_matrix("k") :- st_matrix("l"))

		matrix _`myvar'end = [k , l , m , h]

		matrix list _`myvar'end
		
		putexcel set "Output/FINAL tables for MEX PEA.xlsx", modify sheet("`outputsheet'")
		putexcel `outputcell' = matrix(_`myvar'end)
	}
	}	

/*******************************************************************************
* End of 05_Annex_Table_6.do
*******************************************************************************/
cap log close step05	
	
