#! /usr/bin/env perl
use Modern::Perl '2015';
###

use Mojo::UserAgent;
use Data::Dump qw/dump dd/;
use JSON;
my $testing =0;

my ( $url, $api_key );
if ($testing) {
    ( $url, $api_key )=('https://sandbox-api.coinmarketcap.com/v1/cryptocurrency/quotes/latest?id=1', 'b54bcf4d-1bca-4e8e-9a24-22ff2c3d462c');
} else {
    ( $url, $api_key )=('https://pro-api.coinmarketcap.com/v1/cryptocurrency/quotes/latest?id=1,1831,3602,825','afeb6511-f298-477b-9823-5b2677df3bfe');
}
#$url = 'https://pro-api.coinmarketcap.com/v1/cryptocurrency/map?limit=200&sort=cmc_rank';
# Request a resource and make sure there were no connection errors
my $ua = Mojo::UserAgent->new;
my $tx = $ua->get($url => {Accept => 'application/json', 'X-CMC_PRO_API_KEY'=>$api_key});
my $res = $tx->result;

# Decide what to do with its representation
if ($res->is_error) {
    say $res->body;
    die;
} elsif ($res->is_success) {
    my $info= decode_json($res->body);
    dd $info;
#    dd $info->{data}->{1}->{quote}->{USD};
#    my $quote = $data->{quote}->{USD};
#    my @percentages = map {'percent_change_'.$_} qw/1h 24h 7d 30d 60d/;
#    for my $key ('price', 'volume_24h', @percentages, 'last_updated' ) {
#	say "$key: ",$info->{data}->{1}->{quote}->{USD}->{$key};
#    }
} else {
    dump $res;
    die;
}
