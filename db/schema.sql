-- db/schema.sql

-- Every material from every source lands here first
CREATE TABLE IF NOT EXISTS materials (
    id                  SERIAL PRIMARY KEY,
    mp_id               VARCHAR(20) UNIQUE,        -- Materials Project ID e.g. "mp-72"
    name                VARCHAR(200) NOT NULL,      -- Human readable e.g. "Ti-6Al-4V"
    formula             VARCHAR(100) NOT NULL,      -- Chemical formula e.g. "Ti3Al2V2"
    formula_reduced     VARCHAR(100),               -- Simplified formula
    crystal_system      VARCHAR(50),                -- cubic, hexagonal, etc.
    space_group         VARCHAR(50),                -- Crystal space group
    
    -- Source tracking — where did this come from?
    source              VARCHAR(100) DEFAULT 'materials_project',
    source_url          TEXT,
    trust_level         VARCHAR(20)  DEFAULT 'PROVISIONAL',
    -- VERIFIED | PROVISIONAL | COMMUNITY | UNVERIFIED
    
    -- Metadata
    ingested_at         TIMESTAMP DEFAULT NOW(),
    last_updated        TIMESTAMP DEFAULT NOW(),
    human_reviewed      BOOLEAN DEFAULT FALSE,
    needs_review        BOOLEAN DEFAULT FALSE,
    review_notes        TEXT
);

-- Properties stored separately — one row per property per material
-- This is the key design: flexible, extensible, condition-aware
CREATE TABLE IF NOT EXISTS material_properties (
    id                  SERIAL PRIMARY KEY,
    material_id         INTEGER REFERENCES materials(id) ON DELETE CASCADE,
    
    -- What property is this?
    property_name       VARCHAR(100) NOT NULL,
    -- density, tensile_strength, melting_point, band_gap, etc.
    
    -- The actual value
    value_numeric       FLOAT,                      -- For numbers
    value_text          TEXT,                       -- For text values
    unit                VARCHAR(50),                -- MPa, g/cm³, °C, etc.
    
    -- Original value before normalization
    original_value      FLOAT,
    original_unit       VARCHAR(50),
    
    -- Condition under which this property was measured
    -- This is what most databases miss
    condition_temp_c    FLOAT,                      -- Temperature in °C
    condition_notes     TEXT,                       -- e.g. "annealed at 800°C"
    test_standard       VARCHAR(100),               -- ASTM E8, ISO 6892, etc.
    
    -- Trust and source
    source              VARCHAR(100),
    trust_level         VARCHAR(20) DEFAULT 'PROVISIONAL',
    
    ingested_at         TIMESTAMP DEFAULT NOW()
);

-- Elements that make up each material (composition)
CREATE TABLE IF NOT EXISTS material_composition (
    id                  SERIAL PRIMARY KEY,
    material_id         INTEGER REFERENCES materials(id) ON DELETE CASCADE,
    element_symbol      VARCHAR(5)  NOT NULL,       -- Ti, Al, V, Fe, etc.
    element_name        VARCHAR(50),                -- Titanium, Aluminum, etc.
    atomic_fraction     FLOAT,                      -- 0.0 to 1.0
    weight_fraction     FLOAT                       -- 0.0 to 1.0
);

-- Track every ingestion run — for debugging and auditing
CREATE TABLE IF NOT EXISTS ingestion_log (
    id                  SERIAL PRIMARY KEY,
    run_id              VARCHAR(50) UNIQUE,         -- UUID for this run
    source              VARCHAR(100),
    started_at          TIMESTAMP DEFAULT NOW(),
    completed_at        TIMESTAMP,
    status              VARCHAR(20),                -- RUNNING | SUCCESS | FAILED
    materials_fetched   INTEGER DEFAULT 0,
    materials_inserted  INTEGER DEFAULT 0,
    materials_skipped   INTEGER DEFAULT 0,
    errors_count        INTEGER DEFAULT 0,
    error_details       JSONB,
    notes               TEXT
);

-- Indexes for fast querying by agents later
CREATE INDEX IF NOT EXISTS idx_materials_formula 
    ON materials(formula_reduced);
CREATE INDEX IF NOT EXISTS idx_properties_name 
    ON material_properties(property_name);
CREATE INDEX IF NOT EXISTS idx_properties_material 
    ON material_properties(material_id);
CREATE INDEX IF NOT EXISTS idx_composition_element 
    ON material_composition(element_symbol);