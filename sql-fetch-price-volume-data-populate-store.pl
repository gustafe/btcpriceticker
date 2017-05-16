#!/usr/bin/perl
use strict;
use warnings;
use DBI;
use Text::CSV;
use LWP::Simple;
use JSON;
use POSIX::strptime;
use POSIX qw(strftime);

local $SIG{__WARN__} = sub {
    my $msg = strftime("[%Y-%m-%dT%H:%M:%SZ] ", gmtime(time)) . shift;
    warn $msg;
};
local $SIG{__DIE__} = sub {
    my $msg = strftime("[%Y-%m-%dT%H:%M:%SZ] ", gmtime(time)) . shift;
    die $msg;
};

my $date = strftime("%Y-%m-%d", gmtime(time));
open STDERR, '>>', "/home/gustaf/tmp/err_$date.log" or die $!;

my $driver = 'SQLite';

my $database = '/home/www/gerikson.com/cgi-bin/data/historical-prices.db';
my $dsn = "DBI:$driver:dbname=$database";
my ($user, $pass) = ('','');

my $dbh = DBI->connect($dsn, $user, $pass, {RaiseError=>1}) or die $DBI::errstr;

my $exchangeurl = "https://api.bitcoinaverage.com/exchanges/USD";

my $json = get( $exchangeurl );
if ( !defined $json ) {
    my $ts = strftime("%Y-%m-%dT%H:%M:%SZ", gmtime(time));
    die "[$ts] Could not get $exchangeurl!";
}


# Decode the entire JSON
my $decoded_json = decode_json( $json );

my $info = $decoded_json;

my $datestring = $info->{timestamp};
delete $info->{timestamp};

my $ts;

if ( defined $datestring ) { 
#  Mon, 22 Sep 2014 13:59:23 -0000
    my ($sec, $min, $hour, $mday, $mon, $year, $wday, $yday)
      = POSIX::strptime($datestring, "%a, %d %b %Y %H:%M:%S -0000");
    $ts = sprintf("%04d-%02d-%02d %02d:%02d:%02d",
		 $year+1900, $mon+1, $mday, $hour, $min, $sec);
} else  {
    $ts = strftime( "%Y-%m-%d %H:%M:%S", gmtime(time));
}

my $data = encode_json( $info );

my $sth = $dbh->prepare("insert into pricevolumes (timestamp, data) values (?,?)");
$sth->execute($ts, $data);

$sth->finish;
$dbh->disconnect;
#warn scalar localtime(time()), " got data with timestamp: $ts\n";
