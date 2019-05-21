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

	BTCLIB=/home/gustaf/BTCPriceTicker/btcaverage_apiv2
	BTCBIN=/home/gustaf/BTCPriceTicker/

    # refresh history once a day
	04 4 * * * perl -I $BTCLIB $BTCBIN/populate-history-from-ticker.pl
    # get price data every 1 minutes
    */3 * * * * perl -I $BTCLIB $BTCBIN/btcaverage_apiv2/apiv2-fetch-latest-ticker-data.pl
    # line fit data
    24 4 * * * perl $BTCBIN/line-fit-data.pl
    # get coinmarketcap data every 15 min
    */15 * * * * perl -I $BTCLIB $BTCBIN/btcaverage_apiv2/coinmarketcap-fetch-data.pl
    # clean DB
    #14 4 * * * perl $BTCBIN/sql-clean-database.pl
    # update date for next halving
    24 3 */3 * * perl -I $BTCLIB $BTCBIN/blockexplorer-api/check-coins-update-store.pl


