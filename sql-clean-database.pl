#!/usr/bin/perl
use strict;
use warnings;
use DBI;

my $driver = 'SQLite';
my $database = '/home/www/gerikson.com/cgi-bin/data/historical-prices.db';
#my $database = '/home/gustaf/prj/BTCPriceTicker/historical-prices.db';
my $dsn = "DBI:$driver:dbname=$database";
my ($user, $pass) = ('','');

my $dbh = DBI->connect($dsn, $user, $pass, {RaiseError=>1}) or die $DBI::errstr;

my @statements;
push @statements, ['Clean incomplete daily history entries older than 1 month',
		   qq/delete from history
		      where volume is null
		      and  timestamp < datetime('now', '-31 day')/];
push @statements, ['Clean cached ticker data older than 7 days',
		   qq/delete from ticker
where timestamp < datetime('now', '-7 day')/];

push @statements, ['Clean daily price/volume data older than 7 days',
		   qq/delete from pricevolumes
where timestamp < datetime('now', '-7 day')/];


foreach my $sql (@statements) {
    my $sth= $dbh->prepare($sql->[1]);
    my $rv = $sth->execute();
        warn $DBI::errstr if $rv < 0;
    print $sql->[0], ": $rv\n";
}

__END__
my $stmt = "select count(1) from history where low is null and strftime('%s', timestamp) < ?";
my $sth= $dbh->prepare($stmt);
$sth->execute($week);
while  ( my $r = $sth->fetchrow_arrayref ) {
    print join(' ', @$r), "\n";
}


