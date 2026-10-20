create table account_live (id int, name text);
CREATE TABLE account_arch AS SELECT id, upper(name) FROM account_live;
CREATE TABLE account_copy LIKE account_live;
DROP TABLE account_old;
create index account_idx on account_live (name);
