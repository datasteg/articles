// ISO 3166-1 alpha-3 → alpha-2 and English short name, for the /svc/v1 economy hook: articles' meta.countries uses
// alpha-2 codes (KR, US) plus EA (euro area) and EU, while the datasteg API names economies by alpha-3 (KOR, USA; EMU
// for the euro area, EUU for the EU, as money-flow and the World Bank do). Generated on 10 Nov 2026 from
// money-flow/config/economies.csv (its non-aggregate rows); English names only.
export const ISO3: Record<string, [string, string]> = {
  ABW:["AW","Aruba"],AFG:["AF","Afghanistan"],AGO:["AO","Angola"],AIA:["AI","Anguilla"],
  ALA:["AX","\u00c5land Islands"],ALB:["AL","Albania"],AND:["AD","Andorra"],ARE:["AE","UAE"],ARG:["AR","Argentina"],
  ARM:["AM","Armenia"],ASM:["AS","American Samoa"],ATA:["AQ","Antarctica"],ATF:["TF","French Southern Territories"],
  ATG:["AG","Antigua and Barbuda"],AUS:["AU","Australia"],AUT:["AT","Austria"],AZE:["AZ","Azerbaijan"],
  BDI:["BI","Burundi"],BEL:["BE","Belgium"],BEN:["BJ","Benin"],BES:["BQ","Bonaire"],BFA:["BF","Burkina Faso"],
  BGD:["BD","Bangladesh"],BGR:["BG","Bulgaria"],BHR:["BH","Bahrain"],BHS:["BS","Bahamas"],
  BIH:["BA","Bosnia and Herzegovina"],BLM:["BL","St Barth\u00e9lemy"],BLR:["BY","Belarus"],BLZ:["BZ","Belize"],
  BMU:["BM","Bermuda"],BOL:["BO","Bolivia"],BRA:["BR","Brazil"],BRB:["BB","Barbados"],BRN:["BN","Brunei"],
  BTN:["BT","Bhutan"],BVT:["BV","Bouvet Island"],BWA:["BW","Botswana"],CAF:["CF","Central African Republic"],
  CAN:["CA","Canada"],CCK:["CC","Cocos Islands"],CHE:["CH","Switzerland"],CHL:["CL","Chile"],CHN:["CN","China"],
  CIV:["CI","C\u00f4te d'Ivoire"],CMR:["CM","Cameroon"],COD:["CD","DR Congo"],COG:["CG","Congo"],
  COK:["CK","Cook Islands"],COL:["CO","Colombia"],COM:["KM","Comoros"],CPV:["CV","Cabo Verde"],
  CRI:["CR","Costa Rica"],CUB:["CU","Cuba"],CUW:["CW","Cura\u00e7ao"],CXR:["CX","Christmas Island"],
  CYM:["KY","Cayman Islands"],CYP:["CY","Cyprus"],CZE:["CZ","Czechia"],DEU:["DE","Germany"],DJI:["DJ","Djibouti"],
  DMA:["DM","Dominica"],DNK:["DK","Denmark"],DOM:["DO","Dominican Republic"],DZA:["DZ","Algeria"],
  ECU:["EC","Ecuador"],EGY:["EG","Egypt"],EMU:["EA","Euro area"],ERI:["ER","Eritrea"],ESH:["EH","Western Sahara"],
  ESP:["ES","Spain"],EST:["EE","Estonia"],ETH:["ET","Ethiopia"],EUU:["EU","European Union"],FIN:["FI","Finland"],
  FJI:["FJ","Fiji"],FLK:["FK","Falkland Islands"],FRA:["FR","France"],FRO:["FO","Faroe Islands"],
  FSM:["FM","Micronesia"],GAB:["GA","Gabon"],GBR:["GB","UK"],GEO:["GE","Georgia"],GGY:["GG","Guernsey"],
  GHA:["GH","Ghana"],GIB:["GI","Gibraltar"],GIN:["GN","Guinea"],GLP:["GP","Guadeloupe"],GMB:["GM","Gambia"],
  GNB:["GW","Guinea-Bissau"],GNQ:["GQ","Equatorial Guinea"],GRC:["GR","Greece"],GRD:["GD","Grenada"],
  GRL:["GL","Greenland"],GTM:["GT","Guatemala"],GUF:["GF","French Guiana"],GUM:["GU","Guam"],GUY:["GY","Guyana"],
  HKG:["HK","Hong Kong"],HMD:["HM","Heard and McDonald Islands"],HND:["HN","Honduras"],HRV:["HR","Croatia"],
  HTI:["HT","Haiti"],HUN:["HU","Hungary"],IDN:["ID","Indonesia"],IMN:["IM","Isle of Man"],IND:["IN","India"],
  IOT:["IO","British Indian Ocean Territory"],IRL:["IE","Ireland"],IRN:["IR","Iran"],IRQ:["IQ","Iraq"],
  ISL:["IS","Iceland"],ISR:["IL","Israel"],ITA:["IT","Italy"],JAM:["JM","Jamaica"],JEY:["JE","Jersey"],
  JOR:["JO","Jordan"],JPN:["JP","Japan"],KAZ:["KZ","Kazakhstan"],KEN:["KE","Kenya"],KGZ:["KG","Kyrgyzstan"],
  KHM:["KH","Cambodia"],KIR:["KI","Kiribati"],KNA:["KN","St Kitts and Nevis"],KOR:["KR","Korea"],KWT:["KW","Kuwait"],
  LAO:["LA","Laos"],LBN:["LB","Lebanon"],LBR:["LR","Liberia"],LBY:["LY","Libya"],LCA:["LC","St Lucia"],
  LIE:["LI","Liechtenstein"],LKA:["LK","Sri Lanka"],LSO:["LS","Lesotho"],LTU:["LT","Lithuania"],
  LUX:["LU","Luxembourg"],LVA:["LV","Latvia"],MAC:["MO","Macao"],MAF:["MF","St Martin"],MAR:["MA","Morocco"],
  MCO:["MC","Monaco"],MDA:["MD","Moldova"],MDG:["MG","Madagascar"],MDV:["MV","Maldives"],MEX:["MX","Mexico"],
  MHL:["MH","Marshall Islands"],MKD:["MK","North Macedonia"],MLI:["ML","Mali"],MLT:["MT","Malta"],
  MMR:["MM","Myanmar"],MNE:["ME","Montenegro"],MNG:["MN","Mongolia"],MNP:["MP","Northern Marianas"],
  MOZ:["MZ","Mozambique"],MRT:["MR","Mauritania"],MSR:["MS","Montserrat"],MTQ:["MQ","Martinique"],
  MUS:["MU","Mauritius"],MWI:["MW","Malawi"],MYS:["MY","Malaysia"],MYT:["YT","Mayotte"],NAM:["NA","Namibia"],
  NCL:["NC","New Caledonia"],NER:["NE","Niger"],NFK:["NF","Norfolk Island"],NGA:["NG","Nigeria"],
  NIC:["NI","Nicaragua"],NIU:["NU","Niue"],NLD:["NL","Netherlands"],NOR:["NO","Norway"],NPL:["NP","Nepal"],
  NRU:["NR","Nauru"],NZL:["NZ","New Zealand"],OMN:["OM","Oman"],PAK:["PK","Pakistan"],PAN:["PA","Panama"],
  PCN:["PN","Pitcairn Islands"],PER:["PE","Peru"],PHL:["PH","Philippines"],PLW:["PW","Palau"],
  PNG:["PG","Papua New Guinea"],POL:["PL","Poland"],PRI:["PR","Puerto Rico"],PRK:["KP","North Korea"],
  PRT:["PT","Portugal"],PRY:["PY","Paraguay"],PSE:["PS","Palestine"],PYF:["PF","French Polynesia"],QAT:["QA","Qatar"],
  REU:["RE","R\u00e9union"],ROU:["RO","Romania"],RUS:["RU","Russia"],RWA:["RW","Rwanda"],SAU:["SA","Saudi Arabia"],
  SDN:["SD","Sudan"],SEN:["SN","Senegal"],SGP:["SG","Singapore"],SGS:["GS","South Georgia"],SHN:["SH","St Helena"],
  SJM:["SJ","Svalbard and Jan Mayen"],SLB:["SB","Solomon Islands"],SLE:["SL","Sierra Leone"],SLV:["SV","El Salvador"],
  SMR:["SM","San Marino"],SOM:["SO","Somalia"],SPM:["PM","St Pierre and Miquelon"],SRB:["RS","Serbia"],
  SSD:["SS","South Sudan"],STP:["ST","S\u00e3o Tom\u00e9 and Pr\u00edncipe"],SUR:["SR","Suriname"],
  SVK:["SK","Slovakia"],SVN:["SI","Slovenia"],SWE:["SE","Sweden"],SWZ:["SZ","Eswatini"],SXM:["SX","Sint Maarten"],
  SYC:["SC","Seychelles"],SYR:["SY","Syria"],TCA:["TC","Turks and Caicos"],TCD:["TD","Chad"],TGO:["TG","Togo"],
  THA:["TH","Thailand"],TJK:["TJ","Tajikistan"],TKL:["TK","Tokelau"],TKM:["TM","Turkmenistan"],
  TLS:["TL","Timor-Leste"],TON:["TO","Tonga"],TTO:["TT","Trinidad and Tobago"],TUN:["TN","Tunisia"],
  TUR:["TR","T\u00fcrkiye"],TUV:["TV","Tuvalu"],TWN:["TW","Taiwan"],TZA:["TZ","Tanzania"],UGA:["UG","Uganda"],
  UKR:["UA","Ukraine"],UMI:["UM","US Outlying Islands"],URY:["UY","Uruguay"],USA:["US","United States"],
  UZB:["UZ","Uzbekistan"],VAT:["VA","Vatican"],VCT:["VC","St Vincent and Grenadines"],VEN:["VE","Venezuela"],
  VGB:["VG","British Virgin Islands"],VIR:["VI","US Virgin Islands"],VNM:["VN","Vietnam"],VUT:["VU","Vanuatu"],
  WLF:["WF","Wallis and Futuna"],WSM:["WS","Samoa"],XKX:["XK","Kosovo"],YEM:["YE","Yemen"],ZAF:["ZA","South Africa"],
  ZMB:["ZM","Zambia"],ZWE:["ZW","Zimbabwe"],
};

/** Alternative codes callers use for the two aggregates. */
const ALIASES: Record<string, string> = { EA: 'EMU', EA19: 'EMU', EA20: 'EMU', EU27: 'EUU', EU: 'EUU', EU28: 'EUU' };

/** The alpha-3 code and its alpha-2 code and name, or null for a code no table knows. */
export function economy(code: string): { iso3: string; iso2: string; name: string } | null {
  const c = (ALIASES[code.toUpperCase()] ?? code.toUpperCase());
  const hit = ISO3[c];
  return hit ? { iso3: c, iso2: hit[0], name: hit[1] } : null;
}

/** The alpha-3 code of an alpha-2 code (KR → KOR), for the list's country filter. */
const BY_ISO2 = new Map(Object.entries(ISO3).map(([k, v]) => [v[0], k]));
export const iso3Of = (iso2: string) => BY_ISO2.get(iso2.toUpperCase()) ?? null;
