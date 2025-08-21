-- Auto-Promo AI Main Database Schema
-- This file imports all schema components in the correct order

-- Import extensions first
\i schema/00-extensions.sql

-- Import user management
\i schema/01-user-management.sql

-- Import subscription system
\i schema/02-subscription-system.sql

-- Import credit system
\i schema/03-credit-system.sql

-- Import content system
\i schema/04-content-system.sql

-- Import media system
\i schema/05-media-system.sql

-- Import functions
\i schema/06-functions.sql

-- Import views
\i schema/07-views.sql

-- Import initial data last
\i schema/08-initial-data.sql 