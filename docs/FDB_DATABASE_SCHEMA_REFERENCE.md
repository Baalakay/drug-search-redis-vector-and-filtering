# FDB Database Schema Reference

**Database Type:** Aurora MySQL Serverless v2  
**Database Name:** `fdb`  
**Total Tables:** 118  
**Primary Drug Table:** `rndc14` (493,573 drugs)

---

## 📊 Database Overview

The FDB (First DataBank) database contains 118 tables with comprehensive drug information, pricing, interactions, and clinical data.

### Major Table Categories

| Category | Key Tables | Total Rows |
|----------|-----------|------------|
| **Drug Master Data** | `rndc14`, `rmindc1` | 493K + 493K |
| **Pricing** | `rnp2` | 12.8M |
| **Drug Interactions** | `rddimrm0`, `rddimag0` | 998K + 89K |
| **RxNorm Mappings** | `rxnconso`, `revdel0_ext_vocab_link` | 1.0M + 611K |
| **Clinical Content** | `rfmlisr1`, `rfmlinm1` | 442K + 204K |
| **Generic Classification** | `rgcnseq4` | 37K |

---

## 🔍 RNDC14 - Main Drug Table (493,573 records)

### Identity & Basic Information

| Field | Type | Description | Sample Values / Distribution |
|-------|------|-------------|------------------------------|
| **NDC** | `varchar(11)` | **National Drug Code** - Unique 11-digit identifier for each drug product | `00002063202`, `00002030902` |
| **LBLRID** | `varchar(6)` | **Labeler ID** - Manufacturer/distributor code (4,590 unique labelers) | `A00002`, `A00003`, `A00004` |
| **LN** | `varchar(30)` | **Label Name (30 chars)** - Short drug name | `LISINOPRIL 10 MG TABLET` |
| **LN60** | `varchar(60)` | **Label Name (60 chars)** - Full drug name with strength and form | `AMMONIUM CHLORIDE 500 MG ENS` |
| **BN** | `varchar(30)` | **Brand Name** - Trade/brand name (47,853 unique brands) | `PRINIVIL`, `LIPITOR`, `ZOCOR` |

### Drug Classification

| Field | Type | Description | Distribution |
|-------|------|-------------|--------------|
| **GCN_SEQNO** | `mediumint` | **Generic Code Number** - Groups therapeutically equivalent drugs (32,257 unique) | Used for generic substitution |
| **INNOV** | `varchar(1)` | **Innovator Flag** - Brand vs Generic indicator | `0` = Generic (86.5%)<br>`1` = Brand/Innovator (13.5%) |
| **GNI** | `varchar(1)` | **Generic Name Indicator** - Status in generic marketplace | `1` = Most common (54.7%)<br>`2` = Secondary (31.1%)<br>`0` = Other (14.2%) |
| **GMI** | `varchar(1)` | **Generic Multisource Indicator** - Number of manufacturers | `1` = Single source (39.5%)<br>`4` = Multi-source (31.7%)<br>`0-3` = Various |
| **GTI** | `varchar(1)` | **Generic Therapeutic Indicator** | `4` = Most common (46.6%)<br>`3` = Secondary (29.9%) |

### Physical Characteristics

| Field | Type | Description | Distribution |
|-------|------|-------------|--------------|
| **DF** | `varchar(1)` | **Dosage Form Code** | `1` = Solid oral (70.1%)<br>`2` = Liquid/Injectable (19.9%)<br>`3` = Topical/Other (9.9%) |
| **PS** | `decimal(11,3)` | **Package Size** - Quantity in package | `100.000`, `1000.000`, `0.500` |
| **AD** | `varchar(20)` | **Additional Description** - Packaging details | `ENSEAL`, `SUV`, `P/F` |
| **PD** | `varchar(10)` | **Package Description** - Container type | `BOTTLE`, `VIAL`, `BLIST PACK`, `SYRINGE`, `BOX` |

### Regulatory & Control

| Field | Type | Description | Distribution |
|-------|------|-------------|--------------|
| **DEA** | `varchar(1)` | **DEA Schedule** - Controlled substance classification | `0` = Not controlled (90.8%)<br>`4` = Schedule IV (4.1%)<br>`2` = Schedule II (2.5%)<br>`3` = Schedule III (1.8%)<br>`5` = Schedule V (0.7%) |
| **CL** | `varchar(1)` | **Drug Class** | `F` = (66.3%)<br>`O` = OTC (29.1%)<br>`Q` = (4.6%) |
| **HOSP** | `varchar(1)` | **Hospital Use** | `0` = Not hospital (71.6%)<br>`1` = Hospital use (28.4%) |
| **UD** | `varchar(1)` | **Unit Dose** | `0` = Not unit dose (94.5%)<br>`1` = Unit dose (5.5%) |

### Product Status

| Field | Type | Description | Distribution |
|-------|------|-------------|--------------|
| **OBC** | `varchar(2)` | **Orange Book Code** - FDA approval status | `ZB` = Generic (43.1%)<br>`ZA` = Innovator (27.7%)<br>`AB` = Therapeutic equivalent (19.9%)<br>`AP`, `ZC`, `AA` = Various |
| **REPACK** | `varchar(1)` | **Repackaged Product** | `0` = Original (75.7%)<br>`1` = Repackaged (24.3%) |
| **STPK** | `varchar(1)` | **Stock Package** | `0` = Not stock (84.2%)<br>`1` = Stock package (15.8%) |
| **IPI** | `varchar(1)` | **Investigational Product Indicator** | `0` = Not investigational (99.3%)<br>`1` = Investigational (0.7%) |
| **MINI** | `varchar(1)` | **Maintenance Drug Indicator** | `0` = Not maintenance (84.5%)<br>`1` = Maintenance (15.5%) |

### Dates

| Field | Type | Description |
|-------|------|-------------|
| **DADDNC** | `datetime(6)` | **Date Added to NDC** - When drug was added (8,800 unique dates) |
| **DUPDC** | `datetime(6)` | **Date Updated** - Last modification date (2,506 unique dates) |
| **OBSDTEC** | `datetime(6)` | **Obsolete Date** - Discontinuation date |
| **GPIDC** | `datetime(6)` | **GPI Date** - GPI assignment date |
| **BBDC** | `datetime(6)` | **Black Box Date** - Black box warning date |

### HCFA/Medicare Fields

| Field | Type | Description | Distribution |
|-------|------|-------------|--------------|
| **HCFA_FDA** | `varchar(2)` | **HCFA FDA Code** - Medicare approval code | 23 unique codes |
| **HCFA_UNIT** | `varchar(3)` | **HCFA Unit** - Billing unit | `TAB` (16.9%), `ML` (9.1%), `CAP` (4.4%), `GM` (2.8%) |
| **HCFA_PS** | `decimal(11,3)` | **HCFA Package Size** - Medicare package size |
| **HCFA_TYP** | `varchar(1)` | **HCFA Type** | Empty (65.1%), `1` (27.9%), `2` (7.0%) |
| **HCFA_DC** | `varchar(1)` | **HCFA Drug Category** | Empty (67.0%), `N` (26.7%), `I` (3.5%), `S` (2.9%) |

### Packaging & Administration

| Field | Type | Description |
|-------|------|-------------|
| **NDL_GDGE** | `decimal(5,3)` | **Needle Gauge** - For injectable products |
| **NDL_LNGTH** | `decimal(5,3)` | **Needle Length** - In inches |
| **SYR_CPCTY** | `decimal(5,3)` | **Syringe Capacity** - Volume in mL |
| **SHLF_PCK** | `int` | **Shelf Pack** - Units per shelf pack |
| **SHIPPER** | `int` | **Shipper** - Units per shipper box |
| **CSP** | `int` | **Count of Solid Products** - Pills/tablets per package |

### Related Product Links

| Field | Type | Description |
|-------|------|-------------|
| **PNDC** | `varchar(11)` | **Parent NDC** - Original product for repackages (18,543 unique) |
| **REPNDC** | `varchar(11)` | **Replacement NDC** - Superseding product (18,543 unique) |

### Specialty Indicators

| Field | Type | Description | Distribution |
|-------|------|-------------|--------------|
| **HOME** | `varchar(1)` | **Home Health** | `0` = Not home health (95.6%)<br>`1` = Home health (4.4%) |
| **PLBLR** | `varchar(1)` | **Private Label** | `0` = Not private label (90.6%)<br>`1` = Private label (9.4%) |
| **INPCKI** | `varchar(1)` | **Inpatient Package** | `0` = No (97.2%)<br>`1` = Yes (2.8%) |
| **OUTPCKI** | `varchar(1)` | **Outpatient Package** | `0` = No (97.0%)<br>`1` = Yes (3.0%) |
| **LN25I** | `varchar(1)` | **Label Name 25 Indicator** | `1` (60.6%), `0` (39.4%) |
| **NDCGI1** | `varchar(1)` | **NDC GI Indicator** | `1` (90.9%), `2` (9.1%) |
| **UU** | `varchar(1)` | **Unit Use** | `0` = Not unit use (99.3%)<br>`1` = Unit use (0.7%) |
| **PPI** | `varchar(1)` | **Patient Package Insert** | Empty (99.0%), `1` = Has PPI (1.0%) |

### Top Drugs

| Field | Type | Description |
|-------|------|-------------|
| **TOP200** | `varchar(3)` | **Top 200 Drugs** - Ranking in top prescribed drugs (196 unique ranks) |
| **TOP50GEN** | `varchar(2)` | **Top 50 Generic** - Ranking in top generic drugs (51 unique ranks) |

### Legacy/Unused Fields

| Field | Type | Description | Status |
|-------|------|-------------|--------|
| **DESI** | `varchar(1)` | **DESI Status** | All empty |
| **DESDTEC** | `datetime(6)` | **DESI Date** | All zeros |
| **DESI2** | `varchar(1)` | **DESI Status 2** | All empty |
| **DES2DTEC** | `datetime(6)` | **DESI Date 2** | All zeros |
| **LN25** | `varchar(25)` | **Label Name 25** | All empty |
| **HCFA_DESC1** | `datetime(6)` | **HCFA Description Date** | All zeros |
| **HCFA_DESI1** | `varchar(1)` | **HCFA DESI** | All empty |
| **GPI** | `varchar(1)` | **GPI Indicator** | All `9` |
| **GSI** | `varchar(1)` | **GS Indicator** | All `9` |

### Additional Status Fields

| Field | Type | Description |
|-------|------|-------------|
| **NDCFI** | `varchar(1)` | **NDC Format Indicator** - Format of NDC display |
| **OBC_EXP** | `varchar(2)` | **Orange Book Code Expanded** |
| **OBC3** | `varchar(3)` | **Orange Book Code 3-char** |
| **PS_EQUIV** | `decimal(11,3)` | **Package Size Equivalent** |
| **MAINT** | `varchar(1)` | **Maintenance** - Empty (66.1%), `1` (33.9%) |
| **HCFA_APPC** | `datetime(6)` | **HCFA Application Date** |
| **HCFA_MRKC** | `datetime(6)` | **HCFA Market Date** |
| **HCFA_TRMC** | `datetime(6)` | **HCFA Termination Date** |

---

## 🔑 Key Field Interpretation Summary

### For Generic vs Brand Determination

**PRIMARY INDICATOR: INNOV**
- `INNOV = '0'` → **Generic** (86.5% of drugs)
- `INNOV = '1'` → **Brand/Innovator** (13.5% of drugs)

**Supporting fields:**
- `GNI`: Generic marketplace status (1, 2, or 0)
- `GMI`: Number of manufacturers (1=single, 4=multi-source)
- `OBC`: Orange Book therapeutic equivalence code

### For Controlled Substances

**PRIMARY INDICATOR: DEA**
- `DEA = '0'` → Not controlled (90.8%)
- `DEA = '2'` → Schedule II (2.5%) - High abuse potential
- `DEA = '3'` → Schedule III (1.8%)
- `DEA = '4'` → Schedule IV (4.1%)
- `DEA = '5'` → Schedule V (0.7%)

### For Drug Classification

**Use GCN_SEQNO** (Generic Code Number)
- Links to `rgcnseq4` table for full therapeutic classification
- 32,257 unique GCN codes group therapeutically equivalent drugs

---

## 📚 Related Tables (Key References)

| Table | Rows | Purpose |
|-------|------|---------|
| **rgcnseq4** | 37,693 | Generic classification and drug grouping by GCN |
| **rnp2** | 12.8M | National pricing data |
| **rddimrm0** | 998K | Drug-drug interaction monographs |
| **rxnconso** | 1.0M | RxNorm concept mappings |
| **rfmlisr1** | 442K | Drug-indication relationships |
| **rhicd5** | 16,301 | ICD-10 diagnosis codes |
| **rlblrid3** | 5,267 | Labeler/manufacturer details |

---

## 💡 Usage Notes

1. **For drug search by name**: Use `LN60` (full 60-char name) or `LN` (30-char)
2. **For brand identification**: Check `BN` (brand name) and `INNOV='1'`
3. **For generic substitution**: Group by `GCN_SEQNO`
4. **For controlled substances**: Filter by `DEA IN ('2','3','4','5')`
5. **For active drugs**: Exclude records where `OBSDTEC` is set (obsolete)
6. **For therapeutic classification**: Join to `rgcnseq4` on `GCN_SEQNO`

---

## 🔍 Data Quality Observations

- **493,573 total drug records** in `rndc14`
- **97,463 unique drug names** (LN60)
- **47,853 unique brand names**
- **32,257 unique GCN codes** for grouping
- **4,590 unique manufacturers/labelers**
- **INNOV field is reliable** for generic/brand classification
- **GNI field meaning unclear** - values 0, 1, 2 without documentation
- Several legacy fields are unused (all NULL or zero)

---

**Last Updated:** 2025-11-15  
**Data Source:** Aurora MySQL `fdb` database  
**Analysis Method:** Direct database inspection with sample data verification

