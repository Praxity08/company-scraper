-- Tables in the Neon project "company-scraper" (already created there; kept here as a record).
-- Running these statements twice changes nothing.

-- One row per domain scrape. "result" is the full scraper output (pages and their text).
CREATE TABLE IF NOT EXISTS scrapes (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  created_at timestamptz NOT NULL DEFAULT now(),
  domain text NOT NULL,
  status text NOT NULL,
  found text[] NOT NULL DEFAULT '{}',
  missing text[] NOT NULL DEFAULT '{}',
  result jsonb NOT NULL
);
CREATE INDEX IF NOT EXISTS scrapes_created_idx ON scrapes (created_at DESC);

-- At most ONE Hunter lookup per scrape (the primary key makes a second one impossible).
-- outcome: 'pending' while Hunter is being asked, then 'found' or 'none'.
-- Rows are deleted 30 days after the lookup.
CREATE TABLE IF NOT EXISTS contacts (
  scrape_id uuid PRIMARY KEY REFERENCES scrapes(id) ON DELETE CASCADE,
  created_at timestamptz NOT NULL DEFAULT now(),
  domain text NOT NULL,
  outcome text NOT NULL CHECK (outcome IN ('pending', 'found', 'none')),
  contact jsonb
);
CREATE INDEX IF NOT EXISTS contacts_created_idx ON contacts (created_at);

-- Daily counters, by India date (e.g. Hunter lookups per day).
CREATE TABLE IF NOT EXISTS counters (
  day date NOT NULL,
  name text NOT NULL,
  n integer NOT NULL DEFAULT 0,
  PRIMARY KEY (day, name)
);
