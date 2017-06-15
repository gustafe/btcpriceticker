package BTCtracker;

use strict;
use Exporter;
use Digest::SHA qw/hmac_sha256_hex/;
use Config::Simple;
use DBI;
use LWP::UserAgent;

use vars qw/$VERSION @ISA @EXPORT @EXPORT_OK %EXPORT_TAGS/;

$VERSION = 1.00;
@ISA = qw/Exporter/;
@EXPORT = ();
@EXPORT_OK = qw/get_dbh get_ua/;
%EXPORT_TAGS = (DEFAULT => [qw/&signature/]);

my $cfg = Config::Simple->new('/home/gustaf/prj/BTCPriceTicker/btcaverage_apiv2/btctracker.ini');

#### BTCAverage access sig

my $secret = $cfg->param('BTCtracker.secret_key');
my $public = $cfg->param('BTCtracker.public_key');

sub signature {
    my $timestamp = time();

    my $payload = $timestamp .'.'. $public;
    my $hash = hmac_sha256_hex($payload, $secret);
    my $signature = $payload .'.'. $hash;
    return $signature;
}

#### User agent

#### DBH

my $driver = $cfg->param('DB.driver');
my $database = $cfg->param('DB.database');
my $dbuser = $cfg->param('DB.user');
my $dbpass = $cfg->param('DB.password');

sub get_dbh { 
    my $dsn = "DBI:$driver:dbname=$database";
    my $dbh=DBI->connect($dsn, $dbuser, $dbpass, {PrintError=>0}) or die $DBI::errstr;
    return $dbh;
}

sub get_ua {
    my $ua = LWP::UserAgent->new;
    my $sig = signature();
    $ua->default_header('X-Signature'=>$sig);
    return $ua;
}

1;
