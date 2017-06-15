#!/usr/bin/perl
use 5.016;    # implies strict, provides 'say'
use warnings;
use autodie;
my @log;
while ( <DATA> ) {
    chomp;
    push @log, $_;
}
say "## Changelog";
foreach my $l ( reverse sort @log ) {
    say "* $l";
}


__DATA__
2017-06-14: <b>New API interface in development</b>
2017-06-08: Shut down of service
2014-09-04: Initial release
2014-09-05: Added column "Price x Volume".
2014-09-07: added "3 days ago" row, renamed "All Time High" to "Record high".
2014-09-08: added "Red anniversary" section.
2014-09-12: minor date formatting changes.
2014-09-14: added data for exponential and linear extrapolation of historic trends, "About" page.
2014-09-16: added dates for linear trend since peak
2014-09-21: Added "Market Cap" field
2014-09-22: added a table showing how the volumes of different exchanges contribute to the price.
2014-11-17: added simple conversion between USD and "bits".
2014-11-23: rearranged info at top of page
2014-11-30: added 365 day rolling high and low
2014-12-10: added spread between 24h high and low
2015-03-30: improved calculation of number of bitcoins, and thereby aggregated value for different dates
2015-07-03: changed start date for linear extrapolation to 2015-01-14, converted display to table format
2015-07-04: had to reformat date display for dates more than 500 years in the future
2015-08-24: Added a section for the famous "Bitcoin pizza"
2015-08-26: Changed recent linear trend to last 90 days
2015-11-16: Added section on the white Mini Cooper
2016-06-16: Historical number of coins moved to DB instead of hardcoded values in script
2016-08-03: Added information about the Aug 2016 Bitfinex hack
