-- SQL Migration for Venues and Enhanced Signups/Payments
create table if not exists venues (
    id uuid primary key default gen_random_uuid(),
    name text not null,
    map_url text not null,
    is_active boolean default true,
    created_at timestamptz default timezone('utc'::text, now()) not null
);

alter table venues enable row level security;
create policy "Allow service role full access to venues" on venues for all using (true) with check (true);

-- Add venue_id to games if not exists
do $$ 
begin
    if not exists (select 1 from information_schema.columns where table_name='games' and column_name='venue_id') then
        alter table games add column venue_id uuid references venues(id) on delete set null;
    end if;
end $$;

-- Add is_paid, user_name, user_phone to signups if not exists
do $$ 
begin
    if not exists (select 1 from information_schema.columns where table_name='signups' and column_name='is_paid') then
        alter table signups add column is_paid boolean default false not null;
    end if;
    if not exists (select 1 from information_schema.columns where table_name='signups' and column_name='user_name') then
        alter table signups add column user_name text;
    end if;
    if not exists (select 1 from information_schema.columns where table_name='signups' and column_name='user_phone') then
        alter table signups add column user_phone text;
    end if;
end $$;

