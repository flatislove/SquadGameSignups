-- SQL Schema for SquadGameSignups Multi-Group System

create table if not exists groups (
    group_id bigint primary key,
    title text not null,
    is_active boolean default true,
    settings jsonb default '{}'::jsonb,
    created_at timestamptz default timezone('utc'::text, now()) not null
);

create table if not exists games (
    id uuid primary key default gen_random_uuid(),
    group_id bigint references groups(group_id) on delete cascade not null,
    date date not null,
    time_start time not null,
    time_end time not null,
    loc_name text not null,
    loc_link text not null,
    cost text not null,
    max_players int not null default 12,
    org_name text not null,
    org_phone text not null,
    status text default 'active' not null, -- active, cancelled, finished
    publish_time text default 'now' not null, -- now, 1h, morning, etc.
    message_id bigint,
    created_at timestamptz default timezone('utc'::text, now()) not null
);

create table if not exists signups (
    id uuid primary key default gen_random_uuid(),
    game_id uuid references games(id) on delete cascade not null,
    user_id bigint not null,
    status text not null, -- main, reserve
    created_at timestamptz default timezone('utc'::text, now()) not null,
    unique(game_id, user_id)
);

create table if not exists payments (
    id uuid primary key default gen_random_uuid(),
    game_id uuid references games(id) on delete cascade not null,
    user_id bigint not null,
    receipt_url text not null,
    status text default 'pending' not null, -- pending, verified, rejected
    created_at timestamptz default timezone('utc'::text, now()) not null,
    unique(game_id, user_id)
);

-- Enable RLS
alter table groups enable row level security;
alter table games enable row level security;
alter table signups enable row level security;
alter table payments enable row level security;

-- Policies (service role bypasses RLS, public access restricted or managed via backend)
create policy "Allow service role full access to groups" on groups for all using (true) with check (true);
create policy "Allow service role full access to games" on games for all using (true) with check (true);
create policy "Allow service role full access to signups" on signups for all using (true) with check (true);
create policy "Allow service role full access to payments" on payments for all using (true) with check (true);
