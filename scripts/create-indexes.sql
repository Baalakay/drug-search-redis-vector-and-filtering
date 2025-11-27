--
-- Create Indexes for DAW Drug Search
--
-- This script creates performance indexes on the FDB tables
-- to optimize drug search queries.
--

\timing on

BEGIN;

-- ================================================================
-- PRIMARY DRUG TABLE (rndc14) INDEXES
-- ================================================================

\echo ''
\echo '📊 Creating indexes on rndc14 (primary drug table)...'

-- Primary key (if not already created)
CREATE INDEX IF NOT EXISTS idx_rndc14_ndc ON rndc14(ndc);

-- Generic Code Number (for drug classification joins)
CREATE INDEX IF NOT EXISTS idx_rndc14_gcn_seqno ON rndc14(gcn_seqno);

-- Drug names (for text search)
CREATE INDEX IF NOT EXISTS idx_rndc14_ln ON rndc14(ln);  -- Label name
CREATE INDEX IF NOT EXISTS idx_rndc14_bn ON rndc14(bn);  -- Brand name

-- Labeler ID (for manufacturer queries)
CREATE INDEX IF NOT EXISTS idx_rndc14_lblrid ON rndc14(lblrid);

-- DEA Schedule (for controlled substance filtering)
CREATE INDEX IF NOT EXISTS idx_rndc14_dea ON rndc14(dea);

-- Dosage form and route
CREATE INDEX IF NOT EXISTS idx_rndc14_df ON rndc14(df);

-- Composite index for common query patterns
CREATE INDEX IF NOT EXISTS idx_rndc14_gcn_dea ON rndc14(gcn_seqno, dea);

\echo '✅ rndc14 indexes created'

-- ================================================================
-- GENERIC CLASSIFICATION TABLE (rgcnseq4) INDEXES
-- ================================================================

\echo ''
\echo '📊 Creating indexes on rgcnseq4 (drug classification)...'

-- Primary key
CREATE INDEX IF NOT EXISTS idx_rgcnseq4_gcn_seqno ON rgcnseq4(gcn_seqno);

-- Hierarchical ingredient code (drug class)
CREATE INDEX IF NOT EXISTS idx_rgcnseq4_hic3 ON rgcnseq4(hic3);
CREATE INDEX IF NOT EXISTS idx_rgcnseq4_hicl_seqno ON rgcnseq4(hicl_seqno);

-- Therapeutic class (for indication-based searches)
CREATE INDEX IF NOT EXISTS idx_rgcnseq4_gtc ON rgcnseq4(gtc);
CREATE INDEX IF NOT EXISTS idx_rgcnseq4_tc ON rgcnseq4(tc);

-- Route of administration
CREATE INDEX IF NOT EXISTS idx_rgcnseq4_gcrt ON rgcnseq4(gcrt);

-- Composite index for common joins
CREATE INDEX IF NOT EXISTS idx_rgcnseq4_hicl_gtc ON rgcnseq4(hicl_seqno, gtc);

\echo '✅ rgcnseq4 indexes created'

-- ================================================================
-- PRICING TABLE (rnp2) INDEXES
-- ================================================================

\echo ''
\echo '📊 Creating indexes on rnp2 (pricing)...'

-- NDC (foreign key to rndc14)
CREATE INDEX IF NOT EXISTS idx_rnp2_ndc ON rnp2(ndc);

-- Price type (AWP, WAC, etc.)
CREATE INDEX IF NOT EXISTS idx_rnp2_npt_type ON rnp2(npt_type);

-- Price effective date (for historical queries)
CREATE INDEX IF NOT EXISTS idx_rnp2_npt_datec ON rnp2(npt_datec);

-- Composite index for price lookups
CREATE INDEX IF NOT EXISTS idx_rnp2_ndc_type_date ON rnp2(ndc, npt_type, npt_datec DESC);

\echo '✅ rnp2 indexes created'

-- ================================================================
-- INDICATION TABLES (rdlimxx) INDEXES
-- ================================================================

\echo ''
\echo '📊 Creating indexes on indication tables...'

-- Check if table exists first (FDB may have different versions)
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'rdlimxx') THEN
        CREATE INDEX IF NOT EXISTS idx_rdlimxx_gcn_seqno ON rdlimxx(gcn_seqno);
        CREATE INDEX IF NOT EXISTS idx_rdlimxx_dxid ON rdlimxx(dxid);
        RAISE NOTICE '✅ rdlimxx indexes created';
    ELSE
        RAISE NOTICE '⚠️  rdlimxx table not found, skipping';
    END IF;
END$$;

-- ================================================================
-- DRUG INTERACTION TABLES (rddcmxx) INDEXES  
-- ================================================================

\echo ''
\echo '📊 Creating indexes on drug interaction tables...'

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'rddcmxx') THEN
        CREATE INDEX IF NOT EXISTS idx_rddcmxx_gcn_seqno ON rddcmxx(gcn_seqno);
        RAISE NOTICE '✅ rddcmxx indexes created';
    ELSE
        RAISE NOTICE '⚠️  rddcmxx table not found, skipping';
    END IF;
END$$;

-- ================================================================
-- SIDE EFFECTS TABLE (rsidexx) INDEXES
-- ================================================================

\echo ''
\echo '📊 Creating indexes on side effects tables...'

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'rsidexx') THEN
        CREATE INDEX IF NOT EXISTS idx_rsidexx_hicl_seqno ON rsidexx(hicl_seqno);
        RAISE NOTICE '✅ rsidexx indexes created';
    ELSE
        RAISE NOTICE '⚠️  rsidexx table not found, skipping';
    END IF;
END$$;

-- ================================================================
-- PREGNANCY CATEGORY TABLE (rpregxx) INDEXES
-- ================================================================

\echo ''
\echo '📊 Creating indexes on pregnancy category tables...'

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'rpregxx') THEN
        CREATE INDEX IF NOT EXISTS idx_rpregxx_gcn_seqno ON rpregxx(gcn_seqno);
        RAISE NOTICE '✅ rpregxx indexes created';
    ELSE
        RAISE NOTICE '⚠️  rpregxx table not found, skipping';
    END IF;
END$$;

COMMIT;

-- ================================================================
-- ANALYZE TABLES FOR QUERY PLANNER
-- ================================================================

\echo ''
\echo '📈 Analyzing tables for query optimizer...'

ANALYZE rndc14;
ANALYZE rgcnseq4;
ANALYZE rnp2;

-- Analyze optional tables if they exist
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'rdlimxx') THEN
        EXECUTE 'ANALYZE rdlimxx';
    END IF;
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'rddcmxx') THEN
        EXECUTE 'ANALYZE rddcmxx';
    END IF;
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'rsidexx') THEN
        EXECUTE 'ANALYZE rsidexx';
    END IF;
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'rpregxx') THEN
        EXECUTE 'ANALYZE rpregxx';
    END IF;
END$$;

\echo ''
\echo '✅ All indexes created and tables analyzed!'
\echo ''

-- ================================================================
-- VERIFY INDEX CREATION
-- ================================================================

\echo '📋 Index Summary:'
\echo ''

SELECT 
    schemaname,
    tablename,
    indexname,
    pg_size_pretty(pg_relation_size(indexrelid)) AS index_size
FROM pg_indexes
JOIN pg_class ON pg_class.relname = indexname
WHERE schemaname = 'public'
    AND tablename IN ('rndc14', 'rgcnseq4', 'rnp2', 'rdlimxx', 'rddcmxx', 'rsidexx', 'rpregxx')
ORDER BY tablename, indexname;

\echo ''
\echo '📊 Table Row Counts:'
\echo ''

SELECT 
    schemaname,
    tablename,
    n_live_tup AS estimated_rows
FROM pg_stat_user_tables
WHERE schemaname = 'public'
    AND tablename IN ('rndc14', 'rgcnseq4', 'rnp2', 'rdlimxx', 'rddcmxx', 'rsidexx', 'rpregxx')
ORDER BY tablename;

\echo ''

