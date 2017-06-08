#!/usr/bin/perl
use strict;
use warnings;
use DBI;
use DateTime;
use LWP::Simple qw(!head);

my $now = DateTime->now(time_zone=>'UTC');
my $date = $now->strftime("%Y-%m-%d");

open STDERR, '>>', "/home/gustaf/tmp/err_$date.log" or die $!;
my $driver = 'SQLite';
#my $database = '/home/gustaf/prj/BTCPriceTicker/historical-prices.db';
my $database = '/home/www/gerikson.com/cgi-bin/data/historical-prices.db';
my $dsn = "DBI:$driver:dbname=$database";
my ($user, $pass) = ('','');

my $dbh = DBI->connect($dsn, $user, $pass, {RaiseError=>1}) or die $DBI::errstr;

my $price_now = get('https://apiv2.bitcoinaverage.com/ticker/global/USD/last');
warn "==> $price_now\n";
if ( !defined $price_now ) {
    my $ts   = $now->strftime("%Y-%m-%dT%H:%M:%SZ");
    die "[$ts] could not get price right now!" unless defined $price_now;
}

my $sth = $dbh->prepare("insert into prices (timestamp, average) values (datetime('now'), ?)");
my $rv = $sth->execute($price_now);
warn $DBI::errstr if $rv<0;


$dbh->disconnect();
