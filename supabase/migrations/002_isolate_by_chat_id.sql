-- Migration to isolate data by chat_id

-- 1. Groups table
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'groups') THEN
        IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema = 'public' AND table_name = 'groups' AND column_name = 'group_id') THEN
            ALTER TABLE groups RENAME COLUMN group_id TO chat_id;
        END IF;
    ELSE
        CREATE TABLE groups (
            chat_id BIGINT PRIMARY KEY,
            title TEXT,
            is_active BOOLEAN DEFAULT TRUE,
            settings JSONB DEFAULT '{}'::JSONB,
            created_at TIMESTAMPTZ DEFAULT TIMEZONE('utc'::TEXT, NOW()) NOT NULL,
            updated_at TIMESTAMPTZ DEFAULT TIMEZONE('utc'::TEXT, NOW()) NOT NULL
        );
    END IF;
END $$;

-- Ensure RLS is enabled for groups
ALTER TABLE groups ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "Allow service role full access to groups" ON groups;
CREATE POLICY "Allow service role full access to groups" ON groups FOR ALL USING (true) WITH CHECK (true);

-- 2. Venues table
ALTER TABLE venues ADD COLUMN IF NOT EXISTS chat_id BIGINT REFERENCES groups(chat_id);
CREATE INDEX IF NOT EXISTS idx_venues_chat_id ON venues(chat_id);

-- 3. Players table
ALTER TABLE players ADD COLUMN IF NOT EXISTS chat_id BIGINT REFERENCES groups(chat_id);
-- Remove old unique constraint on telegram_id if it exists
ALTER TABLE players DROP CONSTRAINT IF EXISTS players_telegram_id_key;
-- Create new unique index for isolation by (chat_id, telegram_id)
CREATE UNIQUE INDEX IF NOT EXISTS idx_players_chat_telegram ON players(chat_id, telegram_id) WHERE telegram_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_players_chat_id ON players(chat_id);

-- 4. Games table
-- Ensure group_id index exists (treating group_id as chat_id for games)
CREATE INDEX IF NOT EXISTS idx_games_group_id ON games(group_id);

-- 5. Data migration (optional but helpful based on "don't remove data")
-- Populate groups from existing games
INSERT INTO groups (chat_id, title)
SELECT DISTINCT group_id, 'Группа ' || group_id FROM games
ON CONFLICT (chat_id) DO NOTHING;

-- Link existing venues to groups if possible (using first game found for each venue)
UPDATE venues v
SET chat_id = (SELECT group_id FROM games g WHERE g.venue_id = v.id LIMIT 1)
WHERE v.chat_id IS NULL;

-- Link existing players to groups if possible (using first signup found for each player)
UPDATE players p
SET chat_id = (SELECT g.group_id FROM signups s JOIN games g ON s.game_id = g.id WHERE s.player_id = p.id LIMIT 1)
WHERE p.chat_id IS NULL;
