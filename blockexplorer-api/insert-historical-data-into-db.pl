#!/usr/bin/perl
use strict;
use warnings;
use DBI;
use Text::CSV;
use LWP::Simple;
use JSON;
use POSIX::strptime;
use POSIX qw(strftime);
use DateTime;

my $driver = 'SQLite';

my $database = '/home/www/gerikson.com/cgi-bin/data/historical-prices.db';
my $dsn = "DBI:$driver:dbname=$database";
my ($user, $pass) = ('','');

my $dbh; my $sth;

my $base_url = 'https://blockexplorer.com/api';

sub coins_per_block {
    my ( $blocks ) = @_;
    return undef unless $blocks > 0;
    my $reward = 50;
    my $period = 210_000;
    my $diff = 0;
    my $coins = 0;

    while ( $diff >= 0 ) {
	$diff = $blocks - $period;
	$coins += ( $diff < 0 ? $blocks * $reward : $period * $reward );
	$blocks = $diff;
#	$period = $period * 2;
	$reward = $reward / 2;
    }
    return $coins;
}


sub get_data {
    my ( $api_string, $param ) = @_;
    my $json = get ( "$base_url/$api_string" );
    return undef unless defined $json;
    my $info = decode_json( $json );
#    foreach my $key ( sort keys %{$info} ) {
#	print "$key : $info->{$key}\n";
#    }
    
    return $info->{$param};
}

my $start_block = 14468;
my $interval = 2014;
my ( $current_block, $block_hash, $block_time, $dt ) =
  (  $start_block,  undef,        undef,       undef );
while ( $start_block > 0 ) {
    $block_hash = get_data( "block-index/$current_block", 'blockHash');
    die "can't get data for $current_block!" unless defined $block_hash;
    sleep 4;
    $block_time = get_data( "block/$block_hash", 'time' );
    $dt = DateTime->from_epoch( epoch => $block_time );

    # insert into DB
#    
    $dbh = DBI->connect($dsn, $user, $pass, {RaiseError=>1}) or die $DBI::errstr;
    $sth = $dbh->prepare("insert into blocks (timestamp, block, no_of_coins) values (?,?,?)");
    warn join(' ', ('['.scalar localtime(time()).']:', 'found block', $current_block,'at',$dt->strftime('%Y-%m-%d %H:%M:%S'),coins_per_block( $current_block ))),"\n";
    $sth->execute($dt->strftime('%Y-%m-%d %H:%M:%S'),
		  $current_block,
		  coins_per_block( $current_block ) );

    $sth->finish;
    $dbh->disconnect;
    sleep 6;
    $current_block -= $interval;
}
