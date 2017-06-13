#!/usr/bin/perl -T
use strict;
use warnings;

use lib ("/home/gustaf/prj/BTCTicker/"); # , "/home/gustaf/perl5/lib/perl5/");
use DBI;
use CGI qw(:standard start_ul *table);
use CGI::Carp qw(fatalsToBrowser);
use LWP::Simple qw(!head);
use JSON;
use Term::ANSIColor qw(:constants);
use Scalar::Util qw(looks_like_number);
use List::Util qw(min max first);
use Number::Format;
use DateTime;
use Time::Local;
use Text::Wrap;
use Time::Piece; use Time::Seconds;

my $driver = 'SQLite';
my $database = '/home/www/gerikson.com/cgi-bin/data/historical-prices.db';
my $dsn = "DBI:$driver:dbname=$database";
my ($user, $pass) = ('','');

my $dbh = DBI->connect($dsn, $user, $pass, {RaiseError=>1}) or die $DBI::errstr;

### keep the SQLs separate 
my %Sql;

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
timestamp, average 
from history 
where volume is null and strftime('%s', timestamp) 
between ? and ?/;

$Sql{'anniv'} = qq/select 
strftime('%s',timestamp_1), average_1, 
strftime('%s',timestamp_2), average_2
from ranges 
where ? between average_1 and average_2
order by timestamp_1  limit 1/;

$Sql{'coeffs'} = qq/select * from coefficients order by timestamp desc limit 1/;

$Sql{'first_date'} = qq/select julianday(timestamp) from history order by timestamp limit 1/;

$Sql{'price_volume'} = qq/select timestamp, data from pricevolumes order by timestamp desc limit 1/;

$Sql{'daily_min_max'} = qq/select min(p.average), max(p.average) from prices p where p.timestamp > datetime('now','-1 day') and p.average <> ''/;
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

sub date_time { 
    # input: "YYYY-MM-DD HH:MI:SS" string
    # output: arrayref with fields
    # 0: YYYY-MM-DD string
    # 1: HH:MI:SS string
    # 2: DD mon YYYY string
    # 3: Julian date
    # 4: epoch seconds
    
    my ($ts) = @_;
    if ( $ts =~ m/(\d{4})-(\d{2})-(\d{2}) (\d{2}):(\d{2}):(\d{2})/ ) {
	my ( $yyyy, $mm, $dd, $hh, $mi, $ss) = ($1,$2,$3,$4,$5,$6);
	my $dt = DateTime->new(year=>$yyyy,month=>$mm,day=>$dd,
			       hour=>$hh,minute=>$mi,second=>$ss);
	return [sprintf("%04d-%02d-%02d", $1,$2,$3),
		sprintf("%02d:%02d:%02d", $4,$5,$6),
		sprintf("%d %s %04d", $3, $months[$2-1], $1),
		$dt->jd(),
		$dt->epoch()
	       ];
    } else {
	warn "--> $ts is not correctly formatted date string\n";
	return [];
    }
}

sub Jul2Greg {
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
    return sprintf("%3dd %02dh %02dm %02ds", #"%02dw%02dd%02dh%02dm%02ds",
#		   int($ep/(7*24*60*60)),
		   int($ep/(24*60*60)),
		   ($ep/(60*60))%24,
		   ($ep/60)%60,
		   $ep%60);
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
    if ( $x < 0 ) {
	
	$x = $f->format_number($x,2,2) if $x < -1_000;
$x = "$x%" if $is_pct;
	return "<span class='negative'>$x</span>";
    } else {

	$x = $f->format_number($x,2,2) if $x > 1_000;
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
sub number_of_bitcoins_old {
       # next halving, block 420_000
    # http://bitcoinclock.com/ has predicted date and time
    # Checked (UTC)	Predicted (UTC)		Predicted Julian
    # 			2016-08-02T22:32:08	2457603.44621528
    # 2014-12-10	2016-07-31 13:34:36	2457601.065694
    # 2015-03-25	2016-07-29 03:21:07	2457598.639664
    # 2015-04-07 21:20 	2016-07-28 16:08:54
    # 2015-05-28 08:38  2016-07-29 05:28:21
       # 2016-01-20 	2016-07-17 18:23:19
       # 2016-03-15	2016-07-13 00:25:02
       # 2016-05-11	2016-07-10 18:03:03
       # 2016-05-20	2016-07-10 20:57:00
       # 2016-06-09	2016-07-10 12:04:33
    # 2016-06-13	2016-07-10 05:52:12
    # 2016-06-28	2016-07-09 17:59:50
    # 2016-07-04        2016-07-09 10:47:34
    # 2016-07-05	2016-07-09 11:47:44
    # 2016-07-08	2016-07-09 13:03:29
    # 2016-07-09	2016-07-09 16:46:13
}


sub calc_price_volume {
    my ($info) = @_;
    my $total_vol = 0; my $sub_vol =0;
    my $priceXvol = 0; my $sub_priceXvol = 0;

    my $result;
    my $count =0; my $sub_count =0;

    ### we always want localbitcoins displayed
    my $always = 'localbitcoins';
    if ( exists $info->{$always} ) {
	push @$result, {exch => $always,
			last => $info->{$always}->{rates}->{last},
			vol => $info->{$always}->{volume_btc},
			display_name => $info->{$always}->{display_name}};
	$count++;
	$priceXvol += $info->{$always}->{rates}->{last} * $info->{$always}->{volume_btc};
	$total_vol += $info->{$always}->{volume_btc};

	delete $info->{$always};
    }

    foreach my $exch ( sort {
	$info->{$b}->{volume_btc} <=> $info->{$a}->{volume_btc} } keys %$info ) {
	my $last = sprintf("%.02f",$info->{$exch}->{rates}->{last});
	my $vol = sprintf("%.02f", $info->{$exch}->{volume_btc});
	my $display_name = $info->{$exch}->{display_name};
	$priceXvol += $last * $vol;
	$total_vol += $vol;
	if ( $count < 5  ) {	# fill the first 4 
	    push @$result, { exch=>$exch, last=>$last,
			     vol=>$vol, display_name=>$display_name };
	    $count++;
	} else {		# gather the rest in one bucket
	    $sub_priceXvol += $last * $vol;
	    $sub_vol += $vol;
	    $sub_count++;
	}
    }
    $sub_vol = $sub_vol ? $sub_vol : 0.001;
    push @$result, {exch=>"others",
		    last=>sprintf("%.02f",$sub_priceXvol/$sub_vol),
		    vol=>sprintf("%.02f",$sub_vol),
		    display_name=>"Others ($sub_count)"};

    unshift @$result, {vwap => $priceXvol / $total_vol, volume=>$total_vol};

    return $result;
}

sub by_number { # http://perlmaven.com/sorting-mixed-strings
    my ( $anum ) = $a =~ /(\d+)/;
    my ( $bnum ) = $b =~ /(\d+)/;
    ( $anum || 0 ) <=> ( $bnum || 0 );
}

### OUTPUT FUNCTIONS ########################################

my $nf = new Number::Format;
my $api_down = 0;
my $api_down_text = "The War on Bitcoin is over. Bitcoin won.";
sub markdown_out {
    my ($D) = @_;
    print header('text/plain');
    if ($api_down) {
	print $api_down_text, "\n";
	return;
    }
    
    my $price_now = $D->{'now'}->{price_now};
#    print ' ' x 4 . 'Generated on ' . scalar(gmtime(time)) . " UTC\n";
    print ' ' x 4 . '      ' . "Average volume weighted price: " . $price_now . '  ('. format_utc($D->{now}->{fetched})." UTC)\n";
    ### check size of fields: label, date, average, change, percentage
    my @rows;
    my @max = (0,0,0,0,0);
    foreach my $tag ( sort by_number keys %$D ) {
#	next if $tag eq 'now';
	next if $tag !~ m/^\d+/;
	my $price= $D->{$tag}->{average};
	my $diff = $price_now - $price;
	my $pct = ($price_now - $price)/$price * 100;
	my $row = [$D->{$tag}->{label}, '['. date_time($D->{$tag}->{timestamp})->[0] .']:', (map { sprintf(" %.02f", $_) } ($price, $diff)), sprintf(" %.02f%%", $pct) ];
	push @rows, $row;
	for ( my $i = 0; $i < scalar(@$row); $i++ ) {
	    if ( length($row->[$i]) > $max[$i] ) { $max[$i] = length($row->[$i]) }
	}
    }
    foreach my $r (@rows) {
	my $line = '    ';
	for ( my $i=0; $i<scalar @$r; $i++ ) {
	    my $spaces = $max[$i] - length($r->[$i]);
	    if ( $i == 0 ) {
		$line .= ' ' . $r->[$i] . ' ' x $spaces;
	    } else { 
	    $line .= ' ' . ' ' x $spaces . $r->[$i] ;
	}
	}
	print $line,"\n";
    }
    print ' ' x 4 . "Source: http://gerikson.com/cgi-bin/ticker.cgi"."\n";
}
sub debug_out {
    my ($D)=@_;
    my $now = DateTime->now;
    my $jd = $now->jd();
    my $coins_now = number_of_bitcoins($jd);
    print "Estimated number of bitcoins at $now is $coins_now\n";

}

#### Console ####

sub console_out {
    if ($api_down) {
	print $api_down_text, "\n";
	return;
    }


    my $coins_now = number_of_bitcoins(DateTime->now->jd());
    # 3rd row: 24h spread | 30d spread | no. of Bitcoins
    printf("%8s: %8s\n",
	   'Bitcoins',$coins_now?large_num($coins_now):'n/a'
	  );	   
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
    my $about_page = 'http://gerikson.com/btcticker/about.html';
    print header;
    print start_html(
		     -title=>"Current number of bitcoins",
		     -head =>[Link({
				    -rel=>'stylesheet',
				    -type=>'text/css',
				    -media=>'all',
				    -href=>'http://gerikson.com/stylesheets/btcticker.css'
				   })
			     ]);

    my $coins_now = number_of_bitcoins(DateTime->now->jd());
    print p($coins_now?"Est. coins: ".large_num($coins_now).' BTC':'n/a');


    print h2("Changelog");
    my @changelog;
    while (<DATA>) {
	chomp;
	push @changelog, $_."\n";
    }
    @changelog = sort {$b cmp $a} @changelog;
    print ul (li(\@changelog));
    print end_html();
}

#### 

my $query = new CGI;
my $output = $query->param('o') || '';

#### 

my $Data={}; 

### historical coins

my $sth = $dbh->prepare($Sql{historical_coins});
my $rv = $sth->execute();
warn DBI->errstr if $rv<0;
$historical_coins = $sth->fetchall_hashref(1);
$sth->finish();

#$Data->{no_of_coins} = $historical_coins;

### output options

if ($output eq 'json'){
    json_out($Data);

} elsif ($output eq 'console') {
console_out($Data);
}
else {
    html_out($Data);
}

$dbh->disconnect();


__END__
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
