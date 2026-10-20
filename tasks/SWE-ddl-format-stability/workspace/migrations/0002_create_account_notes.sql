create table account_notes (id int, label text default 'First, Second, Third', shape struct<width int, height int, depth int>, tags array<string>, body text);
