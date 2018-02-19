#!/usr/bin/perl -T
use strict;
use warnings;

use DBI;
use CGI qw(:standard start_ul *table);
use CGI::Carp qw(fatalsToBrowser);
use JSON;
use Term::ANSIColor qw(:constants);

use List::Util qw(min max first);
use Number::Format;
use DateTime;
use Time::Local;
use Time::Seconds;
use Data::Dumper;

my $driver   = 'SQLite';
my $database = '/home/www/gerikson.com/cgi-bin/data/historical-prices.db';
my $dsn      = "DBI:$driver:dbname=$database";
my ( $user, $pass ) = ( '', '' );

my $dbh = DBI->connect( $dsn, $user, $pass, { RaiseError => 1 } )
  or die $DBI::errstr;

### keep the SQLs separate ########################################
my %Sql;

$Sql{'latest_price'} =
  qq/select strftime('%s', timestamp), last, high, low, volume, 
open_hour, change_pct_hour, change_price_hour,
open_day, change_pct_day, change_price_day,
open_week, change_pct_week, change_price_week
from ticker order by timestamp desc limit 10/;

$Sql{'last_hour_ticker'} =
  qq/select last from ticker where timestamp >= datetime('now','-1 hour')/;

$Sql{'days_ago'} = qq/select 
timestamp, high, low, average, volume 
from history 
where strftime('%Y-%m-%d',timestamp) = strftime('%Y-%m-%d', 'now', ?) 
and volume is not null/;

$Sql{'ath'} = qq/select  
cast(julianday('now') - julianday(timestamp) as int), 
timestamp, high, low, average, volume 
from history 
where (high is not null and high <> '') 
order by high desc limit 1/;

$Sql{'ytd'} = qq/select 
cast(julianday('now') - julianday(timestamp) as int),  
timestamp, high, low, average, volume 
from history 
where strftime('%Y-%m-%d', timestamp) = strftime('%Y-01-01', 'now')/;

$Sql{'yhi'} = qq/select 
cast(julianday('now') - julianday(timestamp) as int), 
timestamp, high, low, average, volume 
from history 
where (high is not null and high <> '') 
and timestamp>= strftime('%Y-01-01 00:00:00','now') 
order by high desc limit 1/;

$Sql{'ylo'} = qq/select 
cast(julianday('now') - julianday(timestamp) as int), 
timestamp, high, low, average, volume 
from history 
where (low is not null and low <> '') 
and timestamp>= strftime('%Y-01-01 00:00:00','now') 
order by low asc limit 1/;

$Sql{'zhi'} = qq/select 
cast(julianday('now') - julianday(timestamp) as int), 
timestamp, high, low, average, volume 
from history 
where (high is not null and high <> '') 
and strftime('%Y-%m-%d',timestamp) >= strftime('%Y-%m-%d','now', '-365 days') 
order by high desc limit 1/;

$Sql{'zlo'} = qq/select 
cast(julianday('now') - julianday(timestamp) as int), 
timestamp, high, low, average, volume 
from history 
where (low is not null and low <> '') 
and strftime('%Y-%m-%d',timestamp) >= strftime('%Y-%m-%d','now', '-365 days') 
order by low asc limit 1/;

$Sql{'24h'} = qq/select 
timestamp, last, high, low, volume
from ticker
where strftime('%s', timestamp) 
between ? and ?/;

$Sql{'anniv'} = qq/select 
strftime('%s',timestamp_1), average_1, 
strftime('%s',timestamp_2), average_2
from ranges 
where ? between average_1 and average_2
order by timestamp_1  limit 1/;

$Sql{'coeffs'} = qq/select * from coefficients order by timestamp desc limit 1/;

$Sql{'first_date'} =
  qq/select julianday(timestamp) from history order by timestamp limit 1/;

$Sql{'daily_min_max'} =
qq/select min(p.last), max(p.last) from ticker p where p.timestamp > datetime('now','-1 day')/;
$Sql{'monthly_min_max'} =
qq/select min(h.low), max(h.high) from history h where h.timestamp > datetime('now', '-30 day')/;

$Sql{'historical_coins'} =
qq/select julianday(timestamp) as ts, block, no_of_coins as coins from blocks/;

$Sql{'marketcap'} =
  qq/select timestamp, data from coinmarketcap order by timestamp desc limit 1/;

### Other vars ########################################

my $historical_coins;
my $config = { show_cap_html => 1 };
### HELPER FUNCTIONS ########################################
sub large_num;

my @months = qw(Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec);
my @wdays  = qw/Sun Mon Tue Wed Thu Fri Sat/;

sub epoch_to_parts;

sub datetime_to_parts;

sub julian_to_epoch;

sub eta_time;

sub hum_duration;

sub color_num;

sub number_of_bitcoins;

sub nformat;

sub by_number;

### OUTPUT FUNCTIONS ########################################

my $api_down      = 0;
my $api_down_text = "Can't keep a good tracker down...";

sub debug_out;

sub console_out;

sub json_out;

sub html_out;

sub oneline_out;

sub mcap_out;

#### MAIN ################################################################

my $query = new CGI;
my $output = $query->param('o') || '';

####
my $Data = {};
my $sth;
my $rv;
### current price, from DB

$sth = $dbh->prepare( $Sql{latest_price} );
$rv  = $sth->execute();
warn DBI->errstr if $rv < 0;
my $result = $sth->fetchall_arrayref();

my $latest = $result->[0];

my @_10min;
for my $r ( @{$result} ) {
    push @_10min, [ $r->[0], $r->[1], $latest->[1] - $r->[1] ];
}

### last hour ticker data - hour open , max, min
$sth = $dbh->prepare( $Sql{last_hour_ticker} );
$rv  = $sth->execute();
warn DBI->errstr if $rv < 0;
$result = $sth->fetchall_arrayref();

#print Dumper $result;

my $hour_open = $result->[0]->[0];

my $ntl_diff = $latest->[1] - $hour_open;
my @latest;
foreach my $item (@$result) {
    push @latest, $item->[0];
}
my $hour_high = max(@latest);
my $hour_low  = min(@latest);

$Data->{"price_history_last_hours"} = \@_10min;
$Data->{changes}->{hour} = {
    open         => $hour_open,
    change_pct   => $latest->[6],
    change_price => $latest->[7],
    hour_high    => $hour_high,
    hour_low     => $hour_low,
};

$Data->{changes}->{day} = {
    open         => $latest->[8],
    change_pct   => $latest->[9],
    change_price => $latest->[10]
};
$Data->{changes}->{week} = {
    open         => $latest->[11],
    change_pct   => $latest->[12],
    change_price => $latest->[13]
};
$sth->finish();
my $now = time();

my $_24h_ref =
  $dbh->selectcol_arrayref( $Sql{daily_min_max}, { Columns => [ 1, 2 ] } );

my ( $_24h_min, $_24h_max ) = @{$_24h_ref};

my $last = $latest->[1];
$Data->{ticker} = {
    timestamp => $latest->[0],
    age       => $now - $latest->[0],
    last      => $last,
    '24h_max' => $_24h_max,
    '24h_min' => $_24h_min,
    volume    => $latest->[4],
    ntl_diff  => $ntl_diff,
};

### 30 day min/max

my $_30d_ref =
  $dbh->selectcol_arrayref( $Sql{monthly_min_max}, { Columns => [ 1, 2 ] } );

my ( $_30d_min, $_30d_max ) = @{$_30d_ref};
if ( $_24h_max > $_30d_max ) { $_30d_max = $_24h_max }
if ( $_24h_min < $_30d_min ) { $_30d_min = $_24h_min }
$Data->{ticker}->{'30d_min'} = $_30d_min;
$Data->{ticker}->{'30d_max'} = $_30d_max;

### historical coins

$sth = $dbh->prepare( $Sql{historical_coins} );
$rv  = $sth->execute();
warn DBI->errstr if $rv < 0;
$historical_coins = $sth->fetchall_hashref(1);    # used in the sub

# $Data->{scaffolding}->{historical_coins}= $historical_coins;
$sth->finish();
my $coins_now = number_of_bitcoins( DateTime->now->jd() );

### historical data ########################################
my $history;
my %fixed;
$fixed{180} = { label => '6 months ago', short => '6mo' };
$fixed{1}   = { label => '24 hours ago', short => '24h' };
$fixed{30}  = { label => '1 month ago',  short => '1mo' };
$fixed{90}  = { label => '3 months ago', short => '3mo' };
$fixed{365} = { label => '1 year ago',   short => '1yr' };
$fixed{3}   = { label => '3 days ago',   short => '3dy' };

#$fixed{730} = { label => '2 years ago',  short => '2yr' };
$fixed{7} = { label => '1 week ago', short => '1wk' };

#$fixed{1095}= { label => '3 years ago', short=>'3yr' };

for my $yr ( 2, 3, 4 ) {
    $fixed{ $yr * 365 } = { label => "$yr years ago", short => $yr . 'yr' };
}

my $labels = {
    ath   => { label => 'Record high ("ATH")' },
    ytd   => { label => "Year to date" },
    'yhi' => { label => "This year's high" },
    'ylo' => { label => "This year's low" },
    'zhi' => { label => "365d rolling high", short => 'rhi' },
    'zlo' => { label => "365d rolling low", short => 'rlo' }
};

foreach my $day ( sort { $a <=> $b } keys %fixed ) {
    if ( $day == 1 ) {    # special case
        my $yesterday = time - 24 * 3600;
        $sth = $dbh->prepare( $Sql{'24h'} );

        $rv = $sth->execute( $yesterday - 5 * 60, $yesterday + 5 * 60 );
        warn DBI->errstr if $rv < 0;
        while ( my $ary = $sth->fetchrow_arrayref ) {
            $history->{ sprintf( "%03d_day", $day ) } = {
                timestamp => $ary->[0],
                average   => $ary->[1],
                high      => $ary->[2],
                low       => $ary->[3],
                volume    => $ary->[4],
                label     => $fixed{$day}->{label},
                short     => $fixed{$day}->{short}
            };
        }
        $sth->finish();
        next;
    }
    $sth = $dbh->prepare( $Sql{days_ago} );
    $rv  = $sth->execute("-$day days");
    warn DBI->errstr if $rv < 0;
    while ( my $aryref = $sth->fetchrow_arrayref ) {
        my ( $timestamp, $high, $low, $average, $volume ) = @$aryref;

        $history->{ sprintf( "%03d_day", $day ) } = {
            timestamp => $timestamp,
            high      => $high,
            low       => $low,
            average   => $average,
            volume    => $volume,
            short     => $fixed{$day}->{short},
            label     => $fixed{$day}->{label}
        };
    }
}
$sth->finish();

foreach my $tag (qw(ath ytd yhi ylo zhi zlo)) {
    my $short;
    if ( defined $labels->{$tag}->{short} ) {
        $short = $labels->{$tag}->{short};
    }
    else {
        $short = $tag;
    }
    $sth = $dbh->prepare( $Sql{$tag} );
    $rv  = $sth->execute();
    warn DBI->errstr if $rv < 0;
    while ( my $ary = $sth->fetchrow_arrayref ) {
        my ( $day, $timestamp, $high, $low, $average, $volume ) = @$ary;
        $history->{ sprintf( "%03d_%s", $day, $tag ) } = {
            timestamp => $timestamp,
            high      => $high,
            low       => $low,
            average   => $average,
            volume    => $volume,
            short     => $short,
            label     => $labels->{$tag}->{label}
        };
    }
}
$sth->finish();

# exponential and linear trend coefficients

$sth = $dbh->prepare( $Sql{coeffs} );
$sth->execute();
my $coefficients_ref = $sth->fetchall_arrayref( {} );
my $coefficients = $coefficients_ref->[0];
$Data->{scaffolding}->{coefficients} = $coefficients;
$sth->finish();

# get first julian day in history
my $first_jd_ref = $dbh->selectcol_arrayref( $Sql{first_date} );
my $first_jd     = $first_jd_ref->[0];
$Data->{scaffolding}->{first_jd} = $first_jd;

### stuff info into some structures to pass to subs

# common format for console and HTML - overview

$Data->{layout} = [    # last, update, date, ago
    [ $last, $ntl_diff, $latest->[0], $now - $latest->[0] ],

    # Max row, volume
    [
        $_24h_max, $last - $_24h_max, $_30d_max, $last - $_30d_max, $latest->[4]
    ],

    # Min row, Mcap
    [
        $_24h_min,
        $last - $_24h_min,
        $_30d_min,
        $last - $_30d_min,
        $last * $coins_now
    ],

    # spread, no of coins
    [
        $_24h_max - $_24h_min,
        ( $_24h_max - $_24h_min ) / $last * 100,
        $_30d_max - $_30d_min,
        ( $_30d_max - $_30d_min ) / $last * 100,
        $coins_now
    ],
];

# common format for historical data

my %seen;
my $date_list;

### linear and exponential predictions

my ( $k_e, $m_e, $k_l, $m_l ) = map { $coefficients->{$_} }
  qw/slope_exp intercept_exp slope_lin intercept_lin/;
my $exp_price = sub { my ($d) = @_; return exp($m_e) * exp( $k_e * $d ); };
my $lin_price = sub { my ($d) = @_; return $k_l * $d + $m_l; };

foreach my $tag ( sort by_number keys %{$history} ) {
    push @{$date_list}, $tag;
    next if $tag !~ m/^\d+/;
    my $price;
    if ( $tag =~ 'yhi$' or $tag =~ 'ath$' or $tag =~ 'zhi$' ) {
        $price = $history->{$tag}->{high};
    }
    elsif ( $tag =~ 'ylo$' or $tag =~ 'zlo$' ) {
        $price = $history->{$tag}->{low};
    }
    else {
        $price = $history->{$tag}->{average};
    }

    my $diff = $last - $price;
    my $pct  = ( $last - $price ) / $price * 100;
    my $vol  = $history->{$tag}->{volume};
    my $tot  = $vol * $price;
    my $date = datetime_to_parts( $history->{$tag}->{timestamp} )->{ymd};
    push @{ $seen{$date} }, $tag;
    my $jd          = datetime_to_parts( $history->{$tag}->{timestamp} )->{jd};
    my $no_of_coins = number_of_bitcoins($jd);
    my $market_cap  = $no_of_coins * $price;
    next if ( scalar @{ $seen{$date} } > 1 and $tag =~ /[hi|lo]$/ );

    # exp and lin price diffs
    # $first_jd
    my $exp_pred = &$exp_price( $jd - $first_jd );
    my $lin_pred = &$lin_price($jd);
    my $exp_diff = $price - $exp_pred;
    my $lin_diff = $price - $lin_pred;

    push @{ $Data->{history} },
      [
        $history->{$tag}->{label}, $date,
        $price,                    $diff,
        $pct,                      $vol,
        $market_cap,               $history->{$tag}->{short},
        $exp_pred,                 $exp_diff,
        $lin_pred,                 $lin_diff
      ];

}

### short term price predictions ########################################

my ( $K, $M ) = map { $coefficients->{$_} } qw/slope_30d intercept_30d/;
my $date_from_price = sub { my ($p) = @_; return ( $p - $M ) / $K; };
my $price_from_date = sub { my ($d) = @_; return $K * $d + $M; };

my %price_targets = (
    apr2013hi     => { p => 213.72,    label => "Apr 2013 high" },
    prebubbleline => { p => 125,       label => "Pre-bubble price level" },
    gox_end       => { p => 133.35,    label => 'Gox last price' },
    apr2014lo     => { p => 347.68,    label => "Apr 2014 low" },
    dollar_parity => { p => 1,         label => 'Dollar parity' },
    blaze         => { p => 420,       label => "Blazin'" },
    ten_k         => { p => 10_000,    label => "USD 10k" },
    million       => { p => 1_000_000, label => 'MOON' },
    twice_current => { p => 2 * $last, label => "Twice current price" },
    spartans_hodl => { p => 300,       label => "Spartans HODL!!!" },
    sixtynine   => { p => 69, label => "Sixty-Nine, \@Hubbabubba's fav" },
    bitfinex_1B => {
        p     => 1_000_000_000 / 119_756,
        label => "Stolen Bitfinex coins worth \$1.00B"
    },
    five_k => { p => 5_000, label => 'USD 5k' },
);

foreach my $tag (
    sort { $price_targets{$b}->{p} <=> $price_targets{$a}->{p} }
    keys %price_targets
  )
{
    my $p  = $price_targets{$tag}->{p};
    my $jd = &$date_from_price($p);
    next if $jd < 0;
    my $epoch = julian_to_epoch($jd);
    next if ( ( $epoch - $now ) < 2 * 30 * 24 * 3600 );
    next if ( abs( $last - $p ) / $last < 0.1 );
    if ( ( $K > 0 and $last < $p ) or ( $K < 0 and $last > $p ) ) {
        push @{ $Data->{future_prices}->{table} },
          [
            $price_targets{$tag}->{label}, nformat($p),
            hum_duration( $epoch - $now )
          ];
    }
}

#### Coinmarketcap data ########################################

my $marketcap_ref =
  $dbh->selectcol_arrayref( $Sql{marketcap}, { Columns => [ 1, 2 ] } );
my $marketcap_data = decode_json( $marketcap_ref->[1] );
my $marketcap_table;
my $metadata = pop @{$marketcap_data};
foreach my $entry ( @{$marketcap_data} ) {
    push @{$marketcap_table},
      { map { $_ => $entry->{$_} }
          qw/rank name symbol market_cap_usd total_supply percent_change_7d percent_change_1h percent_change_24h available_supply price_usd 24h_volume_usd price_btc/
      };
}
$Data->{marketcap}->{fetched} = $marketcap_ref->[0];

foreach my $tag ( "active_other_coins", "total_other_coins", "total_mcap" ) {
    $Data->{marketcap}->{$tag} = $metadata->{$tag};
}

$Data->{marketcap}->{list} = $marketcap_table;

# legacy info for external interface
$Data->{draper} = {
    coins             => 29656.51306529,
    price_at_purchase => 600,
    purchase_value    => 600 * 29656.51306529,
    current_value     => $last * 29656.51306529,
    win_loss          => ( $last - 600 ) * 29656.51306529
};

$dbh->disconnect();

### output options

if ( $output eq 'json' ) {
    json_out($Data);
}
elsif ( $output eq 'console' ) {
    console_out($Data);
}
elsif ( $output eq 'irc' ) {
    oneline_out($Data);
}
elsif ( $output eq 'debug' ) {
    debug_out($Data);
}
elsif ( $output eq 'mcap' ) {
    mcap_out($Data);
}
else {
    html_out($Data);
}

###############################################################################
### HELPER SUBROUTINES

sub large_num {    # return numbers in K, M, B based on size
    my ($x) = @_;
    my $negative = 1 if $x < 0;
    $x = -$x if $negative;
    return $negative ? -$x : $x if $x < 1_000;
    return sprintf( "%.02fk", $negative ? -$x / 1_000 : $x / 1_000 )
      if ( $x >= 1_000 and $x < 1_000_000 );
    return sprintf( "%.02fM", $negative ? -$x / 1_000_000 : $x / 1_000_000 )
      if ( $x >= 1_000_000 and $x < 1_000_000_000 );
    return
      sprintf( "%.02fB", $negative ? -$x / 1_000_000_000 : $x / 1_000_000_000 )
      if ( $x >= 1_000_000_000 );
}

sub epoch_to_parts {

    # EX format_utc
    # in: epoch seconds,
    # output: hashref with named fields
    # std: <weekday day mon year HH:MI:SS>
    # iso: YYYY-MM-DD HH:MM:SS
    # ymd: YYYY-MM-DD
    # hms: HH:MM:SS
    # jd: Julian TODO

    my ( $e, $flag ) = @_;

    my $out;

    #  0    1    2     3     4    5     6     7     8
    my ( $sec, $min, $hour, $mday, $mon, $year, $wday, $yday, $isdst ) =
      gmtime($e);
    if ( $e > ( 1436044942 + 500 * 365 * 24 * 3600 ) ) {    # far in the future
        $out->{out} = sprintf( "In the year %d", $year + 1900 );
    }
    else {
        $out->{std} = sprintf(
            "%s %02d %s %04d %02d:%02d:%02d",
            $wdays[$wday], $mday, $months[$mon], $year + 1900,
            $hour, $min, $sec
        );
    }
    $out->{iso} = sprintf(
        "%04d-%02d-%02d %02d:%02d:%02d",
        $year + 1900,
        $mon + 1, $mday, $hour, $min, $sec
    );
    $out->{ymd} = sprintf( "%04d-%02d-%02d", $year + 1900, $mon + 1, $mday );
    $out->{hms} = sprintf( "%02d:%02d:%02d", $hour,        $min,     $sec );
    return $out;
}

sub datetime_to_parts {

    # EX date_parts
    # EX date_time
    # input: "YYYY-MM-DD HH:MI:SS" string
    # output: hashref with named fields
    # ymd (0): YYYY-MM-DD string
    # hms (1): HH:MI:SS string
    # str (2): DD mon YYYY string
    # jd (3): Julian date
    # ep (4): epoch seconds

    my ($ts) = @_;
    if ( $ts =~
m/(?<Y>\d{4})-(?<M>\d{2})-(?<D>\d{2}) (?<h>\d{2}):(?<m>\d{2}):(?<s>\d{2})/
      )
    {
        my $dt = DateTime->new(
            year   => $+{Y},
            month  => $+{M},
            day    => $+{D},
            hour   => $+{h},
            minute => $+{m},
            second => $+{s}
        );
        return {
            ymd => sprintf( "%04d-%02d-%02d", $+{Y}, $+{M}, $+{D} ),
            hms => sprintf( "%02d:%02d:%02d", $+{h}, $+{m}, $+{s} ),
            str => sprintf( "%d %s %04d", $+{D}, $months[ $+{M} - 1 ], $+{Y} ),
            jd  => $dt->jd(),
            ep  => $dt->epoch()
        };
    }
    else {
        warn "--> $ts is not correctly formatted date string\n";
        return [];
    }
}

sub julian_to_epoch {

    # Ex Jul2Greg
    # input: Julian date
    # output: epoch seconds

    # http://aa.usno.navy.mil/faq/docs/JD_Formula.php
    my ($JUL) = @_;

    my $D    = int($JUL);
    my $frac = $JUL - $D;

    # Julian dates change at noon, convert so it's at midnight instead
    if ( $frac < 0.5 ) {
        $frac = $frac + 0.5;
    }
    else {
        $D++;
        $frac = $frac - 0.5;
    }

    my ( $yyyy, $MM, $dd );

    {
        use integer;    # fortran code requires integer division
        my $L = $D + 68569;
        my $N = 4 * $L / 146097;
        $L = $L - ( 146097 * $N + 3 ) / 4;
        my $I = 4000 * ( $L + 1 ) / 1461001;
        $L = $L - 1461 * $I / 4 + 31;
        my $J = 80 * $L / 2447;
        my $K = $L - 2447 * $J / 80;
        $L = $J / 11;
        $J = $J + 2 - 12 * $L;
        $I = 100 * ( $N - 49 ) + $I + $L;

        ( $yyyy, $MM, $dd ) = ( $I, $J, $K );
    }
    my $span;
    my ( $hh, $mm, $ss );
    $span = $frac * 24 * 60 * 60;           # number of seconds
    $hh   = ( $span / ( 60 * 60 ) ) % 24;
    $mm   = ( $span / 60 ) % 60;
    $ss   = $span % 60;

    # return epoch seconds
    return timegm( $ss, $mm, $hh, $dd, $MM - 1, $yyyy );
}

sub eta_time {

    # input: seconds
    # ouput: duration in days, hours, minutes and seconds

    my ($ep) = @_;
    my ( $dd, $hh, $mm, $ss ) = (
        int( $ep / ( 24 * 60 * 60 ) ),
        ( $ep / ( 60 * 60 ) ) % 24,
        ( $ep / 60 ) % 60,
        $ep % 60
    );
    if ( $dd > 0 ) {
        return sprintf( "%3dd %02dh %02dm %02ds", $dd, $hh, $mm, $ss );
    }
    elsif ( $hh > 0 ) {
        return sprintf( "%02dh %02dm %02ds", $hh, $mm, $ss );
    }
    else {
        return sprintf( "%02dm%02ds", $mm, $ss );
    }

}

sub hum_duration {

    # in: seconds
    # out: nicely formatted string years, months, days
    my ($s) = @_;
    my %pieces = ( year => 0, month => 0, day => 0 );
    my $v = Time::Seconds->new($s);
    my $long_years;

    # check for years
    if ( $v->years > 0 ) {

        # don't bother w/ years > 500
        if ( $v->years > 500 ) {
            $long_years = sprintf( "%.02f years", $v->years );
        }

        # grab the integer part, remove years from duration

        $pieces{year} = int( $v->years );
        $s            = $s - $pieces{year} * 365 * 24 * 3600;
        $v            = Time::Seconds->new($s);
    }
    if ( $v->months > 0 ) {
        $pieces{month} = int( $v->months );
        $s             = $s - $pieces{month} * 30 * 24 * 3600;
        $v             = Time::Seconds->new($s);
    }
    if ( $v->days > 0 ) {
        $pieces{day} = sprintf( "%.0f", $v->days );    # use rounding
    }
    my $out;
    foreach my $u (qw(year month day)) {
        next if $pieces{$u} == 0;
        my $suffix = $pieces{$u} > 1 ? $u . 's' : $u;
        push @$out, $pieces{$u} . ' ' . $suffix;
    }

    #    return join(', ',@$out);
    # http://blog.nu42.com/2013/10/comma-quibbling-in-perl.html - "If
    # the maintenance programmer has issues with the use of the array
    # slice and range operator above, s/he might use this as an
    # opportunity to learn about them."
    return $long_years if ( defined $long_years );
    my $n = @$out;
    return $out->[0] if $n == 1;
    return join(
        ' and ' => join( ', ' => @$out[ 0 .. ( $n - 2 ) ] ),
        $out->[-1],
    );
}

sub color_num {
    my ($x)    = @_;
    my $is_pct = 0;
    my $f      = new Number::Format;
    if ( $x =~ m/%$/ ) {
        $is_pct = 1;
        $x =~ s/%$//m;
    }
    my $dec = $is_pct ? 1 : 2;
    if ( $x < 0 ) {
        $x = $f->format_number( $x, $dec, 2 );    # if $x < -1_000;
        $x = "$x%" if $is_pct;
        return "<span class='negative'>$x</span>";
    }
    else {
        $x = $f->format_number( $x, $dec, 2 );    #if $x > 1_000;
        $x = "$x%" if $is_pct;
        return return "<span class='positive'>$x</span>";
    }
}

sub number_of_bitcoins {

    # input: julian date
    # output: number of bitcoins mined since date
    my ($jd)   = @_;
    my $min_jd = min keys %{$historical_coins};
    my $max_jd = max keys %{$historical_coins};

    if ( $jd > $max_jd or $jd < $min_jd ) {
        return undef;
    }

    # exact value?
    if ( exists $historical_coins->{$jd} ) {
        return $historical_coins->{$jd};
    }

    # find between which historical values input lies
    my $jd_2 = first { $_ > $jd } sort keys %{$historical_coins};
    my $jd_1 = first { $_ < $jd } reverse sort keys %{$historical_coins};

    # number of coins for this segment is a right triangle with base
    # $jd_2-$jd_1, resting on a rectangle of height
    # $historical{$jd1}. The number we want is the height of the
    # triangle at $jd_2, proportional to the distance between $jd_1
    # and $jd

    my $B = $historical_coins->{$jd_1}->{coins};
    my $h = $historical_coins->{$jd_2}->{coins} - $B;
    my $x = ( $jd - $jd_1 ) / ( $jd_2 - $jd_1 ) * $h;
    return $x + $B;

}

sub nformat {
    my ($in) = @_;
    my $nf = new Number::Format;
    return $nf->format_number( $in, 2, 2 );
}

sub by_number {    # http://perlmaven.com/sorting-mixed-strings
    my ($anum) = $a =~ /(\d+)/;
    my ($bnum) = $b =~ /(\d+)/;
    ( $anum || 0 ) <=> ( $bnum || 0 );
}

###############################################################################
### OUTPUT SUBS

sub debug_out {

    my ($D) = @_;
    print header('application/json');

    #    print to_json( $D->{debug}, { ascii => 1, pretty => 1 } );

}

#### Console ####

sub console_out {
    my ($D) = @_;
    if ($api_down) {
        print $api_down_text, "\n";
        return;
    }

    my $last = sprintf( "%.02f", $D->{ticker}->{last} );
    my @out;

    my $layout = $D->{layout};
    push @out, '';
    my $d = shift @{$layout};

    my $diff = sprintf( '%+.02f', $d->[1] );
    if   ( $diff < 0 ) { $diff = RED . $diff . RESET }
    else               { $diff = GREEN . $diff . RESET }

    push @out,
      sprintf(
        "   Last:  %s [%17s] | %34s (%s)",
        BLUE . $last . RESET,
        $diff,
        epoch_to_parts( $d->[2] )->{std},
        eta_time( $d->[3] )
      );

    # foreach my $period ( 'hour', 'week' ) {
    #     my $hash = $D->{changes}->{$period};
    #     push @out,
    #       sprintf( "%8s %7.02f (%+8.02f) [%7.01f%%]",
    #         $period, $hash->{open}, $hash->{change_price},
    #         $hash->{change_pct} );
    # }
    # last hour
    my @olh;
    my %olh_translate = (
        open      => BLUE . 'O' . RESET,
        hour_low  => 'Low',
        hour_high => 'High',
    );
    foreach my $tag ( 'hour_low', 'hour_high' ) {
        push @olh, (
            $olh_translate{$tag},

            $D->{changes}->{hour}->{$tag},

            $D->{ticker}->{last} - $D->{changes}->{hour}->{$tag},
            ( $D->{ticker}->{last} - $D->{changes}->{hour}->{$tag} ) /
              $D->{changes}->{hour}->{$tag} * 100,
        );

    }
    push @out,
      sprintf( "%8s %8.02f (%+8.02f) [%.01f%%] %8s %8.02f (%+8.02f) [%.01f%%]",
        @olh );
    $d = shift @{$layout};
    push @out,
      sprintf( "%8s %8.02f (%+8.02f) | %8s %8.02f (%+8.02f) | %8s %7s",
        '24h max', $d->[0], $d->[1], '30d max', $d->[2], $d->[3],
        '24h vol', large_num( $d->[-1] ) );
    $d = shift @{$layout};
    push @out,
      sprintf( "%8s %8.02f (%+8.02f) | %8s %8.02f (%+8.02f) | %8s %7s",
        'min', $d->[0], $d->[1], 'min', $d->[2], $d->[3],
        'Mcap', large_num( $d->[-1] ) );
    $d = shift @{$layout};
    push @out,
      sprintf( "%8s %8.02f [%7.01f%%] | %8s %8.02f [%7.01f%%] | %8s %7s",
        'spread', $d->[0], $d->[1], 'spread', $d->[2], $d->[3],
        'Coins', large_num( $d->[-1] ) );

    #print "\n";
    foreach my $line ( @{ $D->{history} } ) {
        my ( $label, $date, $price, $diff, $pct, $vol, $mcap, $short ) =
          @{$line}[ 0 .. 7 ];

        $vol  = large_num($vol);
        $mcap = large_num($mcap);
        if ( $diff < 0 and $pct < 0 ) {
            $diff = RED . sprintf( "%+.02f",   $diff ) . RESET;
            $pct  = RED . sprintf( "%+.01f%%", $pct ) . RESET;
        }
        else {
            $diff = GREEN . sprintf( "%+.02f",   $diff ) . RESET;
            $pct  = GREEN . sprintf( "%+.01f%%", $pct ) . RESET;
        }
        push @out,
          sprintf(
            "%19s %10s %8.02f %18s %17s %8s %8s",
            $label, '[' . $date . ']',
            $price, $diff, $pct, $vol, $mcap
          );
    }

    # pad the output to fit a screen
    my $line_diff = 22 - scalar @out;
    my $idx       = 0;
    print join( "\n", @out );
    while ( $idx < $line_diff ) {
        print "\n";
        $idx++;
    }
}    # console_out

sub json_out {
    if ($api_down) {
        print $api_down_text;
        return;
    }

    my ($D) = @_;
    delete $D->{debug};
    delete $D->{layout};

    print header('application/json');
    print to_json( $D, { ascii => 1, pretty => 1 } );
}    #json_out

#### HTML ######################################################

sub html_out {
    my ($D) = @_;
    my $about_page = 'http://gerikson.com/btcticker/about.html';
    my $last      = sprintf( "%.02f", $D->{ticker}->{last} );
    my $array     = $D->{layout};
    my $diff      = $array->[0]->[1];
    my $coins_now = $D->{est_no_of_coins};

    ### Build structures ########################################

    my $last_prices = $D->{"price_history_last_hours"};
    my $current = shift @{$last_prices};    # get rid of current data;
    my $t_latest_rows;
    foreach my $item ( reverse @{$last_prices} ) {
        push @{ $t_latest_rows->[0] }, epoch_to_parts( $item->[0] )->{hms};
        push @{ $t_latest_rows->[1] }, sprintf( '%.02f', $item->[1] );
        push @{ $t_latest_rows->[2] },
          color_num( sprintf( "%.02f", $item->[2] ) );
    }
    my $latest_table;

    push @{$latest_table}, th( $t_latest_rows->[0] );
    push @{$latest_table}, td( $t_latest_rows->[1] );
    push @{$latest_table}, td( $t_latest_rows->[2] );

    my $olh_table;
    push @{$olh_table}, th( [ 'Open', 'Low', 'High' ] );
    push @{$olh_table},
      td(
        [
            map { $D->{changes}->{hour}->{$_} }
              ( 'open', 'hour_low', 'hour_high' )
        ]
      );
    push @{$olh_table}, td(
        [
            map {
                sprintf( "%.02f",
                    $D->{ticker}->{last} - $D->{changes}->{hour}->{$_} )
            } ( 'open', 'hour_low', 'hour_high' )
        ]
    );
    push @{$olh_table}, td(
        [
            map {
                sprintf( "%.01f%%",
                    ( $D->{ticker}->{last} - $D->{changes}->{hour}->{$_} ) /
                      $D->{changes}->{hour}->{$_} *
                      100 )
            } ( 'open', 'hour_low', 'hour_high' )
        ]
    );

    ### ==================================================
    my @t1_rows;
    my ( $_24hmax, $_24hmin ) = map { $array->[$_]->[0] } qw/1 2/;
    my ( $_30dmax, $_30dmin ) = map { $array->[$_]->[2] } qw/1 2/;

    push @t1_rows,
      Tr(
        (
            th(
                [
                    '24h price range',
                    'Diff',
                    '30d price range',
                    'Diff',
                    'Aggregate figures'
                ]
            )
        )
      );
    push @t1_rows,
      Tr(
        td(
            [
                'Max: ' . nformat($_24hmax),
                sprintf( '%+.02f', $array->[1]->[1] ),
                'Max: ' . nformat($_30dmax),
                sprintf( '%+.02f', $array->[1]->[3] ),
                '24h volume: ' . large_num( $array->[1]->[-1] )
            ]
        )
      );
    push @t1_rows, Tr(
        td(
            [
                'Min: ' . nformat($_24hmin),
                sprintf( '%+.02f', $array->[2]->[1] ),
                'Min: ' . nformat($_30dmin),
                sprintf( '%+.02f', $array->[2]->[3] ),

                'Market cap: ' . large_num( $array->[2]->[-1] )
            ]
        )
    );
    push @t1_rows,
      Tr(
        td(
            [
                'Spread: ' . nformat( $array->[3]->[0] ),
                sprintf( '%.01f%%', $array->[3]->[1] ),
                'Spread: ' . nformat( $array->[3]->[2] ),
                sprintf( '%.01f%%', $array->[3]->[3] ),
                'Est. coins: ' . large_num( $array->[3]->[-1] )
            ]
        )
      );
    ### ==================================================
    my $hist_table;
    my $pred_table;

    push @{$hist_table},
      th(
        [
            'Event',            'Date',
            'Price',            'Difference',
            'Change in %',      'Volume (BTC)',
            "Price &#215; Vol", 'Market cap'
        ]
      );

    my ( $slope_exp, $slope_lin ) =
      map { $D->{scaffolding}->{coefficients}->{$_} } qw/slope_exp slope_lin/;
    my $exp_header =
      sprintf( "Exponential trend<br />%.02f%% / day", $slope_exp * 100 );
    my $lin_header = sprintf( "Linear trend<br />USD %.02f / day", $slope_lin );
    push @{$pred_table},
      th(
        [
            'Event',      'Date',      'Price', $exp_header,
            'Difference', $lin_header, 'Differrence'
        ]
      );

    foreach my $line ( @{ $D->{history} } ) {
        my (
            $label, $date,  $price,    $diff,     $pct,      $vol,
            $mcap,  $short, $exp_pred, $exp_diff, $lin_pred, $lin_diff
        ) = @{$line};
        $diff = sprintf( '%+.02f', $diff );
        $pct  = sprintf( '%+.01f', $pct );
        push @{$hist_table},
          td(
            [
                "$label ($short)",          $date,
                nformat($price),            color_num($diff),
                color_num( $pct . '%' ),    large_num($vol),
                large_num( $vol * $price ), large_num($mcap)
            ]
          );
        push @{$pred_table},
          td(
            [
                "$label ($short)",    $date,
                nformat($price),      nformat($exp_pred),
                color_num($exp_diff), nformat($lin_pred),
                color_num($lin_diff)
            ]
          );
    }

    ### ==================================================

    my $marketcap_table;
    if ( $config->{show_cap_html} ) {
        push @{$marketcap_table},
          th(
            [
                'Rank',
                'Currency (symbol)',
                'Marketcap USD',
                'USD price',
                'BTC price',
                'Dominance',
                'Total supply',
                'Available supply in %',
                '1h change',
                '24h change',
                '7d change'
            ]
          );
        for my $entry ( @{ $D->{marketcap}->{list} } ) {
            my $rank;
            my $currency;
            if ( $entry->{symbol} eq 'others' ) {
                $currency =
                    $entry->{name} . ' ('
                  . $D->{marketcap}->{total_other_coins}
                  . ' coins)<sup>**</sup>';
                $rank = 'n/a';
            }
            elsif ( $entry->{symbol} eq 'BTC' ) {
                $currency =
                  $entry->{name} . ' (' . $entry->{symbol} . ')<sup>*</sup>';
                $rank = $entry->{rank};
            }
            else {
                $currency = $entry->{name} . ' (' . $entry->{symbol} . ')';
                $rank     = $entry->{rank};
            }
            my $mcap;
            my $dominance;
            if ( defined $entry->{market_cap_usd} ) {
                $mcap      = large_num( $entry->{market_cap_usd} );
                $dominance = sprintf( '%.01f%%',
                    $entry->{market_cap_usd} /
                      $D->{marketcap}->{total_mcap} *
                      100 );
            }
            else {
                $mcap      = 'n/a';
                $dominance = 'n/a';
            }
            my $total;
            if ( defined $entry->{total_supply} ) {
                $total = large_num( $entry->{total_supply} );
            }
            else {
                $total = 'n/a';
            }

            my $unit_price = sprintf( '%.02f', $entry->{price_usd} );
            my $btc_price =
              defined $entry->{price_btc}
              ? sprintf( '%.03E', $entry->{price_btc} )
              : 'n/a';

            my $pct_avail;
            if (    defined $entry->{total_supply}
                and defined $entry->{available_supply} )
            {
                $pct_avail = sprintf( '%.01f%%',
                    $entry->{available_supply} / $entry->{total_supply} * 100 );
            }
            else {
                $pct_avail = 'n/a';
            }
            my @changes = map {
                defined( $entry->{ 'percent_change_' . $_ }
                  )    # check if there is data...
                  ? ( color_num( $entry->{ 'percent_change_' . $_ } . '%' ) )
                  : 'n/a'
            } qw/1h 24h 7d/;

            push @{$marketcap_table},
              td(
                [
                    $rank,       $currency,  $mcap,
                    $unit_price, $btc_price, $dominance,
                    $total,      $pct_avail, @changes
                ]
              );
        }
    }

    ### ==================================================
    my $future_table;
    my $K = $D->{scaffolding}->{coefficients}->{slope_30d};
    push @{$future_table}, th( [ 'Event', 'Price', 'ETA' ] );
    foreach my $line ( @{ $D->{future_prices}->{table} } ) {
        push @{$future_table}, td($line);
    }

    ### =================================================
    my @draper = map { $D->{draper}->{$_} } qw/coins price_at_purchase/;
    my @past_events = (
        {
            header  => "Tim Draper's coins from Silk Road",
            content => [
                sprintf(
"On 27 Jun 2014, investor Tim Draper paid approximately USD&nbsp;%.02f/coin for %s BTC seized from Silk Road. ",
                    $draper[1], $draper[0]
                ),
                sprintf( "Purchase price: USD&nbsp;%s",
                    large_num( $draper[0] * $draper[1] ) ),
                sprintf( "Price now: USD&nbsp;%s",
                    large_num( $draper[0] * $last ) ),
                sprintf( "Draper's win/loss: USD&nbsp;%s",
                    large_num( $draper[0] * ( $last - $draper[1] ) ) ),
            ]
        },
        {
            header  => "The Bitcoin pizza",
            content => [
"On 22nd May 2010, Bitcoin enthusiast Laszlo Hanyec bought a pizza for 10,000 bitcoins. More specifically, he sent the coins to someone else who purchased the pizza for him.",
                sprintf( "The Bitcoin pizza is currently worth USD&nbsp;%s.",
                    nformat( 10_000 * $last ) ),
"See the <a href='https://twitter.com/bitcoin_pizza'>\@bitcoin_pizza</a> Twitter account for up-to-date values!",
            ],
        },
        {
            header  => "The white Mini Cooper",
            content => [
                sprintf(
"On 7 Jun 2014, Andreas M. Antonopoulos offered a white Mini Cooper for sale for 14BTC. At the time, the VWAP was USD&nbsp;652.76, so the sales price (assuming it went through) was USD&nbsp;%s.",
                    nformat( 14 * 652.76 ) ),
                sprintf( "Today, the same car is worth USD&nbsp;%s.",
                    nformat( 14 * $last ) ),
"(Source: <a href='https://twitter.com/aantonop/status/475048024453152768'>\@aantonop tweet</a>.)"
            ],
        },
        {
            header  => "2016 Bitfinex hack",
            content => [
"On 2 Aug 2016, the exchange Bitfinex announced they had suffered a security breach and that 119,756 BTC were stolen.",
                sprintf( "Current value of the stolen coins is USD&nbsp;%s.",
                    nformat( 119_756 * $last ) )
            ],
        },
        {
            header  => "Price of a Leica Noctilux-M 75mm f/1.25 ASPH lens",
            content => [
"The price of this lens was \$12,795 at announcement. The price of this lens in BTC is "
                  . sprintf( "%.05f BTC.", 12795 / $last )
            ]
        },

    );

    ### Output ########################################

    print header;
    my $title = sprintf( "\$%s (%+.02f)", $last, $diff );
    print start_html(
        -title => "$title",
        -head  => [
            Link(
                {
                    -rel   => 'stylesheet',
                    -type  => 'text/css',
                    -media => 'all',
                    -href  => 'http://gerikson.com/stylesheets/btcticker.css'
                }
            )
        ]
    );

    print h1( nformat($last) );

    print p(
        sprintf(
            "Updated on %s (%s ago).",
            epoch_to_parts( $array->[0]->[2] )->{std},
            eta_time( $array->[0]->[3] )
        ),
        ' Data from ',
        a( { href => "https://bitcoinaverage.com/" }, "Bitcoinaverage" ),
        '.'
    );

    print h2("At a glance");

    print table( {}, @t1_rows );

    print h3("Hourly open, low, high");
    print table( {}, Tr( {}, $olh_table ) );
    print h3("Changes from last updates (UTC times)");

    print table( {}, Tr( {}, $latest_table ) );

    print h2("Current price compared to historical prices");
    print table( {}, Tr( {}, $hist_table ) );
    if ( $config->{show_cap_html} ) {
        print h2('Current cryptocurrency "marketcaps"');
        print p(
"A more correct term is aggregated value - it's the product of last price and outstanding coins or tokens."
        );
        my $mcap_txt = large_num( $D->{marketcap}->{total_mcap} );
        print h3("Total: $mcap_txt");
        print p(
            "Data from ",
            a( { href => "https://coinmarketcap.com/" }, "Coinmarketcap.com" )
              . '.'
        );
        print p( "Fetched on ", $D->{marketcap}->{fetched}, 'UTC.' );

        print table( {}, Tr( {}, $marketcap_table ) );
        print p(
            "<sup>*</sup> For Bitcoin, values for market cap, unit
		price, and number of coins may differ from other
		values on this page due to different methodology and
		update times. See ",
            a(
                {
                    href =>
                      'http://gerikson.com/btcticker/about.html#marketcap'
                },
                'this section'
            ),
            "for more information."
        );
        print p(
            "<sup>**</sup> Values for total supply, unit price,
		supply percentage, and change percentages are
		volume-weighted averages (USD marketcap used as
		weight)."
        );
    }
    print "<a id='extrapolated'></a>";
    print h2("Historical prices compared to extrapolated trends");
    print table( {}, Tr( {}, $pred_table ) );

    print h2("Future prices based on linear trend from last 90 days");
    print p(
        sprintf(
"Current slope: %.02f USD/day. Based on this line, the price will reach: ",
            $K )
    );
    if ( $K == 0 ) {
        print p("The price will never change in the future.");
    }
    else {
        print table( {}, Tr( {}, $future_table ) );
    }

    print h2("Random stats and figures");

    foreach my $item (@past_events) {
        print h3( $item->{header} );
        foreach my $line ( @{ $item->{content} } ) {
            print p($line);
        }
    }

    ### End matter ########################################
    print p(
        a(
            { href => 'http://gerikson.com/btcticker/about.html#Disclaimer' },
            'Disclaimer'
        )
    );
    print p(
        a( { href => 'http://gerikson.com/btcticker/about.html' }, 'About' ) );
}    # html_out

######################################################################

sub oneline_out {
    my ($D) = @_;
    my ( $hi, $lo ) = map { $D->{ticker}->{$_} } qw/24h_max 24h_min/;
    print header('text/plain');
    my $line = sprintf(
        "Last: \$%.02f [%+.02f] ",
        $D->{ticker}->{last},
        $D->{ticker}->{ntl_diff}
    );
    $line .= sprintf( "(H:%.02f/L:%.02f/S:%.02f) Vol %s | ",
        $hi, $lo, $hi - $lo, large_num( $D->{ticker}->{volume} ) );

    my $coins_now = $D->{layout}->[3]->[-1];
    $line .=
      sprintf( "Mcap %s | ", large_num( $D->{ticker}->{last} * $coins_now ) );
    $line .= eta_time( $D->{ticker}->{age} ) . " ago | ";
    my @array;
    foreach my $l ( @{ $D->{history} } ) {
        my ( $pct, $short ) = @{$l}[ 4, 7 ];
        next if ( $short eq '3mo' or $short eq '3yr' or $short eq '4yr' );
        push @array, sprintf( "%s %+.01f%%;", $short, $pct );
    }
    $line .= join( ' ', @array );

    print "$line - http://is.gd/B7NIP2\n";
}    # oneline_out

### ==================================================

sub mcap_out {
    my ($D)        = @_;
    my $fetched    = $D->{marketcap}->{fetched};
    my $total_mcap = $D->{marketcap}->{total_mcap};
    my $list       = $D->{marketcap}->{list};
    print BLUE;
    printf(
        "%4s %7s %8s %7s %7s %8s %7s %8s %7s %7s",
        '#',     'Coin',   'Mcap', 'Price', 'Domi',
        'Total', 'Avail%', '1h',   '24h',   '7d'
    );
    print RESET. "\n";
    my $line_count = 1;
    my @volumes;
    my %compare_prices;

    foreach my $el ( @{$list} ) {
        my ( $rank, $name ) = map { $el->{$_} } qw/rank symbol/;
        my ($unit_price) = $el->{price_usd};
        my ( $mcap, $total ) =
          map { defined( $el->{$_} ) ? large_num( $el->{$_} ) : 'n/a' }
          qw/market_cap_usd total_supply /;

        my $_24h_vol =
          $el->{'24h_volume_usd'} ? $el->{'24h_volume_usd'} : 'n/a';

        # some hackery for specific volumes and prices
        if ( $name eq 'BTC' or $name eq 'BCH' or $name eq 'ETH' ) {
            push @volumes,
              {
                symbol  => $name,
                rank    => $rank,
                volume  => $_24h_vol,
                unitvol => $_24h_vol / $unit_price
              };
            $compare_prices{$name} = $unit_price;
        }
        my $avail_pct;
        if ( defined $el->{total_supply} ) {
            $avail_pct = $el->{available_supply} / $el->{total_supply} * 100;
            $avail_pct =
              $avail_pct == 100
              ? sprintf( '%02d',  $avail_pct )
              : sprintf( '%.01f', $avail_pct );
        }
        else {
            $avail_pct = 'n/a';
        }
        my $frac_of_top;
        if ( defined $el->{market_cap_usd} ) {
            $frac_of_top =
              sprintf( "%6.01f%%", $el->{market_cap_usd} / $total_mcap * 100 );
        }
        else {
            $frac_of_top = 'n/a';
        }

        my @changes = map {
            defined $el->{$_}
              ? (    # need to code defensively if there's no actual data
                $el->{$_} < 0
                ? RED . sprintf( '%.01f%%', $el->{$_} ) . RESET
                : GREEN . sprintf( '%.01f%%', $el->{$_} ) . RESET
              )
              : YELLOW . 'n/a'
              . RESET
        } qw/percent_change_1h percent_change_24h percent_change_7d/;
        printf( "%4d %7s %8s %8.02f %7s %8s %6s%%  %16s %16s %16s\n",
            $rank, $name, $mcap, $unit_price, $frac_of_top, $total,
            $avail_pct, @changes );
        $line_count++;
    }

    # some extra data
    my $vol_line      = '   24h USD vol: ';
    my $unit_vol_line = '  24h unit vol: ';
    my $prc_line      = '  currency/BTC: ';
    foreach my $item ( sort { $b->{volume} <=> $a->{volume} } @volumes ) {
        $vol_line .= sprintf( " %4s %8s |",
            $item->{symbol} . ' (' . $item->{rank} . ')',
            large_num( $item->{volume} ) );
        $unit_vol_line .=
          sprintf( " %4s %8s |", '---"---', large_num( $item->{unitvol} ) );
        $prc_line .= sprintf( " %4s %8.02e |",
            '---"---',
            $compare_prices{ $item->{symbol} } / $compare_prices{BTC} );

    }
    print $vol_line,      "\n";
    print $unit_vol_line, "\n";
    print $prc_line,      "\n";
    $line_count += 3;

    # pad the output to fit the screen
    my $line_diff = 20 - $line_count;
    my $idx       = 0;
    while ( $idx < $line_diff ) {
        print "\n";
        $idx++;
    }
    my $mcap_txt = large_num($total_mcap);
    print "  Total: $mcap_txt       Fetched: $fetched\n";
}    # mcap_out
