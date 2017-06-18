#!/usr/bin/perl -T
use strict;
use warnings;

use lib ("/home/gustaf/prj/BTCTicker/"); # , "/home/gustaf/perl5/lib/perl5/");
use DBI;
use CGI qw(:standard start_ul *table);
use CGI::Carp qw(fatalsToBrowser);
use JSON;
use Term::ANSIColor qw(:constants);
#use Scalar::Util qw(looks_like_number);
use List::Util qw(min max first);
use Number::Format;
use DateTime;
#use Time::Local;
#use Text::Wrap;
#use Time::Piece;
use Time::Seconds;
use Data::Dumper;

my $driver = 'SQLite';
my $database = '/home/www/gerikson.com/cgi-bin/data/historical-prices.db';
my $dsn = "DBI:$driver:dbname=$database";
my ($user, $pass) = ('','');

my $dbh = DBI->connect($dsn, $user, $pass, {RaiseError=>1}) or die $DBI::errstr;

### keep the SQLs separate 
my %Sql;

$Sql{'latest_price'} = qq/select strftime('%s', timestamp), last, high, low, volume from ticker order by timestamp desc limit 10/;

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
# where strftime('%Y-%m-%d',timestamp) = strftime('%Y-%m-%d', 'now', ?) 
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

$Sql{'first_date'} = qq/select julianday(timestamp) from history order by timestamp limit 1/;

#$Sql{'price_volume'} = qq/select timestamp, data from pricevolumes order by timestamp desc limit 1/;

#$Sql{'daily_min_max'} = qq/select min(p.average), max(p.average) from prices p where p.timestamp > datetime('now','-1 day') and p.average <> ''/;
$Sql{'monthly_min_max'} = qq/select min(h.low), max(h.high) from history h where h.timestamp > datetime('now', '-30 day')/;

$Sql{'historical_coins'} = qq/select julianday(timestamp) as ts, block, no_of_coins as coins from blocks/;
my $historical_coins;

### HELPER FUNCTIONS ########################################

sub large_num { # return numbers in K, M, B based on size
    my ($x) = @_;
    my $negative = 1 if $x<0;
    $x = -$x if $negative;
    return $negative ? -$x : $x if $x < 1_000;
    return sprintf("%.02fk", $negative ? -$x/1_000 : $x/1_000) if ($x >= 1_000 and $x < 1_000_000);
    return sprintf("%.02fM", $negative ? -$x/1_000_000 : $x/1_000_000 ) if ($x >= 1_000_000 and $x < 1_000_000_000);
    return sprintf("%.02fB", $negative ? -$x/1_000_000_000 : $x/1_000_000_000 ) if ($x >= 1_000_000_000);
}

my @months = qw(Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec);
my @wdays  = qw/Sun Mon Tue Wed Thu Fri Sat/;

sub format_utc { # in: epoch seconds, out: <weekday day mon year HH:MI:SS>
    # adding a second defined arguemtn with
    # return an arrayref with date and time
    my ($e,$flag) = @_; 
    #  0    1    2     3     4    5     6     7     8
    my($sec,$min,$hour,$mday,$mon,$year,$wday,$yday,$isdst) =gmtime($e);
    if ( $e > (1436044942 + 500 * 365 * 24 * 3600) ) {
	return $flag ?
	  [sprintf("In the year %d", $year+1900), 'n/a'] :
	   sprintf("In the year %d", $year+1900);
    }
    # 12 Sep 2014 22:33:44
    if ( defined $flag ) {
	return [sprintf("%s %02d %s %04d",
			$wdays[$wday], $mday, $months[$mon], $year+1900),
		sprintf("%02d:%02d:%02d",
			$hour, $min, $sec)];
    } else { 
	return sprintf("%s %02d %s %04d %02d:%02d:%02d",
		       $wdays[$wday], $mday, $months[$mon], $year+1900,
		       $hour, $min, $sec);
    }
}

sub date_parts {
    # EX date_time
    # input: "YYYY-MM-DD HH:MI:SS" string
    # output: hashref with named fields
    # ymd (0): YYYY-MM-DD string
    # hms (1): HH:MI:SS string
    # str (2): DD mon YYYY string
    # jd (3): Julian date
    # ep (4): epoch seconds
    
    my ($ts) = @_;
    if ( $ts =~ m/(\d{4})-(\d{2})-(\d{2}) (\d{2}):(\d{2}):(\d{2})/ ) {
	my ( $yyyy, $mm, $dd, $hh, $mi, $ss) = ($1,$2,$3,$4,$5,$6);
	my $dt = DateTime->new(year=>$yyyy,month=>$mm,day=>$dd,
			       hour=>$hh,minute=>$mi,second=>$ss);
	return { ymd=>sprintf("%04d-%02d-%02d", $1,$2,$3),
		hms=>sprintf("%02d:%02d:%02d", $4,$5,$6),
		str=>sprintf("%d %s %04d", $3, $months[$2-1], $1),
		jd=>$dt->jd(),
		ep=>$dt->epoch()
	       };
    } else {
	warn "--> $ts is not correctly formatted date string\n";
	return [];
    }
}

sub jd_to_ep {
    # Ex Jul2Greg
    # input: Julian date
    # output: epoch seconds
    
    # http://aa.usno.navy.mil/faq/docs/JD_Formula.php
    my ($JUL) = @_;

    my $D = int($JUL);
    my $frac = $JUL - $D;

    # Julian dates change at noon, convert so it's at midnight instead
    if ( $frac < 0.5 ) {
	$frac = $frac + 0.5;
    } else {
	$D++; $frac = $frac - 0.5;
    } 

    my ($yyyy,$MM,$dd);

    { use integer;	      # fortran code requires integer division
      my $L = $D + 68569;
      my $N = 4*$L/146097;
      $L = $L - (146097*$N+3)/4;
      my $I = 4000 * ($L+1)/1461001;
      $L = $L - 1461*$I/4+31;
      my $J = 80 * $L/2447;
      my $K = $L - 2447* $J/80;
      $L = $J/11;
      $J = $J+2 - 12*$L;
      $I = 100*($N-49)+$I+$L;

      ($yyyy,$MM,$dd)=($I,$J,$K);
  }
    my $span;
    my ( $hh, $mm, $ss );
    $span = $frac * 24 * 60 * 60 ; # number of seconds
    $hh = ($span/(60*60))%24;
    $mm = ($span/60)%60;
    $ss =  $span%60;

    # return epoch seconds
    return timegm( $ss, $mm, $hh, $dd, $MM-1, $yyyy );
}

sub eta_time {
    # input: seconds
    # ouput: duration in days, hours, minutes and seconds
    
    my ($ep) = @_;
    my ( $dd, $hh, $mm, $ss ) = ( int($ep/(24*60*60)),
				  ($ep/(60*60))%24,
				  ($ep/60)%60,
				  $ep%60);
    if ($dd>0) {
	return sprintf("%3dd %02dh %02dm %02ds", $dd,$hh,$mm,$ss)
    }elsif ($hh>0){
	return sprintf("%02dh %02dm %02ds",$hh,$mm,$ss)
    }else {
	return sprintf("%02dm%02ds",$mm,$ss)
    }
    
}

sub hum_duration {
    my ($s) = @_;
    my %pieces = (year=>0,month=>0,day=>0);
    my $v = Time::Seconds->new($s);
    my $long_years ;
    # check for years
    if ( $v->years > 0 ) {
	# don't bother w/ years > 500
	if ( $v->years > 500 ) { $long_years = sprintf("%.02f years", $v->years) }
	 
	# grab the integer part, remove years from duration
	
	$pieces{year} = int($v->years);
	$s = $s - $pieces{year} * 365 * 24 * 3600;
	$v = Time::Seconds->new($s);
    }
    if ( $v->months > 0 ) {
	$pieces{month} = int($v->months);
	$s = $s - $pieces{month} * 30 * 24 * 3600;
	$v = Time::Seconds->new($s);
    }
    if ( $v->days > 0 ) {
	$pieces{day} = sprintf("%.0f", $v->days); # use rounding
    }
    my $out;
    foreach my $u (qw(year month day)) {
	next if $pieces{$u} == 0;
	my $suffix = $pieces{$u} > 1 ? $u .'s' : $u;
        push @$out, $pieces{$u}.' '.$suffix;
    }
#    return join(', ',@$out);
    # http://blog.nu42.com/2013/10/comma-quibbling-in-perl.html - "If
    # the maintenance programmer has issues with the use of the array
    # slice and range operator above, s/he might use this as an
    # opportunity to learn about them."
    return $long_years if ( defined $long_years );
    my $n = @$out;
    return $out->[0] if $n == 1;
    return join(' and ' => join(', ' => @$out[0 .. ($n - 2)]),$out->[-1],);
}

sub color_num {
    my ($x) = @_;
    my $is_pct = 0;
    my $f = new Number::Format;
    if ( $x =~ m/%$/ ) {
	$is_pct = 1;
	$x =~ s/%$//m;
    }
    my $dec = $is_pct?1:2;
    if ( $x < 0 ) {
	$x = $f->format_number($x,$dec,2) ;# if $x < -1_000;
	$x = "$x%" if $is_pct;
	return "<span class='negative'>$x</span>";
    } else {
	$x = $f->format_number($x,$dec,2) ; #if $x > 1_000;
	$x = "$x%" if $is_pct;
	return return "<span class='positive'>$x</span>";
    }
}

sub number_of_bitcoins {
    # input: julian date
    # output: number of bitcoins mined since date
    my ($jd) = @_;
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
    my $x = ($jd - $jd_1)/($jd_2 - $jd_1) * $h;
    return $x+$B;
    
}

sub nformat {
    my ( $in) = @_;
    my $nf = new Number::Format;
    return $nf->format_number($in, 2, 2);
}


sub by_number { # http://perlmaven.com/sorting-mixed-strings
    my ( $anum ) = $a =~ /(\d+)/;
    my ( $bnum ) = $b =~ /(\d+)/;
    ( $anum || 0 ) <=> ( $bnum || 0 );
}

### OUTPUT FUNCTIONS ########################################

#my $nf = new Number::Format;

my $api_down = 0;
my $api_down_text = "Can't keep a good tracker down...";
sub debug_out {
    my ($D)=@_;
    my $now = DateTime->now;
    my $jd = $now->jd();
    my $coins_now = number_of_bitcoins($jd);
    print "Estimated number of bitcoins at $now is $coins_now\n";

}

#### Console ####

sub console_out {
    my ($D) = @_;
    if ($api_down) {
	print $api_down_text, "\n";
	return;
    }


    my $coins_now = $D->{est_no_of_coins};
    my $last= $D->{ticker}->{last};
    my $data = $D->{layout};
    my @out;
    my $d = shift @{$data};
    my $diff = sprintf('%+.02f',$d->[1]);
    if ( $diff < 0 ) { $diff=RED.$diff.RESET }
    else { $diff=GREEN.$diff.RESET }

    push @out, sprintf("   Last: %s [%17s] | %34s (%s)",
		       BLUE.$d->[0].RESET, $diff, format_utc($d->[2]), eta_time($d->[3]));
    $d = shift @{$data};
    push @out, sprintf("%8s %7.02f (%+8.02f) | %8s %7.02f (%+8.02f) | %8s %7s",
		       '24h max', $d->[0], $d->[1],
		       '30d max', $d->[2], $d->[3] ,
		       '24h vol', large_num($d->[-1]));
    $d=shift @{$data};
    push @out, sprintf("%8s %7.02f (%+8.02f) | %8s %7.02f (%+8.02f) | %8s %7s", 		       'min', $d->[0], $d->[1],
		       'min',$d->[2], $d->[3],
		       'Mcap',large_num($d->[-1]));
    $d=shift @{$data};
    push @out, sprintf("%8s %7.02f [%7.01f%%] | %8s %7.02f [%7.01f%%] | %8s %7s",
		       'spread', $d->[0], $d->[1],
		       'spread', $d->[2], $d->[3],
		       'Coins',large_num($d->[-1]));

    print join("\n", @out);
    print "\n";
    foreach my $line ( @{$D->{history}} ){
	my ($label, $date, $price, $diff, $pct, $vol, $mcap,$short) = @{$line};
#	$price = nformat($price);
#	$diff = nformat($diff);
#	$pct = nformat($pct);
	$vol = large_num($vol);
	$mcap= large_num($mcap);
	if ( $diff < 0 and $pct < 0 ) {
	    $diff = RED.sprintf("%+.02f",$diff).RESET;
	    $pct = RED.sprintf("%+.01f%%",$pct).RESET;
	} else {
	    $diff = GREEN.sprintf("%+.02f",$diff).RESET;
	    $pct = GREEN.sprintf("%+.01f%%",$pct).RESET;
	}
	printf("%19s %10s %8s %18s %17s %8s %8s\n",
	       $label, '['.$date.']', $price , $diff, $pct, $vol, $mcap);
    }
}

sub json_out {
    if ($api_down) {
	print $api_down_text;
	return;
    }

    my ($D) = @_;
    print header('application/json');
    print to_json($D, {ascii=>1, pretty=>1});
}


#### HTML ####

sub html_out {
    my ($D) = @_;
    my $about_page = 'http://gerikson.com/btcticker/about.html';
    my $last = $D->{ticker}->{last};
    print header;
    print start_html(
		     -title=>"Last: \$$last",
		     -head =>[Link({
				    -rel=>'stylesheet',
				    -type=>'text/css',
				    -media=>'all',
				    -href=>'http://gerikson.com/stylesheets/btcticker.css'
				   })
			     ]);
    my $array = $D->{layout};
    my $diff=$array->[0]->[1];
    my $coins_now = $D->{est_no_of_coins};
    print h1(nformat($last));
    print h3("Change from last update: ", color_num($diff));

    print p(sprintf("Updated on %s (%s ago).",
		    format_utc($array->[0]->[2]),
		    eta_time($array->[0]->[3])));
    my @t1_rows;
    my ($_24hmax, $_24hmin) = map {$array->[$_]->[0]} qw/1 2/;
    my ($_30dmax, $_30dmin) = map {$array->[$_]->[2]} qw/1 2/;

    push @t1_rows,
      Tr((th(['24h price range', 'Diff','30d price range','Diff', 'Aggregate figures'])));
    push @t1_rows,
      Tr(td(['Max: '.nformat($_24hmax),
	     sprintf('%+.02f',$array->[1]->[1]),
	     'Max: '.nformat($_30dmax),
	     sprintf('%+.02f', $array->[1]->[3]),
	     '24h volume: '.large_num($array->[1]->[-1])
	     ]));
    push @t1_rows,
      Tr(td(['Min: '.nformat($_24hmin),
	 sprintf('%+.02f',$array->[2]->[1]),
	     'Min: '.nformat($_30dmin),
	     sprintf('%+.02f', $array->[2]->[3]),

	     'Market cap: '.large_num($array->[2]->[-1])
	]));
    push @t1_rows,
      Tr(td(['Spread: '.nformat($array->[3]->[0]),
	     sprintf('%.01f%%',$array->[3]->[1]),
	     'Spread: '.nformat($array->[3]->[2]),
	     sprintf('%.01f%%',$array->[3]->[3]),
	     'Est. coins: '.large_num($array->[3]->[-1])
	    ]));
    print table( {}, @t1_rows);

    my $hist_table;

    push @{$hist_table}, th(['Event', 'Date', 'Price', 'Difference',
			     'Change in %', 'Volume (BTC)', "Price &#215; Vol",
			     'Market cap']);
    foreach my $line ( @{$D->{history}} ){
	my ($label,$date, $price, $diff, $pct, $vol, $mcap,$short) = @{$line};
	push @{$hist_table},
	  td(["$label ($short)", $date, nformat($price), color_num($diff),
	      color_num($pct.'%'), large_num($vol), large_num($vol*$price), large_num($mcap)]);
    }
    print h2("Current price compared to historical prices");
    print table({}, Tr({}, $hist_table));

    ###
    print p(a({href=>'http://gerikson.com/btcticker/about.html'}, 'About'));
}

sub oneline_out {
    my ($D) = @_;
    my ( $hi, $lo)= map{ $D->{ticker}->{$_}} qw/24h_max 24h_min/;
    print header('text/plain');
    my $line = sprintf("Last: \$%.02f [%+.02f] ", $D->{ticker}->{last}, $D->{ticker}->{ntl_diff});
    $line .= sprintf("(H:%.02f/L:%.02f/S:%.02f) Vol %s | ",
		     $hi,$lo, $hi-$lo,large_num($D->{ticker}->{volume}));
    #		     map{ $D->{ticker}->{$_}} qw/high low volume/);
    my $coins_now = $D->{layout}->[3]->[-1];
    $line .= sprintf("Mcap %s | ", large_num($D->{ticker}->{last} * $coins_now));
    $line .=  eta_time($D->{ticker}->{age})." ago | ";
    my @array;
    foreach my $l ( @{$D->{history}} ) {
	push @array, sprintf("%s %.01f%%;", $l->[-1], $l->[4]);
    }
    $line .= join(' ', @array);

    print "$line - http://is.gd/B7NIP2\n";
}


#### 

my $query = new CGI;
my $output = $query->param('o') || '';

#### 
my $Data = {};
my $sth;
my $rv;
### current price, from DB

$sth=$dbh->prepare($Sql{latest_price});
$rv=$sth->execute();
warn DBI->errstr if $rv < 0;
my $result = $sth->fetchall_arrayref();

my $latest =$result->[0];

my @_10min;
for my $r (@{$result}) {
    push @_10min, $r->[1];
}
my $ntl = $_10min[1];
$Data->{debug} = $result;
$sth->finish();
my $now=time();
my ( $_24h_max, $_24h_min) = ( $latest->[2],$latest->[3]);
my $last = $latest->[1];
$Data->{ticker}  = {
		    timestamp=>$latest->[0],
		    age=>$now-$latest->[0],
		    last =>$last,
		    '24h_max'=>$latest->[2],
		    '24h_min'=>$latest->[3],
		    volume=>$latest->[4],
		    ntl_diff => $last - $ntl
		   };
#$Data->{debug}= {diff => $last - $ntl->[1],		 latest=>$last,		ntl=>$ntl->[1]};

### 30 day min/max

my $_30d_ref =
  $dbh->selectcol_arrayref( $Sql{monthly_min_max},
			    {Columns=>[1,2]});

my ( $_30d_min, $_30d_max ) = @{$_30d_ref};
if ( $_24h_max > $_30d_max ) { $_30d_max = $_24h_max }
if ( $_24h_min < $_30d_min ) { $_30d_min = $_24h_min }
$Data->{ticker}->{'30d_min'} = $_30d_min;
$Data->{ticker}->{'30d_max'} = $_30d_max;

### historical coins

$sth = $dbh->prepare($Sql{historical_coins});
$rv = $sth->execute();
warn DBI->errstr if $rv<0;
$historical_coins = $sth->fetchall_hashref(1);
$sth->finish();
my $coins_now=number_of_bitcoins(DateTime->now->jd());
#$Data->{est_no_of_coins} =$coins_now;

# historical data
my $history;
my %fixed;
$fixed{180}= {label=>'6 months ago',   short=> '6mo'};
$fixed{1}    ={label => '24 hours ago', short=> '24h'};
$fixed{30}  = {label => '1 month ago', short => '1mo' };
$fixed{365} = {label => '1 year ago',  short => '1yr' };
$fixed{3} = { label => '3 days ago', short=>'3dy' };
$fixed{730}  ={label =>'2 years ago', short=>'2yr'};
$fixed{7}   = {label => '1 week ago',  short => '1wk' };

my $labels = { ath=> { label=>'Record high ("ATH")'},
	       ytd=> { label=>"Year to date"},
	       'yhi' =>{ label=>  "This year's high"},
	       'ylo' =>{ label=> "This year's low"},
	       'zhi' =>{ label=> "365d rolling high", short =>'rhi' },
	       'zlo' =>{ label=> "365d rolling low", short=>'rlo'}
	     };

foreach my $day ( sort {$a <=> $b} keys %fixed ) {
    if ( $day == 1 ) { # special case
	my $yesterday = time - 24 * 3600;
	$sth = $dbh->prepare($Sql{'24h'});
#	warn "==> ". $Sql{'24h'}."\n";
#	warn "==> ". $yesterday ."\n";

	$rv = $sth->execute($yesterday - 5*60, $yesterday + 5*60);
	warn DBI->errstr if $rv<0;
	while ( my $ary = $sth->fetchrow_arrayref ) {
	    $history->{sprintf("%03d_day", $day)} =
	      { timestamp => $ary->[0], average => $ary->[1],
		high=>$ary->[2],low=>$ary->[3],volume=>$ary->[4],
		label=>$fixed{$day}->{label},
		short=>$fixed{$day}->{short} };
	}
	$sth->finish();
	next;
    }
    $sth = $dbh->prepare($Sql{days_ago});
    $rv = $sth->execute("-$day days");
    warn DBI->errstr if $rv<0;
    while ( my $aryref = $sth->fetchrow_arrayref ){
	my ( $timestamp, $high, $low, $average, $volume ) = @$aryref;

	$history->{sprintf("%03d_day",$day)} =
	  { timestamp => $timestamp, high=>$high, low=>$low,
	    average=> $average, volume => $volume,
	    short => $fixed{$day}->{short},
	    label => $fixed{$day}->{label} };
    }
}
$sth->finish();

foreach my $tag (qw(ath ytd yhi ylo zhi zlo)) {
    my $short;
    if ( defined $labels->{$tag}->{short} ) {
	$short = $labels->{$tag}->{short} }
    else {
	$short = $tag }
    $sth = $dbh->prepare($Sql{$tag});
    $rv =$sth->execute();
    warn DBI->errstr if $rv<0;
    while ( my $ary = $sth->fetchrow_arrayref ) {
        my ( $day, $timestamp, $high, $low, $average, $volume ) = @$ary;
        $history->{ sprintf( "%03d_%s", $day, $tag ) } = {
                                             timestamp => $timestamp,
                                             high      => $high,
                                             low       => $low,
                                             average   => $average,
                                             volume    => $volume,
                                             short     => $short,
                                             label => $labels->{$tag}->{label}
        };
    }
}
$sth->finish();

# common format for console and HTML
$Data->{layout} = [    # last, update, date, ago
    [ $last, $last - $ntl, $latest->[0], $now - $latest->[0] ],

    # Max row, volume
    [  $_24h_max,         $last - $_24h_max, $_30d_max,
       $last - $_30d_max, $latest->[4] ],

    # Min row, Mcap
    [  $_24h_min,
       $last - $_24h_min,
       $_30d_min,
       $last - $_30d_min,
       $last * $coins_now ],

    # spread, no of coins
    [  $_24h_max - $_24h_min,
       ( $_24h_max - $_24h_min ) / $last * 100,
       $_30d_max - $_30d_min,
       ( $_30d_max - $_30d_min ) / $last * 100,
       $coins_now ], ];

# common format for historical data
my %seen;
foreach my $tag ( sort by_number keys %{$history} ) {
    next if $tag !~ m/^\d+/;
    my $price;
    if ( $tag =~ 'yhi$' or $tag =~ 'ath$' or $tag =~ 'zhi$' ) {
	$price = $history->{$tag}->{high}
    } elsif ( $tag =~ 'ylo$' or $tag =~ 'zlo$' ){
	$price = $history->{$tag}->{low}
    } else {
	$price = $history->{$tag}->{average}
    }

    my $diff = $last - $price;
    my $pct = ($last - $price)/$price*100;
    my $vol = $history->{$tag}->{volume};
    my $tot = $vol*$price;
    my $date = date_parts($history->{$tag}->{timestamp})->{ymd};
    push @{$seen{$date}}, $tag;
    my $no_of_coins= number_of_bitcoins(date_parts($history->{$tag}->{timestamp})->{jd});
    my $market_cap = $no_of_coins*$price;
    next if ( scalar @{$seen{$date}} > 1  and $tag=~/[hi|lo]$/ );

    push @{$Data->{history}}, [$history->{$tag}->{label},
			       $date,
			       $price,
			       $diff,
			       $pct,
			       $vol,
			       $market_cap, $history->{$tag}->{short}] ;
}
for my $d ( sort keys %seen ) {
    next if scalar @{$seen{$d}} == 1;
    print join(' ', ($d, sort @{$seen{$d}})), "\n";
}
### output options

if ($output eq 'json'){
    json_out($Data);

} elsif ($output eq 'console') {
console_out($Data);
} elsif ($output eq 'irc' ){
    oneline_out($Data);
}

else {
    html_out($Data);
}

$dbh->disconnect();

