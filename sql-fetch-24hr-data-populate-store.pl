#!/usr/bin/perl
use strict;
use warnings;
use DBI;
use Text::CSV;
use LWP::Simple;
use POSIX qw(strftime);

my $date = strftime("%Y-%m-%d", gmtime(time));
open STDERR, '>>', "/home/gustaf/tmp/err_$date.log" or die $!;
my $driver = 'SQLite';
#my $database = '/home/gustaf/prj/BTCPriceTicker/historical-prices.db';
my $database = '/home/www/gerikson.com/cgi-bin/data/historical-prices.db';
my $dsn = "DBI:$driver:dbname=$database";
my ($user, $pass) = ('','');

my $dbh = DBI->connect($dsn, $user, $pass, {RaiseError=>1}) or die $DBI::errstr;
# https://api.bitcoinaverage.com/history/USD/per_minute_24h_sliding_window.csv
my $data_url = 'https://apiv2.bitcoinaverage.com/history/USD/per_minute_24h_sliding_window.csv';
my $fh;

my $data = get($data_url) ;
if ( !defined $data )  {
    my $ts = strftime("%Y-%m-%dT%H:%M:%SZ", gmtime(time));
    die "[$ts] no data received from $data_url!";
}

open($fh, '<', \$data) || die "couldn't open scalar variable as file: $!";

my $csv = Text::CSV->new( { binary=>1} );
my $inserted = 0;
my $skipped = 0;
while ( my $row = $csv->getline($fh) ) {
    my ($timestamp, $average ) = @{$row}[0,1];
    next unless ( $timestamp =~ m/\d{4}-\d{2}-\d{2}/ );
    #print join(' ', @{$row}),"\n";

    # do we have this data?
    my $sth = $dbh->prepare('select timestamp from history where timestamp=?');
    $sth->execute($timestamp);
    next if ( $sth->fetchrow_array );

    my $rv = $dbh->do('insert into history (timestamp, average) values (?,?)', undef, $timestamp, $average);
    warn $DBI::errstr if $rv < 0;
    $inserted += $rv;
}
#warn "==> Skipped: $skipped, Inserted: $inserted\n";
close $fh;
$csv->eof or $csv->error_diag();
$dbh->disconnect() or warn $DBI::errstr;
