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
my $api_down_text = "Site down for the time being.";
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
    foreach my $tag ( sort {$a <=> $b} keys %$D ) {
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

sub console_out {
    if ($api_down) {
	print $api_down_text, "\n";
	return;
    }

    my ($D) = @_;
    my $price_now = $D->{'now'}->{price_now};
    my $fetched = $D->{'now'}->{fetched};
    my $next_to_last = $D->{'now'}->{next_to_last};
    my $formatted_price = BOLD . $nf->format_number($price_now,2,2). RESET;
    if ( defined $next_to_last ) { 
	if ( $next_to_last < $price_now ) { # price has gone up
	    $formatted_price =
	      GREEN . $nf->format_number($price_now,2,2). RESET;
	} else {
	    $formatted_price =
	      RED . $nf->format_number($price_now,2,2). RESET;
	}
    }

    my $coins_now = number_of_bitcoins(DateTime->now->jd());
    ### check size of fields: label, date, average, change, percentage, volume
    my @rows;
    # add stuff for predicted price
    #    my @preds;
    my @max = (0,0,0,0,0,0,0);

    my %seen = ();
    # sorting strings of the type "123_tag" on the numerical value
    # http://perlmaven.com/sorting-mixed-strings
    foreach my $tag ( sort by_number keys %$D ) {
	next if $tag !~ m/^\d+/;
	my $price;
	if ( $tag =~  'yhi$' or $tag =~ 'ath$' or $tag =~ 'zhi$') {
	    $price = $D->{$tag}->{high};
	} elsif ( $tag =~ 'ylo$' or $tag =~ 'zlo$' ) {
	    $price = $D->{$tag}->{low};
	} else {
	    $price= $D->{$tag}->{average};
	}
	my $diff = $price_now - $price;
	my $pct = ($price_now - $price)/$price * 100;
	my $vol = $D->{$tag}->{volume}?$D->{$tag}->{volume}:undef;
	my $tot = $vol?$vol * $price:undef;
	my $date = date_time($D->{$tag}->{timestamp})->[0];
	$seen{$date}++;
	my $no_of_coins =
	  number_of_bitcoins(date_time($D->{$tag}->{timestamp})->[3]);
	my $market_cap = $no_of_coins?large_num($no_of_coins * $price):'n/a';

	my $row = [
		   $D->{$tag}->{label},
		   ' ['. $date .']: ',
		   $nf->format_number($price,2,2),
		   sprintf(" %.02f", $diff), 
		   sprintf(" %.02f%%", $pct),
		   $vol?'  '.large_num($vol):' n/a',
		   $market_cap?'  '.$market_cap:'n/a'];
	push @rows, $row unless ( $seen{$date}>1 and $tag =~ /[hi|lo]$/ );

	for ( my $i = 0; $i < scalar(@$row); $i++ ) {
	    if ( length($row->[$i]) > $max[$i] ) {
		$max[$i] = length($row->[$i]);
	    }
	}
    }

    ### exchnages
    my @pv = @{$D->{now}->{price_volume}};
    my $p_v = shift @pv;	# first element
    my $total_vol;
    map {$total_vol += $_->{vol}} @pv;
    my @lasts;


    #### output
    print "      Average volume weighted price: " .$formatted_price. '         '. format_utc($fetched) ."\n";
    my $Kbit = $price_now/1_000;
    my ( $_24hmax, $_24hmin, $_30dmax, $_30dmin ) =
      map { $D->{now}->{$_} } qw (24h_max 24h_min 30d_max 30d_min );

    # we may have more updated values from the 24h set, use them for
    # the 30d set

    if ( $_24hmax > $_30dmax ) { $_30dmax = $_24hmax }
    if ( $_24hmin < $_30dmin ) { $_30dmin = $_24hmin }
    # 1st row: 24h max | 30d max | 24h vol

    printf(" [ %7s: %6.02f (%+6.02f) | %7s: %6.02f (%+7.02f) | %7s: %8s ]\n",
	   '24h max',$_24hmax, $price_now - $_24hmax,
	   '30d max',$_30dmax, $price_now - $_30dmax,
	   '24h vol',  large_num($total_vol)
	  );

    # 2nd row: 24h min | 30d min | Mcap
    printf(" [ %7s: %6.02f (%+6.02f) | %7s: %6.02f (%+7.02f) | %8s: %8s ]\n",
	   'min',$_24hmin, $price_now - $_24hmin,
	   'min',$_30dmin, $price_now - $_30dmin,
	   'Mcap',  $coins_now?large_num($price_now * $coins_now):'n/a'
	  );

    # 3rd row: 24h spread | 30d spread | no. of Bitcoins
    printf(" [ %7s: %6.02f [%5.01f%%] | %7s: %6.02f [%6.01f%%] | %8s: %8s ]\n",
	   'spread', $_24hmax  - $_24hmin,
	   ($_24hmax  - $_24hmin)/$price_now * 100,
	   'spread', $_30dmax  - $_30dmin,
	   ($_30dmax  - $_30dmin)/$price_now*100,
	   'Bitcoins',$coins_now?large_num($coins_now):'n/a'
	   
	  );	   

    foreach my $r (@rows) {
	my $line;
	for ( my $i=0; $i<scalar @$r; $i++ ) {
	    my $spaces = $max[$i] - length($r->[$i]);
	    ### specific formatting
	    my $val = $r->[$i];
	    # color
	    if ( looks_like_number( $val ) and $i == 3) {
		$val = $val < 0 ? RED.$val : GREEN.$val;
	    } elsif ( $val =~ m/%$/ ) {
		$val = $val.RESET;
	    }
	    if ( $i == 0 ) {
		my $padding = ' ' x $spaces;
		$line .= $val . $padding;
	    } else {
		$line .= ' ' x $spaces . $val ;
	    }
	}
	print ' ',$line,"\n";
    }
    my $exch_line = '';
    my $idx = 1;
    foreach my $el (sort {$b->{vol} <=> $a->{vol}} @pv ) {
	my ($exch, $last, $vol, $display_name) =
	  map {$el->{$_}} qw/exch last vol display_name/;

	my $diff = $last-$price_now;
	if ( $diff < 0 ) {
	    $diff = RED sprintf("%6.02f",$last), RESET;
	} else {
	    $diff = GREEN sprintf("%6.02f",$last), RESET;
	}
	$exch_line .= sprintf(" %14s %7s %4.01f%% %s >",
			      $display_name, large_num($vol),
			      ($vol/$total_vol)*100,$diff);
	if ($idx % 2 == 0) {
	    $exch_line .= "\n";
	}
	$idx++;
    }

    print $exch_line;

    # line for different levels from ATH
    my $current_ath;
    foreach my $tag ( keys %$D ) {
	if ( exists $D->{$tag}->{short} and $D->{$tag}->{short} eq 'ath' ) {
	    $current_ath = $D->{$tag}->{high};
	} else {
	    next;
	}
    }
my @pct_line;     my $pct_idx = 0;
my @agg_line; my $agg_idx =0;
#    print "ATH: $current_ath\n";
#    print "  |";

    my $min = $current_ath;
    my $min_idx = 0;
    my @pct_range = (1, 2.5, 5);
    for ( my $p = 10; $p<=200; $p += 5 ) {
	push @pct_range, $p;
    }
    
    foreach my $pct (reverse @pct_range) {

      # (110,105,100,95,90,80,70,65,60,55,50,45,40,35,30,25,20,15,10,5,2.5,1) {
	my $price = $current_ath*$pct/100;
	push @pct_line, {price=>$price, pct => $pct };
	if ( abs($price-$price_now) < $min ) {
	    $min = abs($price-$price_now);
	    $min_idx = $pct_idx;
	}
	$pct_idx++;
    }
    # uncommented 2016-01-07 to get more space
    for (my $i = $min_idx-2; $i<=$min_idx+2; $i++) { 	printf(" %d%%: %.02f |",	   $pct_line[$i]->{pct}-100, 	   $pct_line[$i]->{price});     }    print "\n";

    # $coins_now;

    $min = $current_ath;
    $min_idx = 0;
    my @value_range = (0.1, 0.25, 0.5);
    push @value_range, (1..100);
    if ( defined $coins_now ) { 
    foreach my $billions (reverse @value_range) {
	my $price = $billions * 1_000_000 * 1_000 / $coins_now;
	push @agg_line, {price => $price, billions=>$billions};
	if ( abs($price - $price_now) < $min ) {
	    $min = abs($price-$price_now);
	    $min_idx= $agg_idx;
	}
	$agg_idx++;
    }
}
    # uncommented 2016-01-07 to get more space
    if ( length(scalar @agg_line) > 0 ) { 
    for (my $i = $min_idx-2; $i<=$min_idx+2; $i++) {
	printf(" %3dB: %0.2f |",
	       $agg_line[$i]->{billions},
	       $agg_line[$i]->{price});
    }
    print "\n";
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

sub oneline_out {
    if ($api_down) {
    print header('text/plain');

	print $api_down_text, "\n";
	return;
    }

    my ($D) = @_;
    print header('text/plain');
    my $line;
    my $price_now = $D->{'now'}->{price_now};
    my @pv = @{$D->{now}->{price_volume}};
    my $p_v = shift @pv;
    my $total_volume = $p_v->{volume};

    $line .= sprintf("Avg price: \$%.02f ", $price_now);
    $line .= sprintf("(H:%.02f/L:%.02f/S:%.02f). Vol: %s. ", (map{$D->{now}->{$_}} qw(24h_max 24h_min)) ,$D->{now}->{"24h_max"} - $D->{now}->{"24h_min"}, large_num($total_volume) );

    $line .= '% change from: ';
    my %seen = ();
    my @array = ();
    foreach my $tag ( sort { $a cmp $b } keys %$D ) {
	next if ( $tag !~ m/^\d+/ );
	my $price;
	if ( $tag =~  'yhi$' or $tag =~ 'ath$' or $tag =~ 'zhi$' ) {
	    $price = $D->{$tag}->{high};
	} elsif ( $tag =~ 'ylo$' or $tag =~ 'zlo$' ) {
	    $price = $D->{$tag}->{low};
	} else {
	    $price= $D->{$tag}->{average};
	}
	$seen{date_time($D->{$tag}->{timestamp})->[0]}++;

	my $short = $D->{$tag}->{short};
	my $pct = $price != 0 ? ( $price_now - $price)/$price * 100 : undef;

	push @array, sprintf("%s %.01f%%; ", $short, $pct) unless ($seen{date_time($D->{$tag}->{timestamp})->[0]} > 1 and $tag =~ /[hi|lo]$/ );
    }
    $line .= join('', @array);
    print "$line- http://is.gd/B7NIP2\n";
}

sub vwap_out {
    my ($D) = @_;
    my @pv = @{$D->{now}->{price_volume}};
    my $p_v = shift @pv;
    my $total_volume = $p_v->{volume};
    my $price_now = $D->{now}->{price_now};
    my $line = sprintf("Volume-weighted average price: \$%.02f Volume: %s | ",$price_now, large_num($total_volume));
    foreach my $el (sort {$b->{vol} <=> $a->{vol}} @pv ) {
	$line .= sprintf("%s \$%.02f (%+.02f) %s (%.01f%%) | ",
			 $el->{display_name},
			 $el->{last},
			 $el->{last}-$price_now,
			 large_num($el->{vol}),
			 $el->{vol}/$total_volume*100
			);
    }
    $line .= "http://is.gd/B7NIP2";
    print header('text/plain');
    if ( $api_down ) {
	print $api_down_text, "\n";
	} else {
	    print $line,"\n";
	}

}

sub html_out {
    my ($D) = @_;
    my $price_now = $api_down?'0.00':$D->{now}->{price_now};
    my $about_page = 'http://gerikson.com/btcticker/about.html';
    print header;
    print start_html(
		     -title=>"$price_now - world's slowest BTC price tracker",
		     -head =>[Link({
				    -rel=>'stylesheet',
				    -type=>'text/css',
				    -media=>'all',
				    -href=>'http://gerikson.com/stylesheets/btcticker.css'
				   })
			     ]);
    if ($api_down) {
	print p($api_down_text);
	return;
    }

    print p("Current volume-weighted average price: ");
    
    ## compare to next-to-last price 
    my $next_to_last = $D->{now}->{next_to_last};
    my $formatted_price = h1($nf->format_number($price_now,2,2));
    if ( defined $next_to_last ) {
	if ( $next_to_last > $price_now ) { #negative price diff
	    $formatted_price = h1({-style=>'color:#dc322f;'},$nf->format_number($price_now,2,2));
	} else {
	    $formatted_price = h1({-style=>'color:#859900;'},$nf->format_number($price_now,2,2));
	}
    }
    print $formatted_price;

    print p("Data fetched on ",
	    format_utc($D->{now}->{fetched}),". ");
    ### 1st section
    my $Kbit = $price_now/1_000;

    my $coins_now = number_of_bitcoins(DateTime->now->jd());
    my @pv = @{$D->{now}->{price_volume}};

    my $p_v = shift @pv;	# first element
#    my $top_table;

    my ( $_24hmax, $_24hmin, $_30dmax, $_30dmin ) =
      map { $D->{now}->{$_} } qw (24h_max 24h_min 30d_max 30d_min );

    # we may have more updated values from the 24h set, use them for
    # the 30d set

    if ( $_24hmax > $_30dmax ) { $_30dmax = $_24hmax }
    if ( $_24hmin < $_30dmin ) { $_30dmin = $_24hmin }

    # we need some gymnastics to get a rowspan here 
    my @top_rows;
    my @top_header = (th(['24h price range','Diff',
			  '30d price range','Diff',
			  'Aggregate figures']));
    push @top_rows, Tr(@top_header);
    my @top_r1 = td(['Max: '.$nf->format_number($_24hmax,2,2),
		     sprintf('%+.02f', $price_now - $_24hmax),
		     'Max: '.$nf->format_number($_30dmax,2,2),
		     sprintf('%+.02f', $price_now - $_30dmax),
		     '24hr volume: '.large_num($p_v->{volume}). " BTC"]);

    push @top_rows, Tr(@top_r1);

    my @top_r2 = td(['Min: '.$nf->format_number($_24hmin,2,2),
		     sprintf('%+.02f', $price_now-$_24hmin),
		     'Min: '.$nf->format_number($_30dmin,2,2),
		     sprintf('%+.02f', $price_now - $_30dmin),
		     $coins_now?'Market cap: '.large_num($coins_now*$price_now).' USD':'n/a']);
    push @top_rows, Tr(@top_r2);
    my @top_r3 = td(['Spread: '.$nf->format_number($_24hmax-$_24hmin,2,2),
		     sprintf('%.01f%%', ($_24hmax-$_24hmin)/$price_now * 100),
		     'Spread: '.$nf->format_number($_30dmax-$_30dmin,2,2),
		    sprintf('%.01f%%', ($_30dmax-$_30dmin)/$price_now * 100),
		     $coins_now?"Est. coins: ".large_num($coins_now).' BTC':'n/a']);
    push @top_rows, Tr(@top_r3);

#     my @top_header = (th(['24hr price range','Diff', 'Aggregate figures', 'bits = 10e-6 BTC', 'USD']));
#     push @top_rows, Tr(@top_header);
#     my @top_r1 = td(['Max: '.$nf->format_number($D->{now}->{'24h_max'},2,2),
# 		   sprintf('%+.02f', $price_now - $D->{now}->{'24h_max'})]);
# #    push @top_r1, td({-rowspan=>'2'}, sprintf('%.02f', $D->{now}->{'24h_max'} - $D->{now}->{'24h_min'}));
#     push @top_r1, td(['24hr volume: '.large_num($p_v->{volume}). " BTC",
# 		   '1,000',
# 		   $nf->format_number($Kbit,2,2)]);
#     push @top_rows, Tr(@top_r1);
#     my @top_r2 = td(['Min: '.$nf->format_number($D->{now}->{'24h_min'},2,2),
# 		   sprintf('%+.02f', $price_now-$D->{now}->{'24h_min'}),
# 		   $coins_now?'Market cap: '.large_num($coins_now*$price_now).' USD':'n/a',
# 		   $nf->format_number(10/$price_now*1_000_000,0,0),
# 		   '10.00']);
#     push @top_rows, Tr(@top_r2);

    print table( {}, @top_rows);
    print p('Volume per exchange (data fetched ',     $D->{now}->{price_volume_timestamp},'): ');

    ### volume information
    my $pv_table;
    my @pv_header; my @pv_row;
    push @pv_header, "Exchange:";
    push @pv_row, "Last price:<br />Diff:<br />Volume:<br />\% of total:";
    foreach my $el (sort {$b->{vol} <=> $a->{vol}} @pv ) {
	my ($exch, $last, $vol, $display_name) =
	  map {$el->{$_}} qw/exch last vol display_name/;
	push @pv_header, $display_name;
	my $last_diff = sprintf("%.02f", $last-$price_now);
	push @pv_row, sprintf("%s<br />%s<br />%s<br />%.01f%%",
			      $nf->format_number($last,2,2),
			      color_num($last_diff),
			      $nf->format_number($vol,2,2),
			      $vol/$p_v->{volume}* 100);

    }
    push @$pv_table, th([@pv_header]);
    push @$pv_table, td([@pv_row]);

    print table( {},
		 Tr({},
		    $pv_table));

    print p("Data source",
	    a({-href=>"https://bitcoinaverage.com/markets#USD"}, "Bitcoinaverage. "),
	    "Prices in USD. Dates and times in UTC.<br /> ", 
	    "Current price is cached and may be delayed for up to 60 seconds. ",
	    
	    a({-href=>$about_page}, "About this page."));


    ## generate table data
    my $table;

    my %coeffs = %{$D->{now}->{coeffs}->[0]};
    my ($k_e, $m_e, $k_l, $m_l) = map {$coeffs{$_}}
      qw(slope_exp intercept_exp slope_lin intercept_lin);

    my $juld_offset = $D->{now}->{first_date};
    my $exp_price =sub {
    	my ($d)=@_;
    	return exp($m_e)*exp($k_e*$d);
    };
    my  $lin_price= sub {
    	my ($d)=@_;
    	return $k_l*$d + $m_l;
    };

    my $ptable;
    my $exp_header = sprintf("Exponential trend<br />%.02f%% / day", $k_e*100);
    my $lin_header = sprintf("Linear trend<br />USD %.02f / day", $k_l);

    push @$table, th([("Event", "Date", "Price",
		       "Difference",  "Change in %",
		       "Volume (BTC)", "Price &#215; Vol",
		       "Market cap"
		      )]);

    push @$ptable, th([("Event", "Date", "Price",
			$exp_header, "Difference",
			$lin_header, "Difference")]);


    my %seen = ();
    foreach my $tag ( sort  by_number keys %$D ) {
	next if ( $tag !~ m/^\d+/ );
	my $price;
	if ( $tag =~  'yhi$' or $tag =~ 'ath$' or $tag =~ 'zhi$' ) {
	    $price = $D->{$tag}->{high};
	} elsif ( $tag =~ 'ylo$' or $tag =~ 'zlo$') {
	    $price = $D->{$tag}->{low};
	} else {
	    $price= $D->{$tag}->{average};
	}


	my $diff = sprintf("%.02f", $price_now - $price);
	my $pct =  sprintf("%.02f%%",($price_now-$price)/$price * 100);
	my $vol = $D->{$tag}->{volume};

	my $tot = $vol? $price * $vol :undef;
	my $no_of_coins =
	  number_of_bitcoins(date_time($D->{$tag}->{timestamp})->[3]);
	my $market_cap = $no_of_coins?large_num($no_of_coins * $price):'n/a';

	my $date = date_time($D->{$tag}->{timestamp})->[2];
	$seen{$date}++;
	push @$table,
	  td([$D->{$tag}->{label} . ' ('.$D->{$tag}->{short}.')',
	      span({
		    -title=>date_time($D->{$tag}->{timestamp})->[1]},
		   $date),
	      $nf->format_number($price,2,2),
	      color_num($diff),
	      color_num($pct),
	      $vol?large_num($vol):"n/a",
	      $tot?large_num($tot):"n/a",
	      $market_cap
	     ]) unless ( $seen{$date} > 1 and $tag =~ /[hi|lo]$/ );

	my $juld = date_time($D->{$tag}->{timestamp})->[3];
	my $exp_pred = &$exp_price($juld-$juld_offset);
	my $lin_pred = &$lin_price($juld);

	my $exp_diff = sprintf("%.02f",$price-$exp_pred);
	my $lin_diff = sprintf("%.02f",$price-$lin_pred);

	push @$ptable,
	  td([$D->{$tag}->{label},
	      span({
		    -title=>date_time($D->{$tag}->{timestamp})->[1]},
		   $date),
	      $nf->format_number($price,2,2),
	      $nf->format_number($exp_pred,2,2),
	      color_num($exp_diff),
	      $nf->format_number($lin_pred,2,2),
	      color_num($lin_diff)])
	    unless ( $seen{$date} > 1 and $tag =~ /[hi|lo]$/ );
    }
    print h2("Current price compared to historical prices");



    print table( {},
		 Tr({},
		    $table));

    print p("Other formats: ",
	    " &raquo; ", a({-href=>'ticker.cgi?o=json'}, " JSON"),
	    #	    " &raquo; ", a({-href=>'ticker.cgi?o=markdown'}, " Markdown"),
	    " &raquo; ", a({-href=>'ticker.cgi?o=irc'}, " IRC one-liner"));

    ### extrapolated values
    print "<a id='extrapolated'></a>";
    print    h2("Historical prices compared to extrapolated trends");
    print table( {},
    		 Tr({},
    		    $ptable));




    print a({-id=>'future'},'');
    print h2("Future extrapolations");
    print p(a{-href=>"$about_page\#future"}, "About this section.");

    # red anniversary

    my $anniv = $D->{now}->{anniv};
    print h3({-class=>'redanniv'}, "Red Anniversary");
    if ( !defined $anniv ) {
	print p(qq/Currently no data is available for this feature./);
    } elsif ($anniv > time ) {	# it's in the future!

    	print p(qq"If the current price of USD ", b($price_now),
		qq/ is constant in the future, then 1 BTC purchased
            last year before the November record high will
            be worth the same on/);
    	print span({-class=>'indent'},p(b(format_utc($anniv))));
    	print p(qq/This date is calculated using interpolated
        values from daily averages in the Bitcoinaverage data set./)
    } else {
	print p(qq/Bitcoin first reached its current price /, b($price_now), qq/ on or around /);

	print span({-class=>'indent'},
		   p(b(span({-title=>format_utc($anniv-365*24*3600,1)->[1]},
			    format_utc($anniv-365*24*3600,1)->[0])),
		     ', ',
		     hum_duration((time-$anniv) + 365*24*3600). ' ago.'));
    }

    ### recent linear price trend
    my $now = time();
    my ($K,$M) = map {$coeffs{$_}} qw(slope_30d intercept_30d);
    my $date_from_price = sub { my ($p) = @_; return ($p - $M)/$K; };
    my $price_from_date = sub { my ($d) = @_; return $K*$d + $M; };
    my %prices = (
		  apr2013hi => {p => 213.72, label => "Apr 2013 high"},
		  prebubbleline =>{ p=> 125, label => "Pre-bubble price level" },
		  gox_end=> { p=> 133.35, label=>'Gox last price'},
		  apr2014lo => { p => 347.68, label => "Apr 2014 low"},
#		       zero => { p => 0,      label => 'All time low' },
		  dollar_parity => { p=> 1, label=> 'Dollar parity' },
#		  current_ltc => {p=>45, label => 'Current Litecoin level (relative to peak)'},
 		  blaze => { p=> 420, label => "Blazin'"},
		  mar2017hi3 => { p=>2*1286.75, label=>'Twice Mar 2017 high'},
#		  nov2013hi2 => { p =>2*1132.26, label => "Twice Nov 2013 high"},
		  ten_k => { p => 10_000, label => "USD 10k" },
		  million => { p => 1_000_000, label => 'MOON' },
		  twice_current => { p => 2*$price_now, label=>"Twice current price"},
		  spartans_hodl => { p => 300, label =>"Spartans HODL!!!" },
		  sixtynine => {p=>69, label=>"Sixty-Nine, \@Hubbabubba's fav"},
		  mining_limit => { p=>200, label=>"Theoretical limit of mining profitability"},
		     );

#        $K = 1; $M=-$M;
    print h3("Future prices based on linear trend from last 90 days");
    print p(sprintf("Current slope: %.02f USD/day. Based on this line, the price will reach: ", $K));

	my $array;
   my $future_table; 
   if ( $K == 0 ) {
	push @$array, "The price will never change in the future.";
    } else {
 
    push @$future_table, th([("Event", "Price", "Date", "ETA")]);

	foreach my $tag ( sort {$prices{$b}->{p} <=> $prices{$a}->{p}}
			  keys %prices ) {
	    my $p = $prices{$tag}->{p};
	    my $d = &$date_from_price($p);
#warn "K: $K, M: $M, p: $p, d: $d\n";
	    next if $d<0; # sometimes we get negative dates?
	    my $epoch_seconds = Jul2Greg($d);
	    my $nf = Number::Format->new();
	    next if (($epoch_seconds - $now) < 2 * 30 * 24 * 3600); # skip stuff closer then 2 months
	    next if ( abs($price_now - $p) / $price_now < 0.1 ); # skip entry if difference to current price less than 10%
	    if ( ($K > 0 and $price_now < $p ) or ( $K < 0 and $price_now > $p )) {
	    push @$future_table,
	      td([$prices{$tag}->{label},
		  $nf->format_number($p),span({-title=>format_utc($epoch_seconds,1)->[1]},format_utc($epoch_seconds,1)->[0]),
	hum_duration($epoch_seconds - $now)]);				      

	    push @$array, sprintf("<i>%s</i> <b>%s</b> in %s, on <b>%s</b>",
				  $prices{$tag}->{label},
				  $nf->format_number($p), hum_duration($epoch_seconds - $now),
				  span({-title=>format_utc($epoch_seconds,1)->[1]},format_utc($epoch_seconds,1)->[0]));
	}
	}
}
	print "<div class='future'>";
#	print ul({-class=>"prices"},li( $array));
    print table( {},
    		 Tr({},
    		    $future_table));

	print "</div>";

    print a({-id=>'random'},'');
    print h2("Random stats and figures");
    print h3("Tim Draper's bitcoins from Silk Road");

    my $sr_coins=$D->{draper}->{coins}; # 29_656.51306529;
    my $buy_price = $D->{draper}->{price_at_purchase}; # 600;
      
    print p(sprintf("On 27 Jun 2014, investor Tim Draper
            paid approximately USD %.02f/coin for %s bitcoins
            seized from Silk Road. ",
		    $buy_price,
		    $nf->format_number($sr_coins,8)));
    print ul({-class=>'prices'},
	     li([
		 sprintf("Purchase price: %s", large_num($sr_coins * $buy_price)),
		 sprintf("Price now: %s", large_num($sr_coins * $price_now)),
		 sprintf("Draper's win/loss: %s", large_num( $sr_coins*($price_now - $buy_price)))
		]));

    print h3("The Bitcoin pizza");
    print p("On 22nd May 2010, Bitcoin enthusiast Laszlo Hanyec bought a pizza for 10,000 bitcoins. More specifically, he sent the coins to someone else who purchased the pizza for him.");

    my $btc_pizza = 10_000;
    my $pizza_now = $btc_pizza * $price_now;

    print p("The bitcoin pizza is currently worth ", b(sprintf("USD&nbsp;%s", $nf->format_number($pizza_now))), ".");
    
    print p("See the ". a({href=>'https://twitter.com/bitcoin_pizza'}, "\@bitcoin_pizza"), " Twitter account for up-to-date values!");

    print h3("The White Mini Cooper");
    print p("On 7 Jun 2014, Andreas M. Antonopoulos offered a white Mini Cooper for sale for 14BTC. At the time, the VWAP was USD 652.76 , so the sales price (assuming it went through) was ", sprintf("USD&nbsp;%s", $nf->format_number(14*652.76)),".");
    print p("Today, the same car is worth ", b(sprintf("USD&nbsp;%s", $nf->format_number(14*$price_now))),".");
    print p("(Source: ", a({href=>'https://twitter.com/aantonop/status/475048024453152768'}, " \@aantonop tweet"),'.)');

    print h3("2016 Bitfinex hack");
    print p("On 2 Aug 2016, the exchange Bitfinex announced they had suffered a security breach and that 119,756 BTC were stolen.");
    print p("Current value of the coins is ", b(sprintf("USD&nbsp;%s", $nf->format_number(119_756 * $price_now))),".");
	    

    print h2("Changelog");
    my @changelog;
    while (<DATA>) {
	chomp;
	push @changelog, $_;
    }
    @changelog = sort {$b cmp $a} @changelog;
    print ul (li(\@changelog));
    print end_html();
}

#### 

my $query = new CGI;
my $output = $query->param('o') || '';

#### 

my $Dates; # reference to store date

my %fixed;
$fixed{180}= {label=>'6 months ago',   short=> '6mo'};
$fixed{1}    ={label => '24 hours ago', short=> '24h'};
$fixed{30}  = {label => '1 month ago', short => '1mo' };
$fixed{365} = {label => '1 year ago',  short => '1yr' };
$fixed{3} = { label => '3 days ago', short=>'3dy' };
$fixed{730}  ={label =>'2 years ago', short=>'2yr'};
$fixed{7}   = {label => '1 week ago',  short => '1wk' };
#$fixed{540} = {label => '18 months ago', short=>'18m'};
### check cached price

my $sth;
# fetch latest price, and the one before that
$sth = $dbh->prepare(qq/select strftime('%s', timestamp), average 
from prices order by timestamp desc limit 2/);
my $rv = $sth->execute();
warn DBI->errstr if $rv < 0;
my ($max_timestamp, $price_now) = @{$sth->fetchrow_arrayref()};
my ($ntl_timestamp, $ntl_price) = @{$sth->fetchrow_arrayref()};
my $now = time();
if ( $now - $max_timestamp > 60 and !$api_down) { # fetch the price

    $max_timestamp = $now;
    $price_now = get('https://api.bitcoinaverage.com/ticker/global/USD/last');
    die "could not get price right now!" unless defined $price_now;

    $sth = $dbh->prepare("insert into prices (timestamp, average) values (datetime('now'), ?)");
    $rv = $sth->execute($price_now);
    warn $DBI::errstr if $rv<0;
	
	# don't care about Next-to-last price, it's probably too old
	$ntl_price = undef;
}
$sth->finish();
# add today's price to keep everything in one hashref
$Dates->{'now'} = {price_now => $price_now,  fetched => $max_timestamp, next_to_last => $ntl_price  };

### get data from history store, compare to price now

### these dates are variable (ATH, YTD etc)
my $labels = { ath=> { label=>'Record high ("ATH")'},
	       ytd=> { label=>"Year to date"},
	       'yhi' =>{ label=>  "This year's high"},
	       'ylo' =>{ label=> "This year's low"},
	       'zhi' =>{ label=> "365d rolling high", short =>'rhi' },
	       'zlo' =>{ label=> "365d rolling low", short=>'rlo'}
	     }; 

foreach my $tag (qw(ath ytd yhi ylo zhi zlo)) {
    my $short;
    if ( defined $labels->{$tag}->{short} ) {
	$short = $labels->{$tag}->{short} }
    else {
	$short = $tag }
    $sth = $dbh->prepare($Sql{$tag});
    $rv =$sth->execute();
    warn DBI->errstr if $rv<0;
    while ( my $ary  =$sth->fetchrow_arrayref ) {
	my ( $day, $timestamp, $high, $low, $average, $volume) = @$ary;
	$Dates->{sprintf("%03d_%s",$day,$tag)} = {
	    timestamp => $timestamp, high=>$high, low=>$low,
	    average=> $average, volume => $volume,
	    short => $short, label => $labels->{$tag}->{label}};
    }
}
$sth->finish();

### we know the day delta

foreach my $day ( sort {$a <=> $b} keys %fixed ) {
    if ( $day == 1 ) { # special case
	my $yesterday = time - 24 * 3600;
	$sth = $dbh->prepare($Sql{'24h'});
	$rv = $sth->execute($yesterday - 45, $yesterday + 45);
	warn DBI->errstr if $rv<0;
	while ( my $ary = $sth->fetchrow_arrayref ) {
	    $Dates->{sprintf("%03d_day", $day)} =
	      { timestamp => $ary->[0], average => $ary->[1],
			     high=>undef,low=>undef,volume=>undef,
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

	$Dates->{sprintf("%03d_day",$day)} =
	  { timestamp => $timestamp, high=>$high, low=>$low,
			 average=> $average, volume => $volume,
			   short => $fixed{$day}->{short},
			   label => $fixed{$day}->{label} };
    }
}
$sth->finish();

### red anniversar
$sth = $dbh->prepare($Sql{anniv});
$rv = $sth->execute($price_now);
warn DBI->errstr if $rv<0;
while ( my @ary = $sth->fetchrow_array ) {
    my ($D_1, $p_1, $D_2, $p_2)  = @ary;
    my $k = ($p_2-$p_1)/($D_2-$D_1); #slope
    my $m = $p_1 - $k * $D_1;
    my $D = ($price_now - $m)/$k + 365*24*3600;
    $Dates->{now}->{anniv} = $D;
}
$sth->finish();

### get coefficients
$sth = $dbh->prepare($Sql{coeffs});
$sth->execute();
my $coeffs = $sth->fetchall_arrayref({});
$Dates->{now}->{coeffs} = $coeffs;
$sth->finish();

### get first julian day in history
my $first_date_ref = $dbh->selectcol_arrayref($Sql{first_date});
$Dates->{now}->{first_date} = $first_date_ref->[0];

### get latest price-volume data
my $price_volume_ref = $dbh->selectrow_arrayref($Sql{price_volume});
$Dates->{now}->{price_volume} =
  calc_price_volume(decode_json($price_volume_ref->[1]));
$Dates->{now}->{price_volume_timestamp} = $price_volume_ref->[0];

### get 24hr min/max values
my $min_max_ref = $dbh->selectcol_arrayref($Sql{daily_min_max},{Columns=>[1,2]});
$Dates->{now}->{'24h_min'} = $min_max_ref->[0];
$Dates->{now}->{'24h_max'} = $min_max_ref->[1];

### get monthly min/max values 
# 'monthly_min_max'
my $min_max_ref2 = $dbh->selectcol_arrayref($Sql{monthly_min_max},{Columns=>[1,2]});
$Dates->{now}->{'30d_min'} = $min_max_ref2->[0];
$Dates->{now}->{'30d_max'} = $min_max_ref2->[1];

### Draper's coins

$Dates->{draper} = {coins => 29656.51306529,
		    price_at_purchase => 600,
		    purchase_value => 600 * 29656.51306529,
		    current_value => $price_now * 29656.51306529,
		    win_loss => ($price_now - 600) * 29656.51306529};
      
### historical coins

$sth = $dbh->prepare($Sql{historical_coins});
$rv = $sth->execute();
warn DBI->errstr if $rv<0;
$historical_coins = $sth->fetchall_hashref(1);
$sth->finish();

### output options

if ( $output eq 'markdown' ) {
    markdown_out($Dates) } 
elsif ($output eq 'json'){
    json_out($Dates);
} elsif ( $output eq 'irc' ) {
    oneline_out($Dates);

} elsif ($output eq 'console') {
console_out($Dates);
} elsif ( $output eq 'debug') {
    debug_out($Dates);
} elsif ($output eq 'vwap') {
    vwap_out($Dates)
}
else {
    html_out($Dates);
}

$dbh->disconnect();


__END__
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
