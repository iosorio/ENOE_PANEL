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
		global path "/Users/`c(username)'/Library/CloudStorage/OneDrive-Personal/IOR/Projects/Y2025/FY25_MEX_MinimumWage/ENOE_PANEL"
	}

cd "$path"
global thedo "$path/Do-files"
do "$path/Do-files/00_ENOE_Versioning.do"
cap log close master
cap mkdir "$path/Logs"
log using "Do-Files/Logs/Master.log", replace name(master)
clear
etime, start
********************************************************************************
* STEPS
********************************************************************************

* Step 1. ENOE Harmonization
	do "Do-files/01_ENOE_Harmonization.do"

* Step 2. Append surveys
	do "Do-files/02_Append_ENOE_Surveys.do"

* Step 3. Construct panel of workers
	do "Do-files/03_Construct_panel_of_workers.do"
			
********************************************************************************
* End of 00 Master.do
********************************************************************************
cap log close master
