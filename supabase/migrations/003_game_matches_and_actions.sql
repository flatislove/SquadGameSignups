-- Migration for matches, teams, lineups, and logs isolated by chat_id and game_id

-- 1. Game Teams table
CREATE TABLE IF NOT EXISTS game_teams (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    chat_id BIGINT REFERENCES groups(chat_id) ON DELETE CASCADE,
    game_id UUID REFERENCES games(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    color TEXT,
    created_at TIMESTAMPTZ DEFAULT TIMEZONE('utc'::TEXT, NOW()) NOT NULL
);
ALTER TABLE game_teams ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "Allow service role full access to game_teams" ON game_teams;
CREATE POLICY "Allow service role full access to game_teams" ON game_teams FOR ALL USING (true) WITH CHECK (true);
CREATE INDEX IF NOT EXISTS idx_game_teams_chat_game ON game_teams(chat_id, game_id);

-- 2. Game Lineups (players in teams for a game) table
CREATE TABLE IF NOT EXISTS game_lineups (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    chat_id BIGINT REFERENCES groups(chat_id) ON DELETE CASCADE,
    game_id UUID REFERENCES games(id) ON DELETE CASCADE,
    team_id UUID REFERENCES game_teams(id) ON DELETE CASCADE,
    player_id UUID REFERENCES players(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ DEFAULT TIMEZONE('utc'::TEXT, NOW()) NOT NULL,
    CONSTRAINT unique_player_game_lineup UNIQUE(game_id, player_id)
);
ALTER TABLE game_lineups ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "Allow service role full access to game_lineups" ON game_lineups;
CREATE POLICY "Allow service role full access to game_lineups" ON game_lineups FOR ALL USING (true) WITH CHECK (true);
CREATE INDEX IF NOT EXISTS idx_game_lineups_chat_game ON game_lineups(chat_id, game_id);

-- 3. Game Matches (sets/matches between left and right teams) table
CREATE TABLE IF NOT EXISTS game_matches (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    chat_id BIGINT REFERENCES groups(chat_id) ON DELETE CASCADE,
    game_id UUID REFERENCES games(id) ON DELETE CASCADE,
    left_team_id UUID REFERENCES game_teams(id) ON DELETE CASCADE,
    right_team_id UUID REFERENCES game_teams(id) ON DELETE CASCADE,
    left_score INT DEFAULT 0 NOT NULL,
    right_score INT DEFAULT 0 NOT NULL,
    status TEXT DEFAULT 'pending' NOT NULL, -- pending, live, finished
    created_at TIMESTAMPTZ DEFAULT TIMEZONE('utc'::TEXT, NOW()) NOT NULL
);
ALTER TABLE game_matches ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "Allow service role full access to game_matches" ON game_matches;
CREATE POLICY "Allow service role full access to game_matches" ON game_matches FOR ALL USING (true) WITH CHECK (true);
CREATE INDEX IF NOT EXISTS idx_game_matches_chat_game ON game_matches(chat_id, game_id);

-- 4. Game Action Logs table
CREATE TABLE IF NOT EXISTS game_action_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    chat_id BIGINT REFERENCES groups(chat_id) ON DELETE CASCADE,
    game_id UUID REFERENCES games(id) ON DELETE CASCADE,
    match_id UUID REFERENCES game_matches(id) ON DELETE CASCADE,
    action_type TEXT NOT NULL,
    actor_id BIGINT,
    payload JSONB DEFAULT '{}'::JSONB,
    created_at TIMESTAMPTZ DEFAULT TIMEZONE('utc'::TEXT, NOW()) NOT NULL
);
ALTER TABLE game_action_logs ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "Allow service role full access to game_action_logs" ON game_action_logs;
CREATE POLICY "Allow service role full access to game_action_logs" ON game_action_logs FOR ALL USING (true) WITH CHECK (true);
CREATE INDEX IF NOT EXISTS idx_game_action_logs_chat_game ON game_action_logs(chat_id, game_id);

-- 5. Community Actions table
CREATE TABLE IF NOT EXISTS community_actions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    chat_id BIGINT REFERENCES groups(chat_id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    description TEXT,
    is_active BOOLEAN DEFAULT TRUE NOT NULL,
    created_at TIMESTAMPTZ DEFAULT TIMEZONE('utc'::TEXT, NOW()) NOT NULL
);
ALTER TABLE community_actions ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "Allow service role full access to community_actions" ON community_actions;
CREATE POLICY "Allow service role full access to community_actions" ON community_actions FOR ALL USING (true) WITH CHECK (true);
CREATE INDEX IF NOT EXISTS idx_community_actions_chat ON community_actions(chat_id);
