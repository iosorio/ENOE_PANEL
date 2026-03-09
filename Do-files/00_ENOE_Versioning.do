* ENOE version manifest
*
* Current naming convention:
*   MEX_2005_ENOE_V01_M_V07_A_GLD
*
* Components:
*   MEX   = ISO3 country code
*   2005  = survey year
*   ENOE  = survey name
*   V01_M = raw/master data version
*   V07_A = harmonization ("alt") version
*   GLD   = harmonization template acronym
*
* Versioning rules:
*   1. Bump raw/master version (for example V01_M -> V02_M) only when INEGI
*      republishes the raw microdata or the raw input package changes in a way
*      that affects the master files used by the harmonization.
*   2. Bump harmonization version (for example V06_A -> V07_A) only when there
*      is a substantive harmonization change that should create a new release
*      lineage for the generated harmonized outputs. Future promotions should
*      scaffold a new version tree and preserve the older version tree,
*      do-files, and resulting databases for reproducibility.
*   3. The upstream World Bank GLD comparison baseline can remain on an older
*      harmonization version while local work advances. Keep that baseline
*      explicit below so local-vs-upstream diffs remain reproducible.

if "${enoe_country}" == "" global enoe_country "MEX"
if "${enoe_survey}" == "" global enoe_survey "ENOE"
if "${enoe_raw_version}" == "" global enoe_raw_version "V01"
if "${enoe_harm_version}" == "" global enoe_harm_version "V07"
if "${enoe_harmonization_acronym}" == "" global enoe_harmonization_acronym "GLD"

if "${enoe_raw_tag}" == "" global enoe_raw_tag "${enoe_raw_version}_M"
if "${enoe_harm_tag}" == "" global enoe_harm_tag "${enoe_raw_version}_M_${enoe_harm_version}_A_${enoe_harmonization_acronym}"

if "${enoe_upcmp_raw_version}" == "" global enoe_upcmp_raw_version "V01"
if "${enoe_upcmp_harm_version}" == "" global enoe_upcmp_harm_version "V06"
if "${enoe_upcmp_harm_tag}" == "" global enoe_upcmp_harm_tag "${enoe_upcmp_raw_version}_M_${enoe_upcmp_harm_version}_A_${enoe_harmonization_acronym}"
if "${enoe_upcmp_repo}" == "" global enoe_upcmp_repo "https://github.com/worldbank/gld.git"
