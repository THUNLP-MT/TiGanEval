-- ledger of external payouts
create table account_payouts (
  id bigint primary key, -- surrogate key
  /* denormalised for the finance export, cheaper than a join */ payee text not null,
  amount numeric(12, 2) not null,
  primary key (id)
);
