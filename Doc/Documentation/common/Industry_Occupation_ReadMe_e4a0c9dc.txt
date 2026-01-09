Industry Classification

The years 2005 to 2020 are all coded based on the Mexican SCIAN from 2007. We use the official conversion table from SCIAN 07 to ISIC 4 (file SCIAN_07_ISIC_4.xlsx, contained in this folder) to convert the data. To do so we use an algorithmic matching process. You can find that process in file "SCIAN_07_3D_ISIC_4.R" in the MEX_{Year}_ENOE_V{##}_M\Programs folder. This code uses SCIAN_07_ISIC_4.xlsx and creates the "SCIAN_07_3D_ISIC_4.dta" file (in MEX_{Year}_ENOE_V{##}_M\Data\Stata) that is used in the harmonization process.

Occupation Classification

Year 2005 to 2012 use the Mexican CMO classification. We use the official conversion table (file tablas_comparativas.xlsx, contained in this folder) to convert the data. To do so we use an algorithmic matching process. You can find that process in file "cmo_isco_via_sinco.R" in the MEX_{Year}_ENOE_V{##}_M\Programs folder. This code uses tablas_comparativas.xlsx and creates the "CMO_09_ISCO_08.dta" file (in MEX_{Year}_ENOE_V{##}_M\Data\Stata) that is used in the harmonization process.


Years 2013 to 2020 use the Mexican SINCO classification. We use the official conversion table (file tablas_comparativas.xlsx, contained in this folder) to convert the data. To do so we use an algorithmic matching process. You can find that process in file "sinco_to_isco_correspondance.R" in the MEX_{Year}_ENOE_V{##}_M\Programs folder. This code uses tablas_comparativas.xlsx and creates the "SINCO_11_ISCO_08.dta" file (in MEX_{Year}_ENOE_V{##}_M\Data\Stata) that is used in the harmonization process.