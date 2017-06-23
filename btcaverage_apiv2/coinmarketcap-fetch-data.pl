#!/usr/bin/perl
use strict;
use warnings;
use JSON;
use List::Util qw/max/;

#use LWP::UserAgent;
use BTCtracker qw/get_dbh get_ua/;
my $debug = 0;
my $url   = 'https://api.coinmarketcap.com/v1/ticker/?limit=10';
#my $url   = 'https://api.coinmarketcap.com/v1/ticker/';
my $sql   = "insert into coinmarketcap (timestamp, data)
values (datetime(?,'unixepoch'),?)";
my $ua = get_ua();

my $response = $ua->get($url);

if ( !$response->is_success ) {
    die $response->status_line;

} else {
    my $info = decode_json( $response->decoded_content );

    my $out;
    my @times;
    my $el_count   = 1;
    my $coin_count = 0;
    my $sum_other  = 0;
    my %changes;
    for my $el ( @{$info} ) {
#        if ( $el_count <= 10 ) {
            push @{$out}, $el;
            push @times, $el->{last_updated};
  #      } else {
#	    warn "==> $el->{name}\n";
   #          $coin_count++;

 #            $sum_other += $el->{market_cap_usd}? $el->{market_cap_usd} : 0;
 # 	    foreach my $tag ('1h','24h','7d') {
 # 		next unless ( exists $el->{'percent_change_'.$tag} );
 # 		$changes{$tag} +=
 # 		  ( $el->{'percent_change_'.$tag}?
 # 		    $el->{'percent_change_'.$tag} : 0 ) *
 # 		      $el->{market_cap_usd} ? $el->{market_cap_usd} : 0;
 # 	    }
 #        }
 # # 
#    $el_count++;
	}
    
    # my $others_ref = {symbol=>$coin_count,rank=>999, name=>'Others',id=>'others',
    # 		      market_cap_usd=>$sum_other, };
    # for my $tag ( '1h','24h','7d') {
    # 	$others_ref->{'percent_change_'.$tag} = $changes{$tag}/$sum_other;
    # }
    # $others_ref->{available_supply} = -1;
    # $others_ref->{total_supply} = -1;

#    push @{$out}, $others_ref;

    my $latest = max @times;

    if ($debug) {
        print to_json( $out, { ascii => 1, pretty => 1 } ) if $debug;
    } else {
        my $dbh = get_dbh();
        my $sth = $dbh->prepare($sql);
        $sth->execute( $latest, to_json( $info, { ascii => 1 } ) );
        $sth->finish;
        $dbh->disconnect;
    }

}
