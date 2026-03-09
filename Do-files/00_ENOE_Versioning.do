* ENOE version manifest
*
* Current naming convention:
*   MEX_2005_ENOE_V01_M_V06_A_GLD
*
* Components:
*   MEX   = ISO3 country code
*   2005  = survey year
*   ENOE  = survey name
*   V01_M = raw/master data version
*   V06_A = harmonization ("alt") version
*   GLD   = harmonization template acronym
*
* Versioning rules:
*   1. Bump raw/master version (for example V01_M -> V02_M) only when INEGI
*      republishes the raw microdata or the raw input package changes in a way
*      that affects the master files used by the harmonization.
*   2. Bump harmonization version (for example V06_A -> V07_A) only when there
*      is a substantive harmonization change that should create a new release
*      lineage for the generated harmonized outputs.
*   3. The upstream World Bank GLD comparison baseline can remain on an older
*      harmonization version while local work advances. Keep that baseline
*      explicit below so local-vs-upstream diffs remain reproducible.

if "${enoe_country}" == "" global enoe_country "MEX"
if "${enoe_survey}" == "" global enoe_survey "ENOE"
if "${enoe_raw_version}" == "" global enoe_raw_version "V01"
if "${enoe_harm_version}" == "" global enoe_harm_version "V06"
if "${enoe_harmonization_acronym}" == "" global enoe_harmonization_acronym "GLD"

if "${enoe_raw_tag}" == "" global enoe_raw_tag "${enoe_raw_version}_M"
if "${enoe_harm_tag}" == "" global enoe_harm_tag "${enoe_raw_version}_M_${enoe_harm_version}_A_${enoe_harmonization_acronym}"

if "${enoe_upstream_compare_raw_version}" == "" global enoe_upstream_compare_raw_version "V01"
if "${enoe_upstream_compare_harm_version}" == "" global enoe_upstream_compare_harm_version "V06"
if "${enoe_upstream_compare_harm_tag}" == "" global enoe_upstream_compare_harm_tag "${enoe_upstream_compare_raw_version}_M_${enoe_upstream_compare_harm_version}_A_${enoe_harmonization_acronym}"
if "${enoe_upstream_repo}" == "" global enoe_upstream_repo "https://github.com/worldbank/gld.git"

