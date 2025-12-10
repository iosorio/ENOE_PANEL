*v1.0 iosoriorodarte@worldbank.org
* Reproducibility Package
/*******************************************************************************
* Read me
*******************************************************************************/

********************************************************************************
* Set path
********************************************************************************
* Path: For setting up the path, use the universal forward slash "/",
*       instead of Windows-specific "\". See example below
 
* User 1: Israel Osorio Rodarte
	if c(username)=="israel"|c(username)=="Israel" {
		global path "/Users/`c(username)'/OneDrive/IOR/Projects/Y2025/FY25_MEX_MinimumWage/Mexico_MinWage/ENOE"
	}

* User 2: Israel Osorio Rodarte (WB308767)
	if c(username)=="WB308767" & c(hostname)=="WBGXDP0663" {
		global path "C:/Users/`c(username)'/OneDrive/IOR/Projects/Y2025/FY25_MEX_MinimumWage/Mexico_MinWage/ENOE"
	}	

cd "$path"
cap log close master
cap mkdir "$path/Logs"
log using "Do-Files/Logs/Master.log", replace name(master)
clear
********************************************************************************
* STEPS
********************************************************************************

* Step 1. ENOE Harmonization
	do "Do-files/01_ENOE_Harmonization.do"

* Step 2. Append surveys
	do "Do-files/02_Append_ENOE_Surveys.do"

* Step 3. Construct panel of workers
	do "Do-files/03_Construct_panel_of_workers.do"
	
* Step 4. Figure 08 (left)
	do "Do-files/04_Figure_08.do"
	
* Step 5. Annex Table 6
	do "Do-files/05_Annex_Table_6.do"

* Step 6. Annex Table 8
	do "Do-files/06_Annex_Table_8.do"
		
********************************************************************************
* End of 00 Master.do
********************************************************************************
cap log close master
