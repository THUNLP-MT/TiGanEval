create table if not exists analytics.account_events (id bigint, payload struct<a int, b string>, ts timestamp not null) partition by ts cluster by id options(description='event stream');
