#!/usr/bin/perl
use strict;
use warnings;
use JSON;
use List::Util qw/max/;
use LWP::UserAgent;

#use LWP::UserAgent;
#use BTCtracker qw/get_dbh get_ua/;
my $debug                  = 0;
my $no_of_coins_to_display = 15 ;
my $testing =1;

my ( $url, $api_key );
if ($testing) {
    ( $url, $api_key )=('https://sandbox-api.coinmarketcap.com/v1/cryptocurrency/quotes/latest?id=1', 'b54bcf4d-1bca-4e8e-9a24-22ff2c3d462c');
} else {
    ( $url, $api_key )=('https://pro-api.coinmarketcap.com/v1/cryptocurrency/quotes/latest?id=1','afeb6511-f298-477b-9823-5b2677df3bfe');
}

#my $url='https://pro-api.coinmarketcap.com/v1/cryptocurrency/listings/latest';
#my $url = 'https://api.coinmarketcap.com/v1/ticker/?limit=0';

my $sql = "insert into coinmarketcap (timestamp, data)
values (datetime(?,'unixepoch'),?)";
{
    no strict "refs";
    no warnings "redefine";
    my $orig_sub = \&LWP::UserAgent::send_request;
    *{"LWP::UserAgent::send_request"} = sub {
        my ($self, $request) = @_;
        print $request->as_string . "\n";
        my $response = $orig_sub->(@_);
        print $response->as_string . "\n";
        return $response;
    };
}

my $ua = LWP::UserAgent->new( ssl_opts => {
        SSL_ca_path     => '/etc/ssl/certs',
        verify_hostname => 1,
    });
#$ua->default_headers->header('X-CMC_PRO_API_KEY'=>'afeb6511-f298-477b-9823-5b2677df3bfe');

# afeb6511-f298-477b-9823-5b2677df3bfe
#$ua->default_header('X-CMC_PRO_API_KEY'=>'afeb6511-f298-477b-9823-5b2677df3bfe');
#    $ua->default_headers->header( 'X-Signature'=>$sig );
#    $ua->default_headers->header( 'X-CMC_PRO_API_KEY'=>$cfg->param('CoinMarketC
my $response = $ua->get($url,
			Accepts=> 'application/json',
 'X-CMC_PRO_API_KEY'=>$api_key);

#if ( !$response->is_success ) {
 #   die $response->status_line;

#} else {
    print $response->decoded_content;
#}
__END__
} else {
    my $info = decode_json( $response->decoded_content );

    my $out;
    my @times;
    my $el_count    = 1;
    my $total_count = 0;
    my $ok_count    = 0;
    my $sum_other   = 0;
    my $sum_top     = 0;
    my %averages = ( available_supply   => 0,
                     total_supply       => 0,
                     percent_change_1h  => 0,
                     percent_change_24h => 0,
                     percent_change_7d  => 0,
                     price_usd          => 0,
                     price_btc          => 0 );
    my $others_ref = { name => 'Others', symbol => 'others', id => 'others' };

    for my $el ( @{$info} ) {
        if ($el_count <= $no_of_coins_to_display
            or $el->{symbol} eq 'BCH'
#	    or $el->{symbol} eq 'BCHSV'
	   )
        {
            push @{$out}, $el;
            push @times, $el->{last_updated};
            $sum_top += $el->{market_cap_usd} ? $el->{market_cap_usd} : 0;
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
