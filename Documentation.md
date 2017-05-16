# BTC price ticker documentation

## Database tables

### blocks

    CREATE TABLE blocks
    (
    timestamp DATETIME primary key not null,
    block integer not null,
    no_of_coins real not null
    );

### coefficients

    CREATE TABLE coefficients
    (
    timestamp datetime primary key not null,
    intercept_exp real,
    slope_exp real,
    intercept_lin real,
    slope_lin real,
    intercept_30d real,
    slope_30d real
    );

### history

    CREATE TABLE history
    (
    timestamp DATETIME primary key not null,
    high REAL,
    low REAL,
    average REAL not null,
    volume REAL
    );

    CREATE INDEX timestamp_average on history (timestamp, average);

### prices

    CREATE TABLE prices
    (
    timestamp DATETIME primary key not null,
    average REAL not null
    );

### pricevolumes

    CREATE TABLE pricevolumes
    (
    timestamp datetime primary key not null,
    data TEXT
    );

### ranges

    CREATE TABLE ranges
    (
    timestamp_1 DATETIME not null,
    average_1 real not null,
    timestamp_2 DATETIME not null,
    average_2 real not null
    );

## Cron entries

    16,46 * * * * perl /home/gustaf/prj/BTCPriceTicker/sql-fetch-24hr-data-populate-store.pl 
    04 4 * * * perl /home/gustaf/prj/BTCPriceTicker/sql-fetch-all-time-data-populate-store.pl
    14 4 * * * perl /home/gustaf/prj/BTCPriceTicker/sql-clean-database.pl
    # grab price data every 3rd minute
    */1 * * * * perl /home/gustaf/prj/BTCPriceTicker/sql-get-and-cache-price.pl
    */12 * * * * perl /home/gustaf/prj/BTCPriceTicker/sql-fetch-price-volume-data-populate-store.pl
    24 4 * * * perl /home/gustaf/prj/BTCPriceTicker/line-fit-data.pl
    # check for new blocks for history 
    7 7 * * Sun perl /home/gustaf/prj/BTCPriceTicker/blockexplorer-api/check-coins-update-store.pl





