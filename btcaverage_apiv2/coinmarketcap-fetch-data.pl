#!/usr/bin/perl
use strict;
use warnings;
use JSON;
use List::Util qw/max/;
#use LWP::UserAgent;
use BTCtracker qw/get_dbh get_ua/;

my $url = 'https://api.coinmarketcap.com/v1/ticker/?limit=10';
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
    for my $el ( @{$info} ) {
	push @times, $el->{last_updated};
    }
    my $latest = max @times;
    my $dbh = get_dbh();
    my $sth = $dbh->prepare($sql);
    $sth->execute($latest,to_json($info,{ascii=>1}));
    $sth->finish;
    $dbh->disconnect;
}
