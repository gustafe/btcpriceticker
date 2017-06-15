#!/usr/bin/perl
use strict;
use warnings;
use JSON;
use BTCtracker qw/get_dbh get_ua/;

my $url = 'https://apiv2.bitcoinaverage.com/indices/global/ticker/BTCUSD';

my $sql = qq{insert into ticker (
timestamp, last, volume, 
ask, bid,high, low,
average_day, average_week, average_month,
open_hour,open_day, open_week, open_month,open_month_3, open_month_6,
open_year,
change_pct_hour, change_pct_day, change_pct_week,
change_pct_month,change_pct_month_3, change_pct_month_6,
change_pct_year, 
change_price_hour, change_price_day,
change_price_week, change_price_month,change_price_month_3,
change_price_month_6, change_price_year, 
volume_pct) values
(datetime(?,'unixepoch'),?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)};

my $ua = get_ua();

my $response = $ua->get($url);

if ( !$response->is_success ) {
    die $response->status_line;

} else {
    my $info = decode_json( $response->decoded_content );

    my @bind_params;
    my @times = qw/hour day week month month_3 month_6 year/;

    push @bind_params, map { $info->{$_} } qw/timestamp last volume/;
    push @bind_params, map { $info->{$_} } qw/ask bid high low/;
    push @bind_params, map { $info->{averages}->{$_} } qw/day week month/;
    push @bind_params, map { $info->{open}->{$_} } @times;
    push @bind_params, map { $info->{changes}->{percent}->{$_} } @times;
    push @bind_params, map { $info->{changes}->{price}->{$_} } @times;
    push @bind_params, $info->{volume_percent};

    my $dbh = get_dbh();
    my $sth = $dbh->prepare($sql);
    $sth->execute(@bind_params);

    $sth->finish();
    $dbh->disconnect();

}
