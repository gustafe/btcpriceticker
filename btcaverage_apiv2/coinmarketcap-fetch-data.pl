#!/usr/bin/perl
use strict;
use warnings;
use JSON;
use List::Util qw/max/;

#use LWP::UserAgent;
use BTCtracker qw/get_dbh get_ua/;
my $debug = 0;
#my $url   = 'https://api.coinmarketcap.com/v1/ticker/?limit=10';
my $url   = 'https://api.coinmarketcap.com/v1/ticker/';
#my $url   = 'https://api.coinmarketcap.com/v1/ticker/';
my $sql = "insert into coinmarketcap (timestamp, data)
values (datetime(?,'unixepoch'),?)";
my $ua = get_ua();

my $response = $ua->get($url);

if ( !$response->is_success ) {
    die $response->status_line;

} else {
    my $info = decode_json( $response->decoded_content );

    my $out;
    my @times;
    my $el_count =1;
    my $total_count = 0;
    my $ok_count    = 0;
    my $sum_other   = 0;
    my $sum_top     = 0;
    my %averages = ( available_supply   => 0,
                     total_supply       => 0,
                     percent_change_1h  => 0,
                     percent_change_24h => 0,
                     percent_change_7d  => 0 );
    my $others_ref = { name => 'Others', symbol => 'others', id => 'others' };

    for my $el ( @{$info} ) {
        if ( $el_count <= 10 ) {
            push @{$out}, $el;
            push @times, $el->{last_updated};
            $sum_top += $el->{market_cap_usd};
        } else {
	    
            $total_count++;
            next unless defined( $el->{market_cap_usd} );

            $ok_count++;
            $sum_other += $el->{market_cap_usd};

            # volume weighted average values
            foreach my $tag ( keys %averages ) {
                next unless ( defined $el->{$tag} );
                $averages{$tag} += $el->{$tag} * $el->{market_cap_usd};
            }

        }
        $el_count++;
    }

    my $latest = max @times;
    $others_ref->{rank}           = $total_count;
    $others_ref->{market_cap_usd} = $sum_other;
    foreach my $tag ( keys %averages ) {
        $others_ref->{$tag} = $averages{$tag} / $sum_other;
    }

    push @{$out}, $others_ref;
    push @{$out},
        { latest             => $latest,
          total_mcap         => $sum_top + $sum_other,
          total_other_coins  => $total_count,
          active_other_coins => $ok_count };

    if ($debug) {
        print to_json( $out, { ascii => 1, pretty => 1 } ) if $debug;
    } else {
        my $dbh = get_dbh();
        my $sth = $dbh->prepare($sql);
        $sth->execute( $latest, to_json( $out, { ascii => 1 } ) );
        $sth->finish;
        $dbh->disconnect;
    }

}
